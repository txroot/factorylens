# controllers/actions_handler.py
import threading
import time
import json
from typing import Optional
from threading import Event

from flask import current_app as app
from models.actions import Action as ActionModel
from models.device  import Device


def payload_preview(data, max_length=100):
    """
    Generate a summarized preview of any JSON data.
    For dicts, trims long string values.
    For other types, returns a safe summary.
    """
    if isinstance(data, dict):
        preview = {}
        for k, v in data.items():
            if isinstance(v, str) and len(v) > max_length:
                preview[k] = f"[{len(v)} chars]"
            else:
                preview[k] = v
        return preview
    elif isinstance(data, list):
        return [payload_preview(item, max_length) if isinstance(item, dict) else item for item in data[:5]]
    elif isinstance(data, str) and len(data) > max_length:
        return f"[{len(data)} chars]"
    else:
        return data


def _extract_event(raw: str) -> str:
    """
    Extract a simplified string from a raw payload for comparison.
    If the payload is JSON with 'event' or 'ext', return that value;
    otherwise, return the raw string itself.
    """
    try:
        j = json.loads(raw)
        # if it's an object, pick "event" or "ext"
        if isinstance(j, dict):
            if "event" in j:
                return str(j["event"])
            if "ext" in j:
                return str(j["ext"])
        # if it's a bare JSON string/number/list, use it directly
        return str(j)
    except json.JSONDecodeError:
        pass
    return raw


def _compare(raw: str, expected: str, op: str) -> bool:
    """
    Compare `raw` and `expected` using the given operator.
    Tries numeric comparison first; falls back to string comparison.
    """
    try:
        a = float(raw)
        b = float(expected)
    except ValueError:
        a, b = raw, expected

    if op == "==":  return a == b
    if op == "!=" : return a != b
    if op == "<":   return a <  b
    if op == "<=":  return a <= b
    if op == ">":   return a >  b
    if op == ">=":  return a >= b
    return False


class ActionWrapper:
    def __init__(self, model: ActionModel):
        self.id           = model.id
        self.name         = model.name
        self.chain        = model.chain
        self.state        = "idle"      # idle, running, success, error
        self.if_payload   = None          # raw triggering payload
        self.if_extracted = None          # extracted value for comparisons

    def __repr__(self):
        return f"<Action #{self.id} '{self.name}' state={self.state}>"


class ActionManager:
    def __init__(self, mqtt_client, status_interval: float = 30.0):
        self.client      = mqtt_client
        self.flask_app   = getattr(mqtt_client, "_userdata", None)
        self.interval    = status_interval

        # track pending THEN branches and lock
        self._pending    = {}  # action_id → pending info
        self._lock       = threading.Lock()
        # all loaded actions
        self.actions     = {}
        # sets for listening
        self._triggers   = set()  # topics that trigger IF
        self._results    = set()  # topics that deliver THEN results

        self._load_actions()
        self._install_subscriptions()
        threading.Thread(target=self._status_loop, daemon=True).start()

    def _load_actions(self):
        with self.flask_app.app_context():
            self.actions.clear()
            for m in ActionModel.query.filter_by(enabled=True).all():
                self.actions[m.id] = ActionWrapper(m)
            app.logger.info(f"✅ Loaded {len(self.actions)} Actions")

    def _install_subscriptions(self):
        """
        Subscribe only to IF trigger topics and THEN result topics.
        """
        with self.flask_app.app_context():
            for act in self.actions.values():
                # IF trigger
                if_node = next((n for n in act.chain if n.get('source') == 'io'), None)
                if if_node:
                    dev = Device.query.get(if_node['device_id'])
                    if dev and dev.topic_prefix and dev.mqtt_client_id:
                        trig = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{if_node['topic']}"
                        if trig not in self._triggers:
                            app.logger.info(f"Subscribing to {trig} by {act.name}")
                            self.client.subscribe(trig)
                            self.client.message_callback_add(trig, self.on_message)
                            self._triggers.add(trig)

                # THEN result
                then = act.chain[1] if len(act.chain) > 1 else None
                if then:
                    rt = then.get('result_topic', '')
                    if rt:
                        dev = Device.query.get(then['device_id'])
                        if dev and dev.topic_prefix and dev.mqtt_client_id:
                            res = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{rt}"
                            if res not in self._results:
                                self.client.subscribe(res)
                                self.client.message_callback_add(res, self.on_message)
                                self._results.add(res)

    def _status_loop(self):
        while True:
            with self.flask_app.app_context():
                summary = [{"id": a.id, "name": a.name, "state": a.state} for a in self.actions.values()]
                app.logger.info("🕒 actions/status → %s", summary)
                self.client.publish("actions/status", json.dumps(summary))
            time.sleep(self.interval)

    def _set_state(self, act: ActionWrapper, new_state: str):
        act.state = new_state
        self.client.publish(f"actions/{act.id}/status", new_state)

    def handle_message(self, device_id: int, topic: str, payload: str):
        # manual injection
        class Msg: pass
        msg = Msg()
        msg.topic   = topic
        msg.payload = payload.encode()
        self.on_message(self.client, None, msg)

    def on_message(self, client, userdata, msg):
        """
        Called for subscribed topics: either a trigger or a result.
        """
        with self.flask_app.app_context():
            try:
                raw = msg.payload.decode()
            except UnicodeDecodeError:
                self.flask_app.logger.warning(f"[ActionManager] Ignoring binary on {msg.topic}")
                return
            payload = _extract_event(raw)
            topic   = msg.topic
            log     = app.logger

            # 1) handle pending THEN results
            if topic in self._results:
                with self._lock:
                    for aid, pend in list(self._pending.items()):
                        for br, info in pend['branches'].items():
                            if topic == info['topic']:
                                pend['observed']       = payload
                                pend['observed_topic'] = topic
                                pend['event'].set()
                                break

            # 2) handle IF triggers
            if topic in self._triggers:
                for act in self.actions.values():
                    if act.state != 'idle':
                        continue
                    if_node = next((n for n in act.chain if n.get('source')=='io'), None)
                    if not if_node:
                        continue
                    dev = Device.query.get(if_node['device_id'])
                    if not dev:
                        continue
                    full_if = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{if_node['topic']}"
                    cmp_op  = if_node.get('cmp','==')
                    exp     = str(if_node['match']['value'])

                    log.debug(f"Checking IF #{act.id} {act.name!r}: {full_if} {cmp_op} {exp!r}")
                    if topic == full_if and _compare(payload, exp, cmp_op):
                        log.info(f"🔥 IF triggered for '{act.name}' (#{act.id})")
                        self.client.publish(
                            "actions/if/trigger",
                            json.dumps({"action_id": act.id, "topic": topic, "payload": raw})
                        )
                        self._set_state(act, 'running')
                        act.if_payload   = raw
                        act.if_extracted = payload
                        threading.Thread(target=self._execute_then, args=(act,), daemon=True).start()

    def _execute_then(self, act: ActionWrapper):
        with self.flask_app.app_context():
            log  = app.logger
            then = act.chain[1] if len(act.chain) > 1 else None
            if not then:
                self._set_state(act, 'success')
                self._set_state(act, 'idle')
                return

            # fire THEN command
            dev      = Device.query.get(then['device_id'])
            full_cmd = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{then['topic']}"
            cmd      = then['command'] if then['command'] != '$IF' else act.if_payload or ''
            self.client.publish(
                "actions/then/command",
                json.dumps({"action_id": act.id, "topic": full_cmd, "command": cmd})
            )
            log.debug(f"\n→ [THEN] Pub {full_cmd} → {payload_preview(cmd)!r}\n")
            self.client.publish(full_cmd, cmd)

            # if no branches, done
            branches = [n for n in act.chain if n.get('branch') in ('success','error')]
            if not branches:
                self._set_state(act, 'success')
                self._set_state(act, 'idle')
                return

            # prepare to wait for result
            rt      = then.get('result_topic','')
            succ    = next((n for n in branches if n['branch']=='success'), None)
            err     = next((n for n in branches if n['branch']=='error'),   None)
            def full_rt(node):
                t = node.get('result_topic') or rt
                return f"{dev.topic_prefix}/{dev.mqtt_client_id}/{t}" if t else None
            succ_rt = full_rt(succ) if succ else None
            err_rt  = full_rt(err ) if err  else None

            log.debug(f"→ [THEN] Waiting for {succ_rt} or {err_rt}")
            # determine timeout
            to_base = self._to_seconds(then.get('timeout',0), then.get('timeout_unit','sec'))
            to_succ = self._to_seconds(succ.get('timeout',0), succ.get('timeout_unit','sec')) if succ else None
            to_err  = self._to_seconds(err .get('timeout',0), err .get('timeout_unit','sec')) if err  else None
            wait    = min(x for x in (to_succ, to_err, to_base) if x is not None)

            ev = Event()
            with self._lock:
                self._pending[act.id] = {
                    'event': ev,
                    'branches': {
                        **({ 'success': {'topic': succ_rt, 'cmp': succ.get('cmp','=='), 'match': str(succ['match']['value'])} } if succ and succ_rt else {}),
                        **({ 'error':   {'topic': err_rt,  'cmp': err .get('cmp','==' ), 'match': str(err ['match']['value'])} } if err  and err_rt  else {})
                    },
                    'observed': None,
                    'observed_topic': None
                }

            log.debug("Action %s pending branches: %s", act.id, branches)
            ev.wait(wait)
            with self._lock:
                pend = self._pending.pop(act.id, {})
            obs = pend.get('observed')
            top = pend.get('observed_topic')

            self.client.publish(
                "actions/then/result",
                json.dumps({"action_id": act.id, "result_topic": (succ_rt or err_rt) or "", "matched": bool(obs), "payload": obs})
            )

            # choose and run branch
            chosen = None
            if obs is not None:
                if err and top == err_rt and _compare(obs, str(err['match']['value']), err.get('cmp','==')):
                    chosen = 'error'
                elif succ and top == succ_rt and _compare(obs, str(succ['match']['value']), succ.get('cmp','==')):
                    chosen = 'success'
            if not chosen and succ and err:
                chosen = 'error'

            if chosen:
                log.info(f"[THEN] firing '{chosen}' branch for '{act.name}'")
                self._run_branch(act, chosen)
                self._set_state(act, chosen)

            self._set_state(act, 'idle')

    def _run_branch(self, act: ActionWrapper, branch: str):
        with self.flask_app.app_context():
            log = app.logger
            for node in act.chain:
                if node.get('branch') != branch:
                    continue
                dev      = Device.query.get(node['device_id'])
                full_cmd = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{node['topic']}"
                cmd      = node['command'] if node['command'] != '$IF' else act.if_payload or ''
                evt      = f"actions/evaluate/{branch}/command"
                self.client.publish(evt, json.dumps({"action_id": act.id, "topic": full_cmd, "command": cmd}))
                log.info(f" → [{branch.upper()}] Pub {full_cmd} → {cmd!r}")
                self.client.publish(full_cmd, cmd)

    @staticmethod
    def _to_seconds(val: float, unit: str) -> float:
        return {'ms': val/1000, 'sec': val, 'min': val*60, 'hour': val*3600}.get(unit, val)


# singleton
_manager: Optional[ActionManager] = None

def init_action_manager(mqtt_client, status_interval: float = 30.0) -> ActionManager:
    global _manager
    _manager = ActionManager(mqtt_client, status_interval=status_interval)
    return _manager

def get_action_manager() -> Optional[ActionManager]:
    return _manager

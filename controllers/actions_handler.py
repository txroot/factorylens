# controllers/actions_handler.py
import threading
import time
import json
from typing import Optional, Dict, Any
from threading import Event

from flask import current_app as app
from models.actions import Action as ActionModel
from models.device  import Device


# ─── Helpers ───────────────────────────────────────────────────────────

def _extract_event(raw: str) -> str:
    """
    If the payload is JSON with an "event" field, return that;
    else if it has an "ext" field (file snapshot), return that;
    otherwise just return the raw string.
    """
    try:
        j = json.loads(raw)
        if isinstance(j, dict) and "event" in j:
            return str(j["event"])
        if isinstance(j, dict) and "ext" in j:
            return str(j["ext"])
    except json.JSONDecodeError:
        pass
    return raw


def _compare(raw: str, expected: str, op: str) -> bool:
    """
    Compare `raw` and `expected` using op.
    If both parse as floats, do numeric compare; otherwise string compare.
    """
    try:
        a = float(raw)
        b = float(expected)
    except ValueError:
        a, b = raw, expected

    if op == "==":  return a == b
    if op == "!=":  return a != b
    if op == "<":   return a <  b
    if op == "<=":  return a <= b
    if op == ">":   return a >  b
    if op == ">=":  return a >= b
    return False


# ─── ActionWrapper ─────────────────────────────────────────────────────

class ActionWrapper:
    def __init__(self, model: ActionModel):
        self.id         = model.id
        self.name       = model.name
        self.chain      = model.chain
        self.state      = "idle"    # idle, running, success, error
        self.if_payload = None        # triggering payload

    def __repr__(self):
        return f"<Action #{self.id} '{self.name}' state={self.state}>"


# ─── ActionManager ─────────────────────────────────────────────────────

class ActionManager:
    def __init__(self, mqtt_client, status_interval: float = 30.0):
        self.client    = mqtt_client
        self.flask_app = getattr(mqtt_client, "_userdata", None)
        self.interval  = status_interval

        self._pending = {}  # action_id → pending info
        self._lock    = threading.Lock()
        self.actions  = {}

        self._load_actions()
        self._install_subscriptions()

        # periodic status broadcast
        threading.Thread(target=self._status_loop, daemon=True).start()

    def _load_actions(self):
        with self.flask_app.app_context():
            self.actions.clear()
            for m in ActionModel.query.filter_by(enabled=True).all():
                self.actions[m.id] = ActionWrapper(m)
            app.logger.info(f"✅ Loaded {len(self.actions)} Actions")

    def _install_subscriptions(self):
        """
        Subscribe & register callbacks for each action's command and result topics.
        """
        with self.flask_app.app_context():
            for act in self.actions.values():
                for node in act.chain:
                    dev = Device.query.get(node["device_id"])
                    if not dev or not dev.topic_prefix or not dev.mqtt_client_id:
                        continue
                    # command topic
                    cmd_topic = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{node['topic']}"
                    self.client.subscribe(cmd_topic)
                    self.client.message_callback_add(cmd_topic, self.on_message)
                    # result topic if present
                    rt = node.get("result_topic", "")
                    if rt:
                        res_topic = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{rt}"
                        self.client.subscribe(res_topic)
                        self.client.message_callback_add(res_topic, self.on_message)

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
        """
        Legacy entrypoint from controllers/mqtt: wrap raw topic+payload into on_message.
        """
        class Msg: pass
        msg = Msg()
        msg.topic   = topic
        msg.payload = payload.encode()
        self.on_message(self.client, None, msg)

    def on_message(self, client, userdata, msg):
        """
        Callback for both command and result topics:
         1) wake any pending THEN
         2) handle IF triggers
        """
        with self.flask_app.app_context():
            raw     = msg.payload.decode()
            payload = _extract_event(raw)
            topic   = msg.topic
            log     = app.logger

            # 1) wake pending THEN
            with self._lock:
                for aid, pend in list(self._pending.items()):
                    for br, info in pend['branches'].items():
                        if topic == info['topic']:
                            pend['observed']       = payload
                            pend['observed_topic'] = topic
                            pend['event'].set()
                            break

            # 2) IF triggers
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
                exp     = str(if_node['match']['value'])
                cmp_op  = if_node.get('cmp','==')

                log.debug(f"Checking IF #{act.id} {act.name!r}: {full_if} {cmp_op} {exp!r}")
                if topic == full_if and _compare(payload, exp, cmp_op):
                    log.info(f"🔥 IF triggered for '{act.name}' (#{act.id})")
                    self.client.publish(
                        "actions/if/trigger",
                        json.dumps({"action_id": act.id, "topic": topic, "payload": payload})
                    )
                    self._set_state(act, 'running')
                    act.if_payload = payload
                    threading.Thread(target=self._execute_then, args=(act,), daemon=True).start()

    def _execute_then(self, act: ActionWrapper):
        with self.flask_app.app_context():
            log  = app.logger
            then = act.chain[1]
            dev  = Device.query.get(then['device_id'])
            if not dev:
                log.error(f"Action #{act.id}: THEN device missing")
                self._set_state(act, 'error')
                return

            # publish THEN command
            full_cmd = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{then['topic']}"
            cmd      = then['command'] if then['command'] != '$IF' else act.if_payload or ''
            self.client.publish(
                "actions/then/command",
                json.dumps({"action_id": act.id, "topic": full_cmd, "command": cmd})
            )
            log.debug(f"→ [THEN] Pub {full_cmd} → {cmd!r}")
            self.client.publish(full_cmd, cmd)

            # gather eval branches
            branches = [n for n in act.chain if n.get('branch') in ('success','error')]
            if not branches:
                self._set_state(act, 'success')
                self._set_state(act, 'idle')
                return

            then_rt   = then.get('result_topic','')
            succ_node = next((n for n in branches if n['branch']=='success'), None)
            err_node  = next((n for n in branches if n['branch']=='error'),   None)

            def full_rt(node):
                rt = node.get('result_topic') or then_rt
                return f"{dev.topic_prefix}/{dev.mqtt_client_id}/{rt}" if rt else None

            succ_rt = full_rt(succ_node) if succ_node else None
            err_rt  = full_rt(err_node ) if err_node  else None

            base_secs = self._to_seconds(then.get('timeout',0), then.get('timeout_unit','sec'))
            succ_secs = self._to_seconds(succ_node.get('timeout',0), succ_node.get('timeout_unit','sec')) if succ_node else None
            err_secs  = self._to_seconds(err_node.get('timeout',0), err_node.get('timeout_unit','sec')) if err_node  else None
            wait_secs = min(s for s in (succ_secs, err_secs, base_secs) if s is not None)

            ev = Event()
            with self._lock:
                self._pending[act.id] = {
                    'event': ev,
                    'branches': {
                        **({'success':{'topic':succ_rt, 'cmp':succ_node.get('cmp','=='), 'match':str(succ_node['match']['value'])}} if succ_node and succ_rt else {}),
                        **({'error':  {'topic':err_rt,  'cmp':err_node.get('cmp','=='), 'match':str(err_node ['match']['value'])}} if err_node  and err_rt  else {})
                    },
                    'observed': None,
                    'observed_topic': None
                }

            log.debug(f"Waiting up to {wait_secs}s for {succ_rt}, {err_rt}")
            got = ev.wait(wait_secs)
            with self._lock:
                pend = self._pending.pop(act.id, {})
            observed = pend.get('observed')
            obs_topic= pend.get('observed_topic')

            self.client.publish(
                "actions/then/result",
                json.dumps({"action_id":act.id, "result_topic":(succ_rt or err_rt) or "", "matched":bool(got), "payload":observed})
            )

            # choose branch
            chosen=None
            if got and observed is not None:
                err_info = pend['branches'].get('error')
                if err_info and obs_topic==err_info['topic'] and _compare(observed, err_info['match'], err_info['cmp']):
                    chosen='error'
                else:
                    suc_info = pend['branches'].get('success')
                    if suc_info and obs_topic==suc_info['topic'] and _compare(observed, suc_info['match'], suc_info['cmp']):
                        chosen='success'
            if chosen is None and succ_node and err_node:
                chosen='error'
            if chosen:
                log.info(f"[THEN] firing '{chosen}' branch for '{act.name}'")
                self._run_branch(act, chosen)
                self._set_state(act, chosen)

            self._set_state(act, 'idle')

    def _run_branch(self, act: ActionWrapper, branch: str):
        with self.flask_app.app_context():
            log = app.logger
            for node in act.chain:
                if node.get('branch') != branch: continue
                dev = Device.query.get(node['device_id'])
                if not dev:
                    log.error(f"Action #{act.id}: branch device missing")
                    continue
                full_cmd = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{node['topic']}"
                cmd      = node['command'] if node['command']!='$IF' else act.if_payload or ''
                evt      = f"actions/evaluate/{branch}/command"
                self.client.publish(evt, json.dumps({"action_id":act.id,"topic":full_cmd,"command":cmd}))
                log.info(f" → [{branch.upper()}] Pub {full_cmd} → {cmd!r}")
                self.client.publish(full_cmd, cmd)

    @staticmethod
    def _to_seconds(val: float, unit: str) -> float:
        return {'ms': val/1000, 'sec': val, 'min': val*60, 'hour': val*3600}.get(unit, val)


# ─── Singleton holder ───────────────────────────────────────────────────

_manager: Optional[ActionManager] = None

def init_action_manager(mqtt_client, status_interval: float = 30.0) -> ActionManager:
    global _manager
    _manager = ActionManager(mqtt_client, status_interval=status_interval)
    return _manager

def get_action_manager() -> Optional[ActionManager]:
    return _manager
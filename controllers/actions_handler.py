# controllers/actions_handler.py
import os
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


# ------------------------------------------------------------------
# ActionManager
# ------------------------------------------------------------------
class ActionManager:
    def __init__(self, mqtt_client, status_interval: float = 30.0,
                 watchdog_factor: int = 2):
        # ─────────── general state ───────────
        self.last_beat        = time.time()
        self.watchdog_timeout = status_interval * watchdog_factor
        self.client           = mqtt_client
        self.flask_app        = getattr(mqtt_client, "_userdata", None)
        self.interval         = status_interval

        # ─────────── per-action state ────────
        self._pending: dict[int, dict] = {}   # action_id → info
        self._lock     = threading.Lock()
        self.actions   = {}

        # topics we listen to
        self._triggers: set[str] = set()
        self._results : set[str] = set()

        # ─────────── background workers ──────
        threading.Thread(                      # ONE heartbeat thread
            target=self._status_loop,
            name="ActionManager-Heartbeat",
            daemon=True
        ).start()

        threading.Thread(                      # watchdog (unchanged)
            target=self._watchdog_loop,
            name="ActionManager-Watchdog",
            daemon=True
        ).start()

        # ─────────── initialisation ──────────
        self._load_actions()
        self._install_subscriptions()

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
            self.last_beat = time.time()
            time.sleep(self.interval)

    def _watchdog_loop(self):
        """
        Kills the process if the heartbeat has not advanced within
        `self.watchdog_timeout` seconds. Docker will auto-restart.
        """
        while True:
            time.sleep(self.watchdog_timeout)
            if time.time() - self.last_beat > self.watchdog_timeout:
                app.logger.critical(
                    "⚠️  ActionManager heartbeat stalled >%ds – exiting",
                    self.watchdog_timeout
                )
                os._exit(1)      # let Docker restart the container

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
        """
        Fire the THEN command and, if success/error branches exist,
        wait for the outcome published by the *THEN* device.

        ┌── IF  (trigger topic)
        │
        ├── THEN (command topic) ──► result_topic   ← we ONLY watch this
        │                             │
        │                             └─ payload 'success' / 'error'
        │
        ├── EVALUATE success (optional)
        └── EVALUATE error   (optional)
        """
        with self.flask_app.app_context():
            log = app.logger
            log.debug("↪️  _execute_then(%s) entering – chain=%s", act.id, act.chain)

            # ────────────────────────────────────────────────────
            # 1) Grab the THEN node
            # ────────────────────────────────────────────────────
            then = act.chain[1] if len(act.chain) > 1 else None
            if not then:
                log.debug("⚠️  Action %s has no THEN – marking success/idle", act.id)
                self._set_state(act, "success")
                self._set_state(act, "idle")
                return

            # ────────────────────────────────────────────────────
            # 2) Publish the command on the target device/topic
            # ────────────────────────────────────────────────────
            dev_then = Device.query.get(then["device_id"])
            full_cmd = f"{dev_then.topic_prefix}/{dev_then.mqtt_client_id}/{then['topic']}"
            cmd      = then["command"] if then["command"] != "$IF" else act.if_payload or ""

            self.client.publish(
                "actions/then/command",
                json.dumps({"action_id": act.id, "topic": full_cmd, "command": cmd})
            )
            log.debug("🚀 [THEN] Pub %s → %r", full_cmd, payload_preview(cmd))

            self.client.publish(full_cmd, cmd)

            # ────────────────────────────────────────────────────
            # 3) If there are no evaluation branches we're done
            # ────────────────────────────────────────────────────
            branches = [n for n in act.chain if n.get("branch") in ("success", "error")]
            if not branches:
                log.debug("✅ No EVALUATE branches for Action %s – done", act.id)
                self._set_state(act, "success")
                self._set_state(act, "idle")
                return

            succ = next((n for n in branches if n["branch"] == "success"), None)
            err  = next((n for n in branches if n["branch"] == "error"),   None)
            log.debug("🔎 Branch nodes – success=%s  error=%s", succ, err)

            # ────────────────────────────────────────────────────
            # 4) Compute the single *result* topic that tells us
            #    whether the THEN step succeeded or failed
            # ────────────────────────────────────────────────────
            base_rt = then.get("result_topic", "")
            full_rt = (
                f"{dev_then.topic_prefix}/{dev_then.mqtt_client_id}/{base_rt}"
                if base_rt else None
            )

            succ_rt = full_rt if succ else None
            err_rt  = full_rt if err  else None      # both point to the SAME topic

            # ────────────────────────────────────────────────────
            # 5) Timeout calculation
            # ────────────────────────────────────────────────────
            to_base = self._to_seconds(
                then.get("timeout", 0), then.get("timeout_unit", "sec")
            )
            to_succ = self._to_seconds(
                succ.get("timeout", 0), succ.get("timeout_unit", "sec")
            ) if succ else None
            to_err  = self._to_seconds(
                err.get("timeout", 0), err.get("timeout_unit", "sec")
            ) if err else None

            wait = min(x for x in (to_succ, to_err, to_base) if x is not None)
            log.debug(
                "⏳ Waiting %.1fs for result – base=%s  succ_rt=%s  err_rt=%s",
                wait, full_rt, succ_rt, err_rt
            )

            # ────────────────────────────────────────────────────
            # 6) Register the pending wait in the shared dict
            # ────────────────────────────────────────────────────
            ev = Event()
            with self._lock:
                self._pending[act.id] = {
                    "event": ev,
                    "branches": {
                        **({
                            "success": {
                                "topic": succ_rt,
                                "cmp":   succ.get("cmp", "=="),
                                "match": str(succ["match"]["value"])
                            }
                        } if succ and succ_rt else {}),
                        **({
                            "error": {
                                "topic": err_rt,
                                "cmp":   err.get("cmp", "=="),
                                "match": str(err["match"]["value"])
                            }
                        } if err and err_rt else {})
                    },
                    "observed":       None,
                    "observed_topic": None
                }

            log.debug("📌 pending[%s] = %s", act.id, self._pending[act.id])

            # ────────────────────────────────────────────────────
            # 7) Block until we receive the result or timeout
            # ────────────────────────────────────────────────────
            ev.wait(wait)

            with self._lock:
                pend = self._pending.pop(act.id, {})
            obs = pend.get("observed")
            top = pend.get("observed_topic")
            log.debug("🔔 Wait finished – observed=%r  topic=%s", obs, top)

            self.client.publish(
                "actions/then/result",
                json.dumps({
                    "action_id": act.id,
                    "result_topic": full_rt or "",
                    "matched": bool(obs),
                    "payload": obs,
                })
            )

            # ────────────────────────────────────────────────────
            # 8) Decide which branch to fire
            # ────────────────────────────────────────────────────
            chosen = None
            if obs is not None:                       # we got a message
                if err and _compare(
                    obs, str(err["match"]["value"]), err.get("cmp", "==")
                ):
                    chosen = "error"
                elif succ and _compare(
                    obs, str(succ["match"]["value"]), succ.get("cmp", "==")
                ):
                    chosen = "success"
            else:                                     # timeout
                if err:                               # “timeout counts as error”
                    chosen = "error"

            log.debug("🎯 Branch decision for Action %s → %s", act.id, chosen)

            # ────────────────────────────────────────────────────
            # 9) Fire branch (if any) and update state
            # ────────────────────────────────────────────────────
            if chosen:
                log.info("[THEN] firing '%s' branch for '%s'", chosen, act.name)
                self._run_branch(act, chosen)
                self._set_state(act, chosen)

            self._set_state(act, "idle")
            log.debug("🏁 _execute_then(%s) finished – state back to idle", act.id)


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

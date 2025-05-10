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
    otherwise just return the raw string.
    """
    try:
        j = json.loads(raw)
        if isinstance(j, dict) and "event" in j:
            return str(j["event"])
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
        a = raw
        b = expected

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
        self.id    = model.id
        self.name  = model.name
        self.chain = model.chain
        self.state = "idle"    # idle, running, success, error

    def __repr__(self):
        return f"<Action #{self.id} {self.name!r} state={self.state!r}>"


# ─── ActionManager ─────────────────────────────────────────────────────

class ActionManager:
    def __init__(self, mqtt_client, status_interval: float = 30.0):
        self.client    = mqtt_client
        self.flask_app = getattr(mqtt_client, "_userdata", None)
        self.interval  = status_interval

        # pending waits: action_id → { event, topic, payload }
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._lock    = threading.Lock()

        self.actions: Dict[int, ActionWrapper] = {}
        self._load_actions()
        self._install_subscriptions()

        # periodic status logger
        threading.Thread(target=self._status_loop, daemon=True).start()

    def _load_actions(self):
        """Load only *enabled* Actions into memory."""
        with self.flask_app.app_context():
            self.actions.clear()
            for m in ActionModel.query.filter_by(enabled=True).all():
                self.actions[m.id] = ActionWrapper(m)
            app.logger.info(f"✅ Loaded {len(self.actions)} Actions")

    def _install_subscriptions(self):
        with self.flask_app.app_context():
            for act in self.actions.values():
                for node in act.chain:
                    raw = node.get("topic")
                    if not raw:
                        continue
                    dev = Device.query.get(node["device_id"])
                    if not dev or not dev.topic_prefix or not dev.mqtt_client_id:
                        continue
                    full = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{raw}"
                    self.client.subscribe(full)
            # override paho's on_message
            self.client.on_message = self.on_message

    def _status_loop(self):
        while True:
            with self.flask_app.app_context():
                summary = [
                    {"id": act.id, "name": act.name, "state": act.state}
                    for act in self.actions.values()
                ]
                app.logger.info("🕒 actions/status → %s", summary)
                self.client.publish("actions/status", json.dumps(summary))
            time.sleep(self.interval)

    def _set_state(self, act: ActionWrapper, new_state: str):
        act.state = new_state
        topic = f"actions/{act.id}/status"
        self.client.publish(topic, new_state)

    def on_message(self, client, userdata, msg):
        """Universal MQTT handler:  
         1) wake any waiting THEN  
         2) handle IF triggers"""
        with self.flask_app.app_context():
            raw     = msg.payload.decode()
            payload = _extract_event(raw)
            topic   = msg.topic
            log     = app.logger

            # — 1) wake up any pending THEN
            with self._lock:
                for aid, pend in list(self._pending.items()):
                    if topic == pend["topic"]:
                        pend["payload"] = payload
                        pend["event"].set()

            # — 2) check IF for each action
            for act in self.actions.values():
                if act.state != "idle":
                    continue

                if_node = next((n for n in act.chain if n.get("source")=="io"), None)
                if not if_node:
                    continue

                dev = Device.query.get(if_node["device_id"])
                if not dev:
                    continue

                full_if      = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{if_node['topic']}"
                expected_val = str(if_node["match"]["value"])
                cmp_op       = if_node.get("cmp","==")

                log.debug(f"Checking IF #{act.id} {act.name!r}: {full_if} {cmp_op} {expected_val!r}")
                if topic == full_if and _compare(payload, expected_val, cmp_op):
                    log.info(f"🔥 IF triggered for '{act.name}' (#{act.id})")
                    self.client.publish("actions/if/trigger", json.dumps({
                        "action_id": act.id,
                        "topic":     topic,
                        "payload":   payload
                    }))
                    self._set_state(act, "running")
                    threading.Thread(target=self._execute_then, args=(act,), daemon=True).start()

    def _execute_then(self, act: ActionWrapper):
        """Run the THEN command, wait for the result_topic, then dispatch success/error."""
        with self.flask_app.app_context():
            log  = app.logger
            then = act.chain[1]
            dev  = Device.query.get(then["device_id"])
            if not dev:
                log.error(f"Action #{act.id}: THEN device missing")
                self._set_state(act, "error")
                return

            # — publish THEN command
            full_cmd = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{then['topic']}"
            cmd      = then["command"]
            self.client.publish("actions/then/command", json.dumps({
                "action_id": act.id,
                "topic":     full_cmd,
                "command":   cmd
            }))
            log.debug(f"→ [THEN] Pub {full_cmd} → {cmd!r}")
            self.client.publish(full_cmd, cmd)

            # — collect evaluate branches
            branches = [n for n in act.chain[2:] if n.get("branch") in ("success","error")]
            if not branches:
                # no post-THEN logic → immediate finish
                self._set_state(act, "success")
                self._set_state(act, "idle")
                return

            # — if there's no result_topic, immediate success
            res_topic = then.get("result_topic","")
            if not res_topic:
                log.debug("No result_topic → immediate success")
                self._run_branch(act, "success")
                self._set_state(act, "success")
                self._set_state(act, "idle")
                return

            full_res = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{res_topic}"
            then_timeout = then.get("timeout", 0)
            then_unit    = then.get("timeout_unit", "sec")
            secs         = self._to_seconds(then_timeout, then_unit)
            ev           = Event()

            # — prepare separate success/error branch lookups
            succ_node = next((n for n in branches if n.get("branch")=="success"), None)
            err_node  = next((n for n in branches if n.get("branch")=="error"),   None)

            # compute each branch’s own timeout
            succ_secs = (succ_node
                         and self._to_seconds(succ_node.get("timeout", 0),
                                              succ_node.get("timeout_unit", "sec")))
            err_secs  = (err_node
                         and self._to_seconds(err_node.get("timeout", 0),
                                              err_node.get("timeout_unit", "sec")))

            # choose how long to wait:
            if succ_node and err_node:
                # earliest of the two branch timeouts
                wait_secs = min(succ_secs or float("inf"),
                                err_secs  or float("inf"))
            elif err_node:
                wait_secs = err_secs or secs
            elif succ_node:
                wait_secs = succ_secs or secs
            else:
                wait_secs = secs

            # — wait for result payload
            with self._lock:
                self._pending[act.id] = {
                    "event":   ev,
                    "topic":   full_res,
                    "payload": None
                }

            log.debug(f"Waiting up to {wait_secs}s for THEN-result on {full_res!r}")
            got = ev.wait(wait_secs)

            # pull observed payload
            with self._lock:
                pend = self._pending.pop(act.id, {})
            observed = pend.get("payload")

            # publish completion event
            self.client.publish("actions/then/result", json.dumps({
                "action_id":    act.id,
                "result_topic": full_res,
                "matched":      bool(got),
                "payload":      observed
            }))

            # — decide which branch to run
            chosen = None
            if got and observed is not None:
                # 1) error‐match has priority
                if err_node and _compare(
                        observed,
                        str(err_node["match"]["value"]),
                        err_node.get("cmp","==")
                ):
                    chosen = "error"
                # 2) then success‐match
                elif succ_node and _compare(
                        observed,
                        str(succ_node["match"]["value"]),
                        succ_node.get("cmp","==")
                ):
                    chosen = "success"

            # fallback: if both branches exist but no match, run error
            if chosen is None and succ_node and err_node:
                chosen = "error"

            if chosen:
                log.info(f"[THEN] firing '{chosen}' branch for '{act.name}'")
                self._run_branch(act, chosen)
                self._set_state(act, chosen)

            # — back to idle
            self._set_state(act, "idle")

    def _run_branch(self, act: ActionWrapper, branch: str):
        """Send the evaluate‐branch command and publish its event."""
        with self.flask_app.app_context():
            log = app.logger
            for node in act.chain:
                if node.get("branch") != branch:
                    continue

                dev = Device.query.get(node["device_id"])
                if not dev:
                    log.error(f"Action #{act.id}: branch device missing")
                    continue

                full_cmd = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{node['topic']}"
                cmd      = node["command"]
                topic_evt = f"actions/evaluate/{branch}/command"

                self.client.publish(topic_evt, json.dumps({
                    "action_id": act.id,
                    "topic":     full_cmd,
                    "command":   cmd
                }))
                log.info(f" → [{branch.upper()}] Pub {full_cmd} → {cmd!r}")
                self.client.publish(full_cmd, cmd)

    @staticmethod
    def _to_seconds(val: float, unit: str) -> float:
        return {
            "ms":   val / 1000,
            "sec":  val,
            "min":  val * 60,
            "hour": val * 3600
        }.get(unit, val)


# ─── Singleton holder ───────────────────────────────────────────────────

_manager: Optional[ActionManager] = None

def init_action_manager(mqtt_client, status_interval: float = 30.0) -> ActionManager:
    global _manager
    _manager = ActionManager(mqtt_client, status_interval=status_interval)
    return _manager

def get_action_manager() -> Optional[ActionManager]:
    return _manager

import os
import threading
import time
import json
from typing import Optional
from threading import Event
from queue import Full

from flask import current_app as app
from models.actions import Action as ActionModel
from models.device import Device

from controllers.queues import ACTIONS_Q, ALL_QUEUES
from controllers.queue_consumer import QueueConsumerMixin


# ──────────────────────── small helpers ───────────────────────────────
def payload_preview(data, max_length: int = 100):
    if isinstance(data, dict):
        return {
            k: (f"[{len(v)} chars]" if isinstance(v, str) and len(v) > max_length else v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [
            payload_preview(i, max_length) if isinstance(i, dict) else i
            for i in data[:5]
        ]
    if isinstance(data, str) and len(data) > max_length:
        return f"[{len(data)} chars]"
    return data


def _extract_event(raw: str) -> str:
    """Return `event` or `ext` field from JSON, else raw string."""
    try:
        j = json.loads(raw)
        if isinstance(j, dict):
            return str(j.get("event", j.get("ext", raw)))
        return str(j)
    except json.JSONDecodeError:
        return raw


def _compare(raw: str, expected: str, op: str) -> bool:
    """Numeric compare when possible, else string compare."""
    try:
        a, b = float(raw), float(expected)
    except ValueError:
        a, b = raw, expected
    return {
        "==": a == b, "!=": a != b,
        "<": a < b,  "<=": a <= b,
        ">": a > b,  ">=": a >= b
    }.get(op, False)


# ─────────────────────── Action wrapper row ───────────────────────────
class ActionWrapper:
    def __init__(self, model: ActionModel):
        self.id           = model.id
        self.name         = model.name
        self.chain        = model.chain
        self.state        = "idle"          # idle | running | success | error
        self.if_payload   = None            # raw payload that fired IF
        self.if_extracted = None            # value after _extract_event

    def __repr__(self):
        return f"<Action #{self.id} '{self.name}' state={self.state}>"


# ───────────────────── describe for debug ──────────────────────────────
def _describe_action(act: ActionWrapper, idx: int) -> str:
    """
    Summarize an action's IF trigger for debugging.
    """
    if_node = next((n for n in act.chain if n.get("source") == "io"), None)
    trig = "none"
    if if_node:
        dev = Device.query.get(if_node["device_id"])
        if dev:
            topic = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{if_node['topic']}"
            cmp_op = if_node.get("cmp", "==")
            exp   = if_node["match"]["value"]
            trig  = f"{topic} {cmp_op} {exp!r}"
    return f"{idx:>2d}) #{act.id:>3d} {act.name:<30s} IF → {trig}"


# ───────────────────────── ActionManager ──────────────────────────────
class ActionManager(QueueConsumerMixin):
    """
    Consumes messages from the ACTIONS_Q queue and coordinates the IF → THEN
    → EVALUATE flow.  No direct MQTT subscriptions exist; relevance is
    tested via pre-built topic sets.
    """
    _queue     = ACTIONS_Q
    _tag       = "⚙️"
    _n_threads = 8            # THEN waits may block – give us more workers

    # ------------------------------------------------------------------
    # life-cycle
    # ------------------------------------------------------------------
    def __init__(self, mqtt_client, status_interval: float = 30.0,
                 watchdog_factor: int = 2):
        self.client           = mqtt_client
        self.flask_app        = getattr(mqtt_client, "_userdata", None)
        self.last_beat        = time.time()
        self.interval         = status_interval
        self.watchdog_timeout = status_interval * watchdog_factor

        # per-action + pending THEN state
        self.actions:  dict[int, ActionWrapper] = {}
        self._pending: dict[int, dict]          = {}
        self._lock                             = threading.Lock()

        # topic caches
        self._triggers: set[str] = set()
        self._results:  set[str] = set()

        # start heartbeat & watchdog
        threading.Thread(
            target=self._status_loop,
            name="ActionManager-Heartbeat",
            daemon=True
        ).start()
        threading.Thread(
            target=self._watchdog_loop,
            name="ActionManager-Watchdog",
            daemon=True
        ).start()

        # load actions, build topics, then consume queue
        self._load_actions()
        self._build_topic_sets()
        self._start_consumer()

    # ------------------------------------------------------------------
    # QueueConsumerMixin requirements
    # ------------------------------------------------------------------
    def _is_relevant(self, topic: str) -> bool:
        return (topic in self._triggers) or (topic in self._results)

    def _process(self, _dev_id: int, topic: str, payload: str):
        # wrap into fake Paho message
        class _Msg: pass
        msg = _Msg()
        msg.topic   = topic
        msg.payload = payload.encode()
        self.on_message(self.client, None, msg)

    # ------------------------------------------------------------------
    # initialise & debug list
    # ------------------------------------------------------------------
    def _load_actions(self):
        with self.flask_app.app_context():
            self.actions.clear()
            for m in ActionModel.query.filter_by(enabled=True).all():
                self.actions[m.id] = ActionWrapper(m)

            app.logger.info("⚙️  Loaded %d enabled Actions:", len(self.actions))
            for i, a in enumerate(self.actions.values(), 1):
                app.logger.info("⚙️  %s", _describe_action(a, i))

    def _build_topic_sets(self):
        with self.flask_app.app_context():
            self._triggers.clear()
            self._results.clear()

            for act in self.actions.values():
                # IF topics
                if_node = next((n for n in act.chain if n.get("source") == "io"), None)
                if if_node:
                    dev = Device.query.get(if_node["device_id"])
                    if dev and dev.topic_prefix and dev.mqtt_client_id:
                        self._triggers.add(
                            f"{dev.topic_prefix}/{dev.mqtt_client_id}/{if_node['topic']}"
                        )

                # THEN result topics
                then = act.chain[1] if len(act.chain) > 1 else None
                if then:
                    rt = then.get("result_topic")
                    if rt:
                        dev = Device.query.get(then["device_id"])
                        if dev and dev.topic_prefix and dev.mqtt_client_id:
                            self._results.add(
                                f"{dev.topic_prefix}/{dev.mqtt_client_id}/{rt}"
                            )

        app.logger.info("⚙️  ActionManager IF-triggers : %s", sorted(self._triggers))
        app.logger.info("⚙️  ActionManager THEN-results: %s", sorted(self._results))

    # ------------------------------------------------------------------
    # heartbeat & watchdog
    # ------------------------------------------------------------------
    def _status_loop(self):
        while True:
            with self.flask_app.app_context():
                summary = [
                    {"id": a.id, "name": a.name, "state": a.state}
                    for a in self.actions.values()
                ]
                app.logger.info("🕒 actions/status → %s", summary)
                self.client.publish("actions/status", json.dumps(summary))
            self.last_beat = time.time()
            time.sleep(self.interval)

    def _watchdog_loop(self):
        while True:
            time.sleep(self.watchdog_timeout)
            if time.time() - self.last_beat > self.watchdog_timeout:
                app.logger.critical("⚠️  ActionManager heartbeat stalled – exiting")
                os._exit(1)

    # ------------------------------------------------------------------
    # state helper
    # ------------------------------------------------------------------
    def _set_state(self, act: ActionWrapper, new_state: str):
        act.state = new_state
        self.client.publish(f"actions/{act.id}/status", new_state)

    # ------------------------------------------------------------------
    # main handler (reused by queue)
    # ------------------------------------------------------------------
    def on_message(self, client, _userdata, msg):
        with self.flask_app.app_context():
            try:
                raw = msg.payload.decode()
            except UnicodeDecodeError:
                app.logger.warning("[ActionManager] binary payload on %s – skipped", msg.topic)
                return

            payload = _extract_event(raw)
            topic   = msg.topic
            log     = app.logger

            # STEP 1: THEN results
            if topic in self._results:
                with self._lock:
                    for aid, pend in list(self._pending.items()):
                        for br, info in pend["branches"].items():
                            if topic == info["topic"]:
                                pend["observed"]       = payload
                                pend["observed_topic"] = topic
                                pend["event"].set()
                                break

            # STEP 2: IF triggers
            if topic in self._triggers:
                for act in self.actions.values():
                    if act.state != "idle":
                        continue
                    if_node = next((n for n in act.chain if n.get("source") == "io"), None)
                    if not if_node:
                        continue
                    dev = Device.query.get(if_node["device_id"])
                    if not dev:
                        continue

                    full_if = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{if_node['topic']}"
                    cmp_op  = if_node.get("cmp", "==")
                    exp     = str(if_node["match"]["value"])
                    match   = (topic == full_if and _compare(payload, exp, cmp_op))

                    log.debug(
                        "IF-check '%s': incoming=%r  needed=%s  cmp=%s  exp=%r  → %s",
                        act.name, payload, full_if, cmp_op, exp,
                        "MATCH" if match else "no"
                    )

                    if match:
                        log.info("🔥 IF triggered for '%s' (#%s)", act.name, act.id)
                        self.client.publish(
                            "actions/if/trigger",
                            json.dumps({"action_id": act.id, "topic": topic, "payload": raw})
                        )
                        self._set_state(act, "running")
                        act.if_payload   = raw
                        act.if_extracted = payload
                        threading.Thread(
                            target=self._execute_then, args=(act,), daemon=True
                        ).start()

    # ------------------------------------------------------------------
    # THEN + branch execution (with loop-back)
    # ------------------------------------------------------------------
    def _execute_then(self, act: ActionWrapper):
        with self.flask_app.app_context():
            log = app.logger
            then = act.chain[1] if len(act.chain) > 1 else None
            if not then:
                self._set_state(act, "success")
                self._set_state(act, "idle")
                return

            dev_then = Device.query.get(then["device_id"])
            full_cmd = f"{dev_then.topic_prefix}/{dev_then.mqtt_client_id}/{then['topic']}"
            cmd      = then["command"] if then["command"] != "$IF" else act.if_payload or ""

            # publish the THEN command
            self.client.publish(
                "actions/then/command",
                json.dumps({"action_id": act.id, "topic": full_cmd, "command": cmd})
            )
            log.debug("🚀 [THEN] Pub %s → %r", full_cmd, payload_preview(cmd))
            self.client.publish(full_cmd, cmd)

            # ─── NEW: loop the command back into all queues ─────────
            for tag, q in ALL_QUEUES:
                try:
                    q.put_nowait((dev_then.id, full_cmd, cmd))
                    log.debug("%s ← loop-back %s", tag, full_cmd)
                except Full:
                    log.warning("⚠️  %s queue full – dropped loop-back %s", tag, full_cmd)

            # now wait for any success/error branches...
            branches = [n for n in act.chain if n.get("branch") in ("success", "error")]
            if not branches:
                self._set_state(act, "success")
                self._set_state(act, "idle")
                return

            succ = next((n for n in branches if n["branch"] == "success"), None)
            err  = next((n for n in branches if n["branch"] == "error"),   None)

            base_rt = then.get("result_topic", "")
            full_rt = (
                f"{dev_then.topic_prefix}/{dev_then.mqtt_client_id}/{base_rt}"
                if base_rt else None
            )
            succ_rt = full_rt if succ else None
            err_rt  = full_rt if err  else None

            to_base = self._to_seconds(then.get("timeout", 0), then.get("timeout_unit", "sec"))
            to_succ = self._to_seconds(succ.get("timeout", 0), succ.get("timeout_unit", "sec")) if succ else None
            to_err  = self._to_seconds(err.get("timeout", 0), err.get("timeout_unit", "sec"))   if err  else None
            wait    = min(x for x in (to_succ, to_err, to_base) if x is not None)

            ev = Event()
            with self._lock:
                self._pending[act.id] = {
                    "event": ev,
                    "branches": {
                        **({"success": {"topic": succ_rt, "cmp": succ.get("cmp", "=="),
                                        "match": str(succ["match"]["value"])}} if succ_rt else {}),
                        **({"error"  : {"topic": err_rt,  "cmp": err .get("cmp", "=="),
                                        "match": str(err ["match"]["value"])}} if err_rt  else {})
                    },
                    "observed":       None,
                    "observed_topic": None
                }

            ev.wait(wait)

            with self._lock:
                pend = self._pending.pop(act.id, {})
            obs = pend.get("observed")

            self.client.publish(
                "actions/then/result",
                json.dumps({
                    "action_id":    act.id,
                    "result_topic": full_rt or "",
                    "matched":      bool(obs),
                    "payload":      obs,
                })
            )

            chosen = None
            if obs is not None:
                if err and _compare(obs, str(err["match"]["value"]), err.get("cmp", "==")):
                    chosen = "error"
                elif succ and _compare(obs, str(succ["match"]["value"]), succ.get("cmp", "==")):
                    chosen = "success"
            elif err:
                chosen = "error"

            if chosen:
                log.info("[THEN] firing '%s' branch for '%s'", chosen, act.name)
                self._run_branch(act, chosen)
                self._set_state(act, chosen)

            self._set_state(act, "idle")

    def _run_branch(self, act: ActionWrapper, branch: str):
        with self.flask_app.app_context():
            for node in act.chain:
                if node.get("branch") != branch:
                    continue
                dev      = Device.query.get(node["device_id"])
                full_cmd = f"{dev.topic_prefix}/{dev.mqtt_client_id}/{node['topic']}"
                cmd      = node["command"] if node["command"] != "$IF" else act.if_payload or ""
                evt      = f"actions/evaluate/{branch}/command"
                self.client.publish(evt, json.dumps({
                    "action_id": act.id, "topic": full_cmd, "command": cmd
                }))
                app.logger.info(" → [%s] Pub %s → %r", branch.upper(), full_cmd, cmd)
                self.client.publish(full_cmd, cmd)

    @staticmethod
    def _to_seconds(val: float, unit: str) -> float:
        return {
            "ms":   val / 1000,
            "sec":  val,
            "min":  val * 60,
            "hour": val * 3600
        }.get(unit, val)


# ───────────────────────── singleton helpers ──────────────────────────
_manager: Optional[ActionManager] = None


def init_action_manager(mqtt_client, status_interval: float = 30.0) -> ActionManager:
    global _manager
    _manager = ActionManager(mqtt_client, status_interval=status_interval)
    return _manager


def get_action_manager() -> Optional[ActionManager]:
    return _manager

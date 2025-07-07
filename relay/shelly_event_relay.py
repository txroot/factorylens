#!/usr/bin/env python3
"""
Shelly-Relay Microservice (v2)

Bridges Shelly Plus/Pro MQTT-RPC messages to the classic Gen-1 topic tree —
bi-directionally:

  • **Events  →**  `shellies/<legacy>/input_event/<ch>`   and   `input/<ch>`
  • **Status  →**  `shellies/<legacy>/relay/<ch>` (+power/energy) & `input/<ch>`
  • **Commands→**  legacy `relay/<ch>/command` executed via HTTP RPC (requests)

Drop it in its own container; just expose `MQTT_*` and optional `SHELLY_HTTP_*` env vars and it works.
"""
from dotenv import load_dotenv
from pathlib import Path
import os

# ─── Load environment from one level up ───────────────────────────────
dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path)

import argparse
import itertools
import json
import logging
import re
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer

import paho.mqtt.client as mqtt
import requests

# ──────────────────────── Configuration ────────────────────────────────
ENV         = os.environ
BROKER_HOST = ENV.get("MQTT_HOST", "localhost")
BROKER_PORT = int(ENV.get("MQTT_PORT", 1883))
BROKER_USER = ENV.get("MQTT_USER")
BROKER_PASS = ENV.get("MQTT_PASS")
BROKER_TLS  = ENV.get("MQTT_TLS", "false").lower() == "true"
LOG_LEVEL   = ENV.get("LOG_LEVEL", "INFO").upper()

# Optional HTTP-RPC auth
HTTP_USER = ENV.get("SHELLY_HTTP_USER")
HTTP_PASS = ENV.get("SHELLY_HTTP_PASS")

HEARTBEAT_INTERVAL = 30.0  # seconds between self-heartbeat updates
WATCHDOG_FACTOR    = 2     # kill after 2 × interval if heartbeat stalls

# ──────────────────────── Logging ───────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=LOG_LEVEL,
)
log = logging.getLogger("shelly-relay")

# ──────────────────────── State ─────────────────────────────────────────
EvtCounter: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
DeviceMap:  dict[str, str]            = {}   # legacy_id → plus_id
RpcID                               = itertools.count(1)
_last_beat                          = time.time()

# ──────────────────────── Helpers ───────────────────────────────────────
MAC6_RE = re.compile(r"([0-9a-fA-F]{6})$")

def _legacy_id_from_src(src: str) -> str | None:
    """Return `switch-<MAC6>` from Plus/Pro src (e.g. shellyplus2pm-c4d8d557b62c)."""
    if not src:
        return None
    m = MAC6_RE.search(src.replace("-", ""))
    return f"switch-{m.group(1).upper()}" if m else None

def _publish(client: mqtt.Client, topic: str, payload, **kwargs):
    """Helper that stringifies JSON/none as needed and logs."""
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload, separators=(",", ":"))
    client.publish(topic, payload, qos=1, retain=False, **kwargs)
    log.debug("→ %s %s", topic, payload)


# ──────────────────────── MQTT Callbacks ────────────────────────────────

def on_connect(client, userdata, flags, rc, properties=None):
    if rc != 0:
        log.error("MQTT connect failed rc=%s", rc)
        return
    log.info("Connected to MQTT %s:%s", BROKER_HOST, BROKER_PORT)

    # Plus/Pro outbound notifications
    client.subscribe("shellies/events/rpc", qos=1)
    # Plus/Pro periodic status (requires "Generic status update over MQTT" enabled)
    client.subscribe("shellies/+/status/#", qos=1)

    # Legacy Gen-1 commands → HTTP RPC
    client.subscribe("shellies/+/relay/+/command", qos=1)


def on_message(client, userdata, msg):
    global _last_beat
    topic = msg.topic
    payload = msg.payload.decode(errors="ignore")
    log.debug("MQTT ← %s %s", topic, payload)

    # ─── Legacy → HTTP RPC (relay commands) ──────────────────────────────
    if topic.startswith("shellies/") and topic.endswith("/command"):
        parts = topic.split("/")  # shellies/<legacy>/relay/<ch>/command
        if len(parts) == 5 and parts[2] == "relay":
            legacy_id, ch, cmd = parts[1], parts[3], payload.strip().lower()
            plus_id = DeviceMap.get(legacy_id, legacy_id)
            if legacy_id not in DeviceMap:
                log.info("No mapping for %s; using legacy ID for HTTP RPC", legacy_id)

            # build the HTTP-RPC URL
            on_str = "true" if cmd == "on" else "false"
            url = f"http://192.168.1.99/rpc/Switch.Set?id={ch}&on={on_str}"

            # perform HTTP GET and log
            auth = (HTTP_USER, HTTP_PASS) if HTTP_USER else None
            try:
                resp = requests.get(url, auth=auth, timeout=5)
                resp.raise_for_status()
                log.info(
                    "HTTP RPC OK  %s relay/%s %s → GET %s → [%d] %s",
                    legacy_id, ch, cmd, url,
                    resp.status_code,
                    resp.text.strip()
                )
            except Exception as e:
                log.error(
                    "HTTP RPC ERR %s relay/%s %s → GET %s → %s",
                    legacy_id, ch, cmd, url, e
                )
        return

    # ─── Plus/Pro Events (btn, push …) ───────────────────────────────────
    if topic == "shellies/events/rpc":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            log.warning("Bad JSON on events/rpc")
            return

        src    = data.get("src", "")
        method = data.get("method")
        params = data.get("params", {})

        legacy_id = _legacy_id_from_src(src)
        if legacy_id:
            DeviceMap[legacy_id] = src

        if method == "NotifyEvent":
            for ev in params.get("events", []):
                comp  = ev.get("component", "")
                event = ev.get("event", "")
                parts = comp.split(":")
                if len(parts) != 2:
                    continue
                ch = parts[1]

                # Map push events → input_event/<ch>
                code_map = {
                    "single_push": "S",
                    "double_push": "D",
                    "long_push":   "L",
                }
                if event in code_map:
                    cnt = EvtCounter[legacy_id][ch] = EvtCounter[legacy_id][ch] + 1
                    _publish(client,
                             f"shellies/{legacy_id}/input_event/{ch}",
                             {"event": code_map[event], "event_cnt": cnt})

                # Map btn_down/btn_up → input/<ch>
                if event in ("btn_down", "btn_up"):
                    state = 1 if event == "btn_down" else 0
                    _publish(client, f"shellies/{legacy_id}/input/{ch}", state)

        _last_beat = time.time()
        return

    # ─── Plus/Pro Status topics ─────────────────────────────────────────
    m = re.match(r"shellies/([^/]+)/status/([^/]+)", topic)
    if m:
        src, component = m.group(1), m.group(2)
        legacy_id     = _legacy_id_from_src(src)
        if legacy_id:
            DeviceMap[legacy_id] = src

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return

        # Switch status → relay state / power / energy
        if component.startswith("switch:"):
            ch = component.split(":")[1]
            if "output" in data:
                state = "on" if data["output"] else "off"
                _publish(client, f"shellies/{legacy_id}/relay/{ch}", state)
            if "apower" in data:
                _publish(client, f"shellies/{legacy_id}/relay/{ch}/power", data["apower"])
            if ("aenergy" in data and isinstance(data["aenergy"], dict)
                    and "total" in data["aenergy"]):
                _publish(client, f"shellies/{legacy_id}/relay/{ch}/energy",
                         data["aenergy"]["total"])

        # Input status → input/<ch>
        elif component.startswith("input:"):
            ch = component.split(":")[1]
            if "state" in data:
                _publish(client, f"shellies/{legacy_id}/input/{ch}",
                         1 if data["state"] else 0)

        _last_beat = time.time()
        return


# ──────────────────────── Health & Watchdog ───────────────────────────
class _Health(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return
        healthy = (time.time() - _last_beat) < HEARTBEAT_INTERVAL * WATCHDOG_FACTOR
        self.send_response(200 if healthy else 500)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok" if healthy else "dead"}).encode())

    def log_message(self, fmt, *args):
        return  # silence HTTP log

def _run_health():
    HTTPServer(("0.0.0.0", 8080), _Health).serve_forever()

def _watchdog():
    while True:
        time.sleep(HEARTBEAT_INTERVAL * WATCHDOG_FACTOR)
        if (time.time() - _last_beat) > HEARTBEAT_INTERVAL * WATCHDOG_FACTOR:
            log.critical("Heartbeat stalled – exiting for Docker restart")
            os._exit(1)


# ──────────────────────── Main ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Shelly Plus ↔ Gen-1 MQTT relay")
    parser.add_argument("--host", default=BROKER_HOST)
    parser.add_argument("--port", type=int, default=BROKER_PORT)
    args = parser.parse_args()

    client = mqtt.Client()
    client.enable_logger()
    client.on_connect = on_connect
    client.on_message = on_message

    if BROKER_USER:
        client.username_pw_set(BROKER_USER, BROKER_PASS)
    if BROKER_TLS:
        client.tls_set()

    log.info("Connecting to MQTT %s:%s", args.host, args.port)
    client.connect(args.host, args.port, keepalive=60)

    threading.Thread(target=_run_health, daemon=True).start()
    threading.Thread(target=_watchdog, daemon=True).start()

    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Factory-Lens end-to-end watchdog / regression tester
---------------------------------------------------

 * Publishes a Shelly‐Gen2 “short-press” event every 2–5 minutes.
 * Watches factory-lens logs for the rule-engine success pattern.
 * Reports PASS / FAIL and archives failing log chunks.

Author: you (2025-07-15)
"""
import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread

import docker               # docker-sdk-for-python
import paho.mqtt.client as mqtt

###############################################################################
# Configuration constants (override via CLI flags if you like)
###############################################################################

TOPIC      = "shellies/switch-57B62C/input_event/1"
PAYLOAD    = {"event": "S", "event_cnt": 10}

MIN_DELAY  = 120            # 2 min
MAX_DELAY  = 300            # 5 min
TIMEOUT    = 60             # 60 s to consider the test run finished

SUCCESS_PATTERNS = [
    re.compile(r"IF triggered for 'Hikvision - Ftp Upload Success'"),
    re.compile(r"\[THEN] Pub shellies/switch-57B62C/relay/0/command"),
]

###############################################################################
# Helper: follow logs for a given container *since* a unix-epoch timestamp
###############################################################################
def stream_container_logs(container, since: int):
    """
    Generator that yields log lines (decoded to str) from *container*
    starting at unix-timestamp *since*.
    """
    for raw in container.logs(stream=True, follow=True, since=since):
        yield raw.decode(errors="replace").rstrip("\n")

###############################################################################
# Helper: write captured log lines to logs/<timestamp ISO>/factory-lens.log
###############################################################################
def dump_logs(lines):
    ts    = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    fold  = Path("logs") / ts.replace(":", "-")         # ':' breaks on Windows
    fold.mkdir(parents=True, exist_ok=True)
    file  = fold / "factory-lens.log"
    file.write_text("\n".join(lines))
    print(f"[ERROR] Expected pattern not found – logs saved to {file}")
###############################################################################
# One test iteration
###############################################################################
def run_single_test(args, docker_client, mqtt_client):
    delay = random.randint(MIN_DELAY, MAX_DELAY)
    print(f"\nSleeping for {delay} s …", flush=True)
    time.sleep(delay)

    # 1. Send the trigger
    print("Publishing trigger", flush=True)
    mqtt_client.publish(TOPIC, json.dumps(PAYLOAD), qos=0, retain=False)

    start_ts   = int(time.time())
    container  = docker_client.containers.get(args.container)
    captured   = []                # log buffer for potential dump
    matched    = set()
    ok_event   = Event()

    def tail():
        nonlocal matched
        for line in stream_container_logs(container, since=start_ts):
            captured.append(line)
            for idx, pat in enumerate(SUCCESS_PATTERNS):
                if idx not in matched and pat.search(line):
                    matched.add(idx)
            if len(matched) == len(SUCCESS_PATTERNS):
                ok_event.set()
                break

    t0   = time.time()
    th   = Thread(target=tail, daemon=True)
    th.start()

    ok_event.wait(TIMEOUT)
    elapsed = time.time() - t0

    if ok_event.is_set():
        print(f"[OK] Performed well within {elapsed:.2f} s", flush=True)
    else:
        dump_logs(captured)

###############################################################################
# Main: parse CLI, connect services, loop forever
###############################################################################
def main():
    parser = argparse.ArgumentParser(description="Factory-Lens E2E tester")
    parser.add_argument("--mqtt-host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--mqtt-port", type=int,
                        default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--mqtt-user", default=os.getenv("MQTT_USER"))
    parser.add_argument("--mqtt-pass", default=os.getenv("MQTT_PASSWORD"))
    parser.add_argument("--container",  default="factory-lens",
                        help="Docker container to tail logs from")
    args = parser.parse_args()

    # --- mqtt ---
    mqtt_client = mqtt.Client()
    if args.mqtt_user:
        mqtt_client.username_pw_set(args.mqtt_user, args.mqtt_pass)
    mqtt_client.connect(args.mqtt_host, args.mqtt_port, keepalive=30)
    mqtt_client.loop_start()            # background socket housekeeping

    # --- docker ---
    docker_client = docker.from_env()

    print("Started Factory-Lens tester – press Ctrl-C to quit")
    try:
        while True:
            run_single_test(args, docker_client, mqtt_client)
    except KeyboardInterrupt:
        print("\nBye!")

    mqtt_client.loop_stop()
    mqtt_client.disconnect()

###############################################################################
if __name__ == "__main__":
    main()

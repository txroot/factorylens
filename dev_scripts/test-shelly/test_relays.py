#!/usr/bin/env python3
"""
test_relays.py – trigger relay 0, wait 3 s, then relay 1,
using legacy topics if --legacy, else the new RPC schema.
"""
import time
import json
import argparse
import paho.mqtt.client as mqtt

# ───── MQTT CONNECTION ─────
HOST = "10.20.1.31"
PORT = 1883
USER = "ulumin"
PWD  = "ucroniumrosetta"

def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy topic format (shellies/<id>/relay/<ch>/command)"
    )
    p.add_argument(
        "--device",
        required=True,
        help=(
            "Device identifier: "
            "'switch-XXXXXX' for legacy mode, "
            "or the Plus-ID (e.g. shellyplus2pm-c4d8d557b62c) for RPC mode"
        )
    )
    args = p.parse_args()

    # Initialize and connect MQTT
    cli = mqtt.Client()
    cli.username_pw_set(USER, PWD)
    cli.connect(HOST, PORT, keepalive=30)
    cli.loop_start()

    rpc_id = 1
    for ch in (0, 1):
        if args.legacy:
            topic = f"shellies/{args.device}/relay/{ch}/command"
            payload = "on"
        else:
            topic = f"shellies/{args.device}/rpc"
            msg = {
                "id": rpc_id,
                "method": "Switch.Set",
                "params": {"id": ch, "on": True}
            }
            payload = json.dumps(msg, separators=(",", ":"))
            rpc_id += 1

        print(f"→ Publishing: {topic} {payload}")
        cli.publish(topic, payload, qos=1, retain=False)

        # pause: 3 s after channel 0, then 1 s before finishing
        time.sleep(3 if ch == 0 else 1)

    time.sleep(1)  # allow any last packets to send
    cli.loop_stop()
    cli.disconnect()

if __name__ == "__main__":
    main()

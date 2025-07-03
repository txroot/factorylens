#!/usr/bin/env python3
import os
import time
import json
from datetime import datetime
import threading

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# --- Configuration ---
INTERVAL = 60  # seconds between publishes (and log rotation)
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# --- Session state ---
session_lock = threading.Lock()
current_session = None  # holds dict with 'event_cnt', 'start', 'messages'

def flush_session():
    global current_session
    if not current_session:
        return
    ts = current_session["start"].strftime("%Y%m%d%H%M%S")
    filename = os.path.join(LOG_DIR, f"action_{ts}.json")
    data = {
        "event_cnt": current_session["event_cnt"],
        "start": current_session["start"].isoformat(),
        "messages": current_session["messages"]
    }
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote log: {filename}")
    current_session = None

def categorize(topic):
    if topic.startswith("shellies/"):
        return "devices"
    if topic.startswith("actions/"):
        return "actions"
    if topic.startswith("cameras/"):
        return "cameras"
    if topic.startswith("storage/"):
        return "storage"
    return None

# --- MQTT callbacks ---
def on_connect(client, userdata, flags, rc):
    print(f"[{datetime.now().isoformat()}] Connected (rc={rc})")
    subs = [
        ("shellies/switch-0081F2/relay/#", 0),
        ("actions/#", 0),
        ("cameras/HIK-B640HA-0001/snapshot", 0),
        ("storage/#", 0),
    ]
    client.subscribe(subs)
    print(f"Subscribed to: {', '.join(t for t, _ in subs)}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode(errors="ignore")
    print(f"[{datetime.now().isoformat()}] RECV {msg.topic} → {payload}")
    cat = categorize(msg.topic)
    if not cat:
        return
    with session_lock:
        if current_session:
            current_session["messages"][cat].append({
                "timestamp": datetime.now().isoformat(),
                "topic": msg.topic,
                "payload": payload,
                "direction": "recv"
            })

def publish_event(client, event, topic="shellies/switch-0081F2/input_event/1"):
    global current_session
    with session_lock:
        # flush previous session
        flush_session()
        # start new session
        now = datetime.now()
        current_session = {
            "event_cnt": event.get("event_cnt"),
            "start": now,
            "messages": {
                "devices": [],
                "actions": [],
                "cameras": [],
                "storage": []
            }
        }
        # log the published event under devices
        current_session["messages"]["devices"].append({
            "timestamp": now.isoformat(),
            "topic": topic,
            "payload": event,
            "direction": "sent"
        })
    payload_str = json.dumps(event)
    client.publish(topic, payload_str)
    print(f"[{datetime.now().isoformat()}] SENT {topic} → {payload_str}")

def main():
    load_dotenv()
    MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
    MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
    MQTT_USER = os.getenv("MQTT_USER")
    MQTT_PASS = os.getenv("MQTT_PASS")

    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    try:
        while True:
            publish_event(client, {"event": "S", "event_cnt": 2})
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("Interrupted, shutting down")
    finally:
        # flush final session before exit
        with session_lock:
            flush_session()
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()

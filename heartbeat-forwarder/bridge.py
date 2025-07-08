import json
import os
import requests
import paho.mqtt.client as mqtt

# Environment variables
TOPIC           = os.getenv("SUB_TOPIC")
EXPECT_EVENT    = os.getenv("EXPECT_EVENT")
EXPECT_DEVICE   = os.getenv("EXPECT_DEVICE")
SHELLY_IP       = os.getenv("SHELLY_IP")
# Gen3 relay RPC endpoint for turning on/off
SHELLY_ENDPOINT = os.getenv("SHELLY_ENDPOINT", "/rpc/Switch.Set")
# Force POST for Set operations
HTTP_METHOD     = "POST"
# Relay index if multiple channels (0-based)
SHELLY_ID       = int(os.getenv("SHELLY_ID", "0"))

MQTT_BROKER     = os.getenv("MQTT_BROKER")
MQTT_PORT       = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER       = os.getenv("MQTT_USER")
MQTT_PASSWORD   = os.getenv("MQTT_PASSWORD")


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT broker, subscribing to {TOPIC}")
        client.subscribe(TOPIC)
    else:
        print(f"MQTT connection failed with code {rc}")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
    except json.JSONDecodeError:
        print("Received invalid JSON, ignoring")
        return

    event     = payload.get("event")
    device_id = str(payload.get("device_id"))

    if event == EXPECT_EVENT and device_id == EXPECT_DEVICE:
        url = f"http://{SHELLY_IP}{SHELLY_ENDPOINT}"
        print(f"Heartbeat matched: sending POST to {url}")
        try:
            body = {"id": SHELLY_ID, "on": True}
            response = requests.post(url, json=body, timeout=5)
            response.raise_for_status()
            print(f"Shelly relay turned on, status {response.status_code}")
        except requests.RequestException as e:
            print(f"Error sending to Shelly: {e}")


# MQTT client setup
client = mqtt.Client()
if MQTT_USER and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
client.loop_forever()
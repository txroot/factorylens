# controllers/mqtt.py

import threading
import os
from datetime import datetime

import paho.mqtt.client as mqtt
from extensions import db
from models.device import Device

_MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
_MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
_CLIENT_ID = "factorylens-backend"


def _on_connect(client, userdata, flags, rc, properties=None):
    """
    userdata will be your Flask `app`.
    """
    app = userdata
    app.logger.info("MQTT connected RC=%s", rc)
    client.subscribe("shellies/+/+/#")


def _on_message(client, userdata, msg):
    app = userdata
    with app.app_context():  # <- this is the fix
        try:
            topic = msg.topic
            payload = msg.payload.decode()

            print(f"[MQTT] Received message -> Topic: {topic} | Payload: {payload}")

            parts = topic.split("/")
            if len(parts) < 3:
                print(f"[MQTT] Ignored: topic has insufficient parts -> {parts}")
                return

            dev_id = parts[1]
            group = parts[2]

            print(f"[MQTT] Parsed -> Device ID: {dev_id} | Group: {group}")

            dev = Device.query.filter_by(mqtt_client_id=dev_id).first()
            if not dev:
                print(f"[MQTT] Warning: Device not found in DB for ID '{dev_id}'")
                return

            values = dev.values or {}
            print(f"[MQTT] Current stored values for {dev_id}: {values}")

            if group == "relay" and len(parts) >= 5:
                ch, prop = parts[3], parts[4]
                print(f"[MQTT] Relay update -> Channel: {ch} | Prop: {prop} | Value: {payload}")
                values.setdefault("relay", {}).setdefault(ch, {})[prop] = payload

            elif group == "input" and len(parts) >= 4:
                idx = parts[3]
                print(f"[MQTT] Input update -> Index: {idx} | Value: {payload}")
                try:
                    values.setdefault("input", {})[idx] = int(payload)
                except ValueError:
                    print(f"[MQTT] Input payload is not an int: '{payload}'")

            elif group in ("temperature", "temperature_f", "voltage"):
                print(f"[MQTT] Sensor update -> {group}: {payload}")
                try:
                    values[group] = float(payload)
                except ValueError:
                    print(f"[MQTT] Sensor payload is not a float: '{payload}'")

            else:
                print(f"[MQTT] Unhandled group '{group}' or unexpected topic format")

            dev.values = values
            dev.status = "online"
            dev.last_seen = datetime.utcnow()
            db.session.commit()

            print(f"[MQTT] Successfully updated device '{dev_id}'")

        except Exception as e:
            app.logger.error("MQTT msg-handler error: %s", e)
            print(f"[MQTT] ERROR during message handling: {e}")
def init_mqtt(app):
    """
    Should be called once from create_app().
    Spins up a background thread for the MQTT loop, 
    and uses Flask `app` as Paho userdata so our callbacks can log safely.
    """
    client = mqtt.Client(
        client_id=_CLIENT_ID,
        protocol=mqtt.MQTTv5  # or MQTTv311 if your broker only speaks 3.1.1
    )

    # stash the Flask app in userdata
    client.user_data_set(app)

    client.on_connect = _on_connect
    client.on_message = _on_message

    client.connect(_MQTT_HOST, _MQTT_PORT, keepalive=30)

    th = threading.Thread(target=client.loop_forever, daemon=True)
    th.start()

    app.mqtt = client
    app.logger.info("MQTT thread started")

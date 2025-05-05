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
    try:
        topic = msg.topic
        payload = msg.payload.decode()
        parts = topic.split("/")
        if len(parts) < 3:
            return

        dev_id = parts[1]      # e.g. "switch-0081F2"
        group  = parts[2]      # e.g. "relay", "input", "temperature", etc.

        dev = Device.query.filter_by(mqtt_client_id=dev_id).first()
        if not dev:
            return

        values = dev.values or {}
        if group == "relay" and len(parts) >= 5:
            ch, prop = parts[3], parts[4]
            values.setdefault("relay", {}) \
                  .setdefault(ch, {})[prop] = payload

        elif group == "input" and len(parts) >= 4:
            idx = parts[3]
            values.setdefault("input", {})[idx] = int(payload)

        elif group in ("temperature", "temperature_f", "voltage"):
            values[group] = float(payload)

        dev.values = values
        dev.status = "online"
        dev.last_seen = datetime.utcnow()
        db.session.commit()

    except Exception as e:
        app.logger.error("MQTT msg-handler error: %s", e)


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

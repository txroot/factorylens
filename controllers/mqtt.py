# controllers/mqtt.py
import os, threading, copy
from datetime import datetime

import paho.mqtt.client as mqtt
from extensions import db
from models.device import Device

_MQTT_HOST  = os.getenv("MQTT_HOST", "localhost")
_MQTT_PORT  = int(os.getenv("MQTT_PORT", 1883))
_CLIENT_ID  = "factorylens-backend"


# ── MQTT callbacks ────────────────────────────────────────────────────
def _on_connect(client, app, flags, rc, properties=None):
    app.logger.info("MQTT connected RC=%s", rc)
    client.subscribe("shellies/+/+/#")


def _on_message(client, app, msg):
    with app.app_context():

        topic   = msg.topic
        payload = msg.payload.decode()
        parts   = topic.split("/")

        app.logger.debug("MQTT → New message: %s → %s", topic, payload)

        if len(parts) < 3:                      # shellies/<id>/<group>/...
            return

        dev_id, group = parts[1], parts[2]
        dev = Device.query.filter_by(mqtt_client_id=dev_id).first()
        if not dev:
            app.logger.warning("MQTT: Unknown device %s", dev_id)
            return

        # ------- copy the existing JSON so SQLAlchemy sees a *new* object
        values = copy.deepcopy(dev.values) if dev.values else {}

        handled = False

        # ── RELAY ───────────────────────────────────────────────────────
        if group == "relay":
            if len(parts) == 4:                         # state (“on” / “off”)
                ch = parts[3]
                app.logger.debug("MQTT: Relay‑state %s/%s → %s", dev_id, ch, payload)
                values.setdefault("relay", {}) \
                      .setdefault(ch, {})["state"] = payload
                handled = True

            elif len(parts) >= 5:                       # power / energy …
                ch, prop = parts[3], parts[4]
                app.logger.debug("MQTT: Relay‑prop %s/%s/%s → %s",
                                 dev_id, ch, prop, payload)
                values.setdefault("relay", {}) \
                      .setdefault(ch, {})[prop] = payload
                handled = True

        # ── INPUTS ──────────────────────────────────────────────────────
        elif group == "input" and len(parts) >= 4:
            idx = parts[3]
            try:
                values.setdefault("input", {})[idx] = int(payload)
                app.logger.debug("MQTT: Input %s/%s → %s", dev_id, idx, payload)
                handled = True
            except ValueError:
                app.logger.error("MQTT: Invalid input payload %r", payload)

        # ── SIMPLE SENSORS ─────────────────────────────────────────────
        elif group in ("temperature", "temperature_f", "voltage"):
            try:
                values[group] = float(payload)
                app.logger.debug("MQTT: Sensor %s → %s", group, payload)
                handled = True
            except ValueError:
                app.logger.error("MQTT: Invalid %s payload %r", group, payload)

        # Handle special "online" topic from LWT
        elif group == "online":
            # store boolean online state in values, just like temp/voltage/etc.
            is_online = payload.strip().lower() == "true"
            values["online"] = is_online
            app.logger.debug("MQTT: LWT online → %s", is_online)
            handled = True

        # ── Skip anything we don’t handle ──────────────────────────────
        if not handled:
            app.logger.debug("MQTT: skipping unhandled topic %s", parts)
            return

        # ------- commit ------------------------------------------------
        app.logger.debug("MQTT: Device %s values before commit: %s", dev_id, values)

        dev.values    = values        # NEW object ⇒ SQLAlchemy marks dirty
        #dev.status    = "online"
        dev.last_seen = datetime.utcnow()
        db.session.commit()

        app.logger.debug("MQTT: Committed updated values for %s with values: %s", dev_id, values)


# ── one‑time initialiser ──────────────────────────────────────────────
def init_mqtt(app):
    """
    Call once from create_app(); starts a background thread that keeps a single
    MQTT connection alive for the whole Flask process.
    """
    client = mqtt.Client(client_id=_CLIENT_ID, protocol=mqtt.MQTTv5)
    client.user_data_set(app)
    client.on_connect  = _on_connect
    client.on_message  = _on_message

    client.connect(_MQTT_HOST, _MQTT_PORT, keepalive=30)

    t = threading.Thread(target=client.loop_forever, daemon=True)
    t.start()

    app.mqtt = client
    app.logger.info("MQTT thread started")

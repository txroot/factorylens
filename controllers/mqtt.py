# mqtt_client.py

import os
import threading
import copy
import math
import json
import time
from datetime import datetime
from queue import Full

import paho.mqtt.client as mqtt

from extensions import db
from models.device import Device
from controllers.queues import ALL_QUEUES   # ⚙️ 📸 💾 bounded queues

# ─── Broker parameters ────────────────────────────────────────────────
_MQTT_HOST  = os.getenv("MQTT_HOST", "localhost")
_MQTT_PORT  = int(os.getenv("MQTT_PORT", 1883))
_CLIENT_ID  = "factorylens-backend"

# ─── MQTT callbacks ───────────────────────────────────────────────────
def _on_connect(client, app, flags, rc, properties=None):
    try:
        app.logger.info("MQTT connected RC=%s", rc)

        # 1 Shelly devices
        client.subscribe("shellies/+/+/#")

        # 2 Every enabled Device’s own prefix
        with app.app_context():
            for dev in Device.query.filter_by(enabled=True).all():
                if not dev.topic_prefix:
                    continue
                topic = f"{dev.topic_prefix}/#"
                client.subscribe(topic)
                app.logger.info(" ↪ subscribed to %s", topic)

        # 3 Generic wild-cards
        client.subscribe("cameras/#")
        client.subscribe("storage/#")

    except Exception:
        app.logger.exception("Error in on_connect")
        # no rollback needed

def _on_message(client, app, msg):
    try:
        with app.app_context():
            topic   = msg.topic
            payload = msg.payload.decode()
            parts   = topic.split("/")

            # preview
            try:
                preview = payload_preview(json.loads(payload))
            except Exception:
                preview = payload
            app.logger.debug("MQTT → %s → %s", topic, preview)

            if len(parts) < 3:
                return

            dev_id, group = parts[1], parts[2]
            dev = Device.query.filter_by(mqtt_client_id=dev_id).first()
            if not dev:
                app.logger.warning("MQTT: unknown device %s", dev_id)
                return

            values  = copy.deepcopy(dev.values) if dev.values else {}
            handled = False

            # ─── topic‐specific parsing ─────────────────────────────
            if group == "relay":
                if len(parts) == 4:
                    ch = parts[3]
                    app.logger.debug("Relay-state %s/%s → %s", dev_id, ch, payload)
                    values.setdefault("relay", {}).setdefault(ch, {})["state"] = payload
                    handled = True
                elif len(parts) >= 5:
                    ch, prop = parts[3], parts[4]
                    app.logger.debug("Relay-prop %s/%s/%s → %s", dev_id, ch, prop, payload)
                    values.setdefault("relay", {}).setdefault(ch, {})[prop] = payload
                    handled = True

            elif group == "input" and len(parts) >= 4:
                idx = parts[3]
                try:
                    values.setdefault("input", {})[idx] = int(payload)
                    app.logger.debug("Input %s/%s → %s", dev_id, idx, payload)
                    handled = True
                except ValueError:
                    app.logger.error("Invalid input payload %r", payload)

            elif group == "input_event" and len(parts) >= 4:
                ch = parts[3]
                try:
                    evt = json.loads(payload)
                except json.JSONDecodeError:
                    evt = {"event": payload}
                values.setdefault("input_event", {})[ch] = evt
                app.logger.debug("Input-event %s/%s → %s", dev_id, ch, evt)
                handled = True

            elif group in ("temperature", "temperature_f", "voltage"):
                try:
                    val = float(payload)
                    values[group] = math.trunc(val * 100) / 100   # 2 dp
                    app.logger.debug("Sensor %s → %.2f", group, values[group])
                    handled = True
                except ValueError:
                    app.logger.error("Invalid %s payload %r", group, payload)

            elif group == "online":
                is_online = payload.strip().lower() == "true"
                values["online"] = is_online
                app.logger.debug("LWT online → %s", is_online)
                handled = True

            # ─── enqueue for all managers ─────────────────────────
            for tag, q in ALL_QUEUES:
                try:
                    q.put_nowait((dev.id, topic, payload))
                    app.logger.debug("%s ← queued %s", tag, topic)
                except Full:
                    app.logger.warning("⚠️  %s queue full – dropped %s", tag, topic)

            # ─── persist & heartbeat ─────────────────────────────
            if handled:
                dev.values = values
            dev.last_seen = datetime.utcnow()
            db.session.commit()

    except Exception:
        app.logger.exception("Error handling MQTT message")
        db.session.rollback()


def _on_disconnect(client, app, rc):
    app.logger.warning("MQTT disconnected (rc=%s), attempting reconnect…", rc)
    while True:
        try:
            client.reconnect()
            app.logger.info("MQTT reconnected")
            break
        except Exception as e:
            app.logger.error("Reconnect failed: %s", e)
            time.sleep(5)


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


# ─── one-time initializer ────────────────────────────────────────────
def init_mqtt(app):
    client = mqtt.Client(client_id=_CLIENT_ID, protocol=mqtt.MQTTv5)
    client.user_data_set(app)

    # callbacks
    client.on_connect    = _on_connect
    client.on_message    = _on_message
    client.on_disconnect = _on_disconnect

    # built-in Paho logging (shows PINGREQ, PINGRESP, reconnects, etc.)
    client.enable_logger(app.logger)

    # auto back-off between reconnect attempts
    client.reconnect_delay_set(min_delay=1, max_delay=120)

    # connect & start background thread
    client.connect(_MQTT_HOST, _MQTT_PORT, keepalive=60)
    client.loop_start()

    # kick off your managers
    from controllers.camera_handler   import init_camera_manager
    from controllers.storage_handler  import init_storage_manager
    from controllers.actions_handler  import init_action_manager

    app.camera_manager  = init_camera_manager(client)
    app.storage_manager = init_storage_manager(client)
    app.action_manager  = init_action_manager(client)

    app.mqtt = client
    app.logger.info("MQTT loop started")

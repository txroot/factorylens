import os
import json
import time
import base64
import threading
from datetime import datetime

from flask import current_app as app
from extensions import db
from models.device import Device


class StorageManager:
    def __init__(self, mqtt_client):
        self.client    = mqtt_client
        self.flask_app = getattr(mqtt_client, "_userdata", None)
        self._install_subscriptions()

        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def _install_subscriptions(self):
        with self.flask_app.app_context():
            for dev in Device.query.filter_by(enabled=True).all():
                base  = f"{dev.topic_prefix}/{dev.mqtt_client_id}"
                topic = f"{base}/file/create"
                self.client.subscribe(topic)
                self.client.message_callback_add(topic, self.on_create)

    def on_create(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            file_b64 = data.get("file")
            ext      = data.get("ext", "bin").lower().strip(".")
            name     = data.get("name", f"file_{int(time.time())}")
            relpath  = data.get("path", None)
            content  = base64.b64decode(file_b64)

            prefix, client_id, _ = msg.topic.split("/", 2)
            with self.flask_app.app_context():
                dev = Device.query.filter_by(mqtt_client_id=client_id).first()
                if not dev:
                    self.flask_app.logger.error(f"No device found for client_id={client_id}")
                    return

                base_path = dev.parameters.get("base_path", "/tmp")
                full_dir  = os.path.join(base_path, os.path.dirname(relpath or "")) if relpath else base_path
                os.makedirs(full_dir, exist_ok=True)
                
                filename  = f"{name}.{ext}"
                full_path = os.path.join(full_dir, filename)
                with open(full_path, "wb") as f:
                    f.write(content)

                topic_out = f"{prefix}/{client_id}/file/new"
                payload   = json.dumps({"path": os.path.relpath(full_path, base_path)})
                self.client.publish(topic_out, payload)
                self.flask_app.logger.info(f"[StorageManager] Saved file to {full_path}")

                log_topic = f"{prefix}/{client_id}/log"
                log = {
                    "event":     "file_saved",
                    "filename":  filename,
                    "path":      os.path.relpath(full_path, base_path),
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.client.publish(log_topic, json.dumps(log))

        except Exception as e:
            self.flask_app.logger.error(f"[StorageManager] file/create failed: {e}")

    def _poll_loop(self):
        while True:
            now = datetime.utcnow()
            with self.flask_app.app_context():
                for dev in Device.query.filter_by(enabled=True).all():
                    topic = f"{dev.topic_prefix}/{dev.mqtt_client_id}/log"
                    log = {
                        "event":     "heartbeat",
                        "device_id": dev.id,
                        "timestamp": now.isoformat()
                    }
                    self.client.publish(topic, json.dumps(log))
            time.sleep(5.0)


_manager = None

def init_storage_manager(mqtt_client, status_interval=None):
    global _manager
    _manager = StorageManager(mqtt_client)

def get_storage_manager():
    return _manager

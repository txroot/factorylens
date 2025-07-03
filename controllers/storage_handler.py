import os
import json
import time
import base64
import threading
from datetime import datetime

from flask import current_app as app
from extensions import db
from models.device import Device

def payload_preview(data, max_length=100):
    """
    Generate a summarized preview of any JSON data.
    For dicts, trims long string values.
    For other types, returns a safe summary.
    """
    if isinstance(data, dict):
        preview = {}
        for k, v in data.items():
            if isinstance(v, str) and len(v) > max_length:
                preview[k] = f"[{len(v)} chars]"
            else:
                preview[k] = v
        return preview
    elif isinstance(data, list):
        return [payload_preview(item, max_length) if isinstance(item, dict) else item for item in data[:5]]
    elif isinstance(data, str) and len(data) > max_length:
        return f"[{len(data)} chars]"
    else:
        return data

class StorageManager:
    def __init__(self, mqtt_client):
        self.client    = mqtt_client
        self.flask_app = getattr(mqtt_client, "_userdata", None)
        self._install_subscriptions()

        # Start the heartbeat poller in a background thread
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def _install_subscriptions(self):
        """
        Subscribe to storage-related topics for all devices, e.g.:
        cameras/abc123/file/image/create
        """
        with self.flask_app.app_context():
            for dev in Device.query.filter_by(enabled=True).all():
                # skip any device missing its topic prefix or client ID
                if not dev.topic_prefix or not dev.mqtt_client_id:
                    self.flask_app.logger.info(
                        f"[StorageManager] Skipping device {dev.id} "
                        f"(prefix={dev.topic_prefix!r}, client_id={dev.mqtt_client_id!r})"
                    )
                    continue

                base  = f"{dev.topic_prefix}/{dev.mqtt_client_id}"
                topic = f"{base}/file/+/create"
                self.flask_app.logger.info(f"[StorageManager] Subscribing to {topic}")
                self.client.subscribe(topic)
                self.client.message_callback_add(topic, self.on_create)

    def on_create(self, client, userdata, msg):
        """
        Handle incoming file create requests:
        - decode JSON
        - decode base64 payload
        - determine destination folder by file extension
        - normalize base path
        - save to disk
        - publish confirmation
        """

        # Parse topic and extract device ID
        prefix, client_id, _ = msg.topic.split("/", 2)

        try:
            data = json.loads(msg.payload.decode())
            preview = payload_preview(data)
            self.flask_app.logger.info(f"[StorageManager] MQTT← {msg.topic} → Preview: {preview}")

            file_b64 = data.get("file")
            ext = data.get("ext", "bin").lower().strip(".")
            self.flask_app.logger.info(f"[StorageManager] File extension: {ext}")
            name = data.get("name", f"file_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}")

            if not file_b64:
                self.flask_app.logger.error("[StorageManager] Missing file payload in request")
                return

            # Decide folder based on file extension
            image_exts = {"jpg", "jpeg", "png", "gif", "bmp", "webp"}
            pdf_exts = {"pdf"}

            if ext in image_exts:
                folder = "images"
            elif ext in pdf_exts:
                folder = "pdfs"
            else:
                folder = "others"

            # Build relative path (e.g. images/some/path or just images/)
            relpath = os.path.join(folder, data.get("path", "")) if data.get("path") else folder

            self.flask_app.logger.info(f"[StorageManager] Relative path: {relpath}")

            # Decode base64 file content
            content = base64.b64decode(file_b64)

            with self.flask_app.app_context():
                dev = Device.query.filter_by(mqtt_client_id=client_id).first()
                if not dev:
                    self.flask_app.logger.error(f"No device found for client_id={client_id}")
                    return

                self.flask_app.logger.info(f"Device Parameters: {dev.parameters}")
                self.flask_app.logger.info(f"Device Model: {dev.model.name}")

                # Get and normalize base path
                raw_base = dev.parameters.get("base_path", "tmp").strip("/")

                # If model is "Local storage", prepend /app/storage
                if dev.model and dev.model.name.lower() == "local storage":
                    base_path = os.path.normpath(os.path.join("/app/storage", raw_base))
                else:
                    base_path = os.path.normpath(f"/{raw_base}")

                # Final full path and file write
                full_dir = os.path.join(base_path, relpath)
                self.flask_app.logger.info(f"[StorageManager] Full directory: {full_dir}")
                os.makedirs(full_dir, exist_ok=True)

                filename = f"{name}.{ext}"
                full_path = os.path.join(full_dir, filename)

                with open(full_path, "wb") as f:
                    f.write(content)

                # publish the “success” enum on file/created
                result_topic = f"{prefix}/{client_id}/file/created"
                # since our schema’s type is “enum” of strings, just send the JSON string literal
                self.client.publish(result_topic, json.dumps("success"))
                self.flask_app.logger.info(f"[StorageManager] Published success to {result_topic}")

                # Publish file confirmation
                topic_out = f"{prefix}/{client_id}/file/new"
                rel_file = os.path.relpath(full_path, base_path)
                payload = json.dumps({"path": rel_file})
                self.client.publish(topic_out, payload)
                self.flask_app.logger.info(f"[StorageManager] Saved file to {full_path}")

                # Log event
                log_topic = f"{prefix}/{client_id}/log"
                log = {
                    "event": "file_saved",
                    "filename": filename,
                    "path": rel_file,
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.client.publish(log_topic, json.dumps(log))

        except Exception as e:
            self.flask_app.logger.error(f"[StorageManager] file/create failed: {e}")

            # tell the UI “error” so your EVALUATE → On Error branch will fire
            result_topic = f"{prefix}/{client_id}/file/created"
            self.client.publish(result_topic, json.dumps("error"))

    def _poll_loop(self):
        """
        Emit a heartbeat every 5 seconds for each enabled device.
        """
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

    def handle_message(self, dev_id, topic, payload):
        # Unused: routing is handled by message_callback_add
        pass


# ─── Singleton wrapper ─────────────────────────────────────────────

_manager = None

def init_storage_manager(mqtt_client, status_interval=None):
    global _manager
    _manager = StorageManager(mqtt_client)

def get_storage_manager():
    return _manager

import os
import io
import json
import time
import base64
import ftplib
import threading
from datetime import datetime

try:
    import paramiko          # SFTP support
except ImportError:
    paramiko = None

from flask import current_app as app
from extensions import db
from models.device import Device

from controllers.queues        import STORAGE_Q
from controllers.queue_consumer import QueueConsumerMixin   # new helper


# ───────────────────────────── Helpers ────────────────────────────────
def payload_preview(data, max_len: int = 100):
    if isinstance(data, dict):
        return {
            k: (f"[{len(v)} chars]" if isinstance(v, str) and len(v) > max_len else v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [
            payload_preview(i, max_len) if isinstance(i, dict) else i
            for i in data[:5]
        ]
    if isinstance(data, str) and len(data) > max_len:
        return f"[{len(data)} chars]"
    return data


class _FTP(ftplib.FTP):
    """ftplib that logs via Flask logger instead of print()."""
    def __init__(self, logger, *a, **kw):
        self._logger = logger
        super().__init__(*a, **kw)

    # python 3.12 removed the internal prints; we still override for safety
    def _print_debug(self, *msgs):
        self._logger.debug("[FTP dbg] %s", " ".join(str(m) for m in msgs))


# ────────────────────────── StorageManager ────────────────────────────
class StorageManager(QueueConsumerMixin):
    """
    Consumes messages from STORAGE_Q.  Each payload is expected to be the
    same as the old “…/file/…/create” MQTT message.  No direct broker
    subscriptions remain – relevance is tested via `_is_relevant()`.
    """
    _queue     = STORAGE_Q
    _tag       = "💾"
    _n_threads = 4

    # ------------------------------------------------------------------
    # life-cycle
    # ------------------------------------------------------------------
    def __init__(self, mqtt_client):
        self.client    = mqtt_client
        self.flask_app = getattr(mqtt_client, "_userdata", None)

        # start the queue consumer
        self._start_consumer()

        # background heartbeat loop
        threading.Thread(
            target=self._poll_loop,
            name="StorageManager-Heartbeat",
            daemon=True
        ).start()

    # ------------------------------------------------------------------
    # QueueConsumerMixin requirements
    # ------------------------------------------------------------------
    def _is_relevant(self, topic: str) -> bool:
        """
        Cheap test before we dequeue: message must contain '/file/' and
        end with '/create'.
        """
        return topic.endswith("/create") and "/file/" in topic

    def _process(self, _dev_id: int, topic: str, payload: str):
        """Parse the JSON payload exactly like the old on_create()."""
        # split once: <prefix>/<client_id>/file/.../create
        prefix, client_id, _ = topic.split("/", 2)
        self._handle_create(prefix, client_id, topic, payload)

    # ------------------------------------------------------------------
    # main upload handler (refactored from old on_create)
    # ------------------------------------------------------------------
    def _handle_create(self, prefix: str, client_id: str,
                       full_topic: str, raw_payload: str):
        try:
            data = json.loads(raw_payload)
            self.flask_app.logger.info(
                "💾 MQTT← %s → %s", full_topic, payload_preview(data)
            )

            file_b64 = data.get("file")
            ext      = data.get("ext", "bin").lower().strip(".")
            name     = data.get(
                "name", f"file_{datetime.now():%Y-%m-%d_%H-%M-%S}"
            )
            if not file_b64:
                raise ValueError("missing base64 file payload")

            folder = (
                "images" if ext in {"jpg", "jpeg", "png", "gif", "bmp", "webp"}
                else "pdfs" if ext == "pdf" else "others"
            )
            relpath = (
                os.path.join(folder, data.get("path", ""))
                if data.get("path") else folder
            )
            content = base64.b64decode(file_b64)

            # —— look up Device to decide storage backend ————————
            with self.flask_app.app_context():
                dev = Device.query.filter_by(mqtt_client_id=client_id).first()
                if not dev:
                    raise RuntimeError(f"no Device row for client_id={client_id}")

                model  = (dev.model.name or "").lower()
                params = dev.parameters
                self.flask_app.logger.info(
                    "Device Model: %s | Params: %s", model, params
                )

                if model == "local storage":
                    self._save_local(params, relpath, name, ext, content)
                    rel_for_payload = os.path.join(relpath, f"{name}.{ext}")

                elif model == "ftp / sftp storage":
                    rel_for_payload = self._save_remote(
                        params, relpath, name, ext, content
                    )

                else:
                    raise RuntimeError(f"unsupported storage model '{model}'")

                # publish success / log
                self._publish_success(prefix, client_id, rel_for_payload)

        except Exception as exc:
            self.flask_app.logger.error("💾 file/create failed: %s", exc)
            self.client.publish(
                f"{prefix}/{client_id}/file/created", json.dumps("error")
            )

    # ------------------------------------------------------------------
    # local disk
    # ------------------------------------------------------------------
    def _save_local(self, params, relpath, name, ext, content):
        raw_base  = params.get("base_path", "tmp").lstrip("/")
        base_path = os.path.normpath(os.path.join("/app/storage", raw_base))
        full_dir  = os.path.join(base_path, relpath)
        os.makedirs(full_dir, exist_ok=True)

        file_path = os.path.join(full_dir, f"{name}.{ext}")
        with open(file_path, "wb") as fh:
            fh.write(content)
        self.flask_app.logger.info("💾 local save → %s", file_path)

    # ------------------------------------------------------------------
    # remote dispatcher
    # ------------------------------------------------------------------
    def _save_remote(self, params, relpath, name, ext, content):
        proto   = params.get("protocol", "ftp").lower()
        host    = params["host"]
        port    = params.get("port", 21 if proto == "ftp" else 22)
        user    = params.get("username")
        pw      = params.get("password")
        root    = params.get("root_path", "/").rstrip("/")
        passive = params.get("passive_mode", True)

        remote_rel  = os.path.join(relpath, f"{name}.{ext}").replace("\\", "/")
        remote_full = remote_rel  # no double-root

        if proto == "ftp":
            return self._ftp_store(
                host, port, user, pw, passive, params.get("ssl", False),
                root, remote_rel, remote_full, content
            )
        if proto == "sftp":
            return self._sftp_store(
                host, port, user, pw, root, remote_rel, remote_full, content
            )
        raise RuntimeError(f"unknown protocol '{proto}'")

    # ------------------------------------------------------------------ FTP
    def _ftp_store(self, host, port, user, pw, passive,
                   use_ssl, root_path, remote_rel, remote_full, content):
        log = self.flask_app.logger
        ftp = _FTP(log)
        ftp.set_debuglevel(2)
        log.debug("[FTP] connect %s:%s ssl=%s user=%s", host, port, use_ssl, user)
        ftp.connect(host, port, timeout=30)
        ftp.login(user, pw)
        ftp.set_pasv(passive)
        log.debug("[FTP] Logged in. PWD=%s", ftp.pwd())

        if root_path and root_path != "/":
            try:
                ftp.cwd(root_path)
            except ftplib.error_perm:
                self._ftp_mkdirs(ftp, root_path.lstrip("/"))
                ftp.cwd(root_path)

        self._ftp_mkdirs(ftp, os.path.dirname(remote_rel))
        log.debug("[FTP] STOR %s", remote_full)
        ftp.storbinary(f"STOR {os.path.basename(remote_full)}", io.BytesIO(content))
        ftp.quit()
        return remote_rel

    def _ftp_mkdirs(self, ftp, path):
        for part in path.strip("/").split("/"):
            if not part:
                continue
            try:
                ftp.mkd(part)
            except ftplib.error_perm:
                pass
            ftp.cwd(part)

    # ----------------------------------------------------------------- SFTP
    def _sftp_store(self, host, port, user, pw,
                    root_path, remote_rel, remote_full, content):
        if not paramiko:
            raise RuntimeError("paramiko missing → install for SFTP")

        log = self.flask_app.logger
        transport = paramiko.Transport((host, port))
        transport.connect(username=user, password=pw)
        sftp = paramiko.SFTPClient.from_transport(transport)

        rel_root = root_path.lstrip("/")
        self._sftp_mkdirs(sftp, rel_root)
        sftp.chdir(rel_root)

        self._sftp_mkdirs(sftp, os.path.dirname(remote_full))
        with sftp.open(remote_full, "wb") as fh:
            fh.write(content)

        sftp.close()
        transport.close()
        return remote_rel

    def _sftp_mkdirs(self, sftp, path):
        cwd = ""
        for part in path.strip("/").split("/"):
            cwd = f"{cwd}/{part}" if cwd else part
            try:
                sftp.mkdir(cwd)
            except IOError:
                pass

    # ------------------------------------------------------------------ success / logs
    def _publish_success(self, prefix, client_id, rel_file):
        res_topic = f"{prefix}/{client_id}/file/created"
        self.client.publish(res_topic, json.dumps("success"))
        self.flask_app.logger.info("💾 Published success → %s", res_topic)

        self.client.publish(f"{prefix}/{client_id}/file/new",
                            json.dumps({"path": rel_file}))
        self.client.publish(f"{prefix}/{client_id}/log",
                            json.dumps({
                                "event":     "file_saved",
                                "path":      rel_file,
                                "timestamp": datetime.utcnow().isoformat()
                            }))

    # ------------------------------------------------------------------ heartbeat loop
    def _poll_loop(self):
        while True:
            ts = datetime.utcnow().isoformat()
            with self.flask_app.app_context():
                for d in Device.query.filter_by(enabled=True).all():
                    self.client.publish(
                        f"{d.topic_prefix}/{d.mqtt_client_id}/log",
                        json.dumps({
                            "event":     "heartbeat",
                            "device_id": d.id,
                            "timestamp": ts
                        })
                    )
            time.sleep(5)


# ───────────────────────── singleton helpers ──────────────────────────
_manager = None


def init_storage_manager(mqtt_client, **_ignored):
    """
    Factory called from app; any status_interval kwarg is ignored.
    """
    global _manager
    _manager = StorageManager(mqtt_client)
    return _manager


def get_storage_manager():
    return _manager

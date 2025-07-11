# controllers/storage_handler.py
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


# ─────────────────────────── Helpers ──────────────────────────────
def payload_preview(data, max_len=100):
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

    def _print_debug(self, *msgs):
        self._logger.debug("[FTP dbg] %s", " ".join(str(m) for m in msgs))


# ───────────────────────── StorageManager ─────────────────────────
class StorageManager:
    def __init__(self, mqtt_client):
        self.client = mqtt_client
        self.flask_app = getattr(mqtt_client, "_userdata", None)
        self._install_subscriptions()
        threading.Thread(target=self._poll_loop, daemon=True).start()

    # ---------------------------------------------------------------
    # MQTT subscription setup
    # ---------------------------------------------------------------
    def _install_subscriptions(self):
        with self.flask_app.app_context():
            for dev in Device.query.filter_by(enabled=True).all():
                if not dev.topic_prefix or not dev.mqtt_client_id:
                    continue
                topic = f"{dev.topic_prefix}/{dev.mqtt_client_id}/file/+/create"
                self.client.subscribe(topic)
                self.client.message_callback_add(topic, self.on_create)

    # ---------------------------------------------------------------
    # on_create – handles file uploads
    # ---------------------------------------------------------------
    def on_create(self, client, userdata, msg):
        prefix, client_id, _ = msg.topic.split("/", 2)

        try:
            data = json.loads(msg.payload.decode())
            self.flask_app.logger.info(
                "[StorageManager] MQTT← %s → %s", msg.topic, payload_preview(data)
            )

            file_b64 = data.get("file")
            ext      = data.get("ext", "bin").lower().strip(".")
            name     = data.get("name", f"file_{datetime.now():%Y-%m-%d_%H-%M-%S}")
            if not file_b64:
                raise ValueError("missing file payload")

            folder  = (
                "images" if ext in {"jpg", "jpeg", "png", "gif", "bmp", "webp"}
                else "pdfs" if ext == "pdf" else "others"
            )
            relpath = os.path.join(folder, data.get("path", "")) if data.get("path") else folder
            content = base64.b64decode(file_b64)

            # ── look up Device + dispatch ───────────────────────────
            with self.flask_app.app_context():
                dev = Device.query.filter_by(mqtt_client_id=client_id).first()
                if not dev:
                    raise RuntimeError(f"no Device for client_id={client_id}")

                model  = (dev.model.name or "").lower()
                params = dev.parameters
                self.flask_app.logger.info("Device Model: %s | Params: %s", model, params)

                if model == "local storage":
                    self._save_local(params, relpath, name, ext, content)
                    rel_for_payload = os.path.join(relpath, f"{name}.{ext}")

                elif model == "ftp / sftp storage":
                    self.flask_app.logger.debug("[StorageManager] Remote store params: %s", params)
                    rel_for_payload = self._save_remote(params, relpath, name, ext, content)

                else:
                    raise RuntimeError(f"unsupported storage model: {model}")

                self._publish_success(prefix, client_id, rel_for_payload)

        except Exception as exc:
            self.flask_app.logger.error("[StorageManager] file/create failed: %s", exc)
            self.client.publish(f"{prefix}/{client_id}/file/created", json.dumps("error"))

    # ─────────────────────────── Local disk ─────────────────────────
    def _save_local(self, params, relpath, name, ext, content):
        raw_base  = params.get("base_path", "tmp").lstrip("/")
        base_path = os.path.normpath(os.path.join("/app/storage", raw_base))
        full_dir  = os.path.join(base_path, relpath)
        os.makedirs(full_dir, exist_ok=True)

        file_path = os.path.join(full_dir, f"{name}.{ext}")
        with open(file_path, "wb") as fh:
            fh.write(content)
        self.flask_app.logger.info("[StorageManager] local save → %s", file_path)

    # ──────────────────────── FTP / SFTP dispatcher ─────────────────
    def _save_remote(self, params, relpath, name, ext, content):
        proto   = params.get("protocol", "ftp").lower()
        host    = params["host"]
        port    = params.get("port", 21 if proto == "ftp" else 22)
        user    = params.get("username")
        pw      = params.get("password")
        root    = params.get("root_path", "/").rstrip("/")
        passive = params.get("passive_mode", True)
        use_ssl = params.get("ssl", False)

        remote_rel  = os.path.join(relpath, f"{name}.{ext}").replace("\\", "/")
        remote_full = remote_rel  # ← no duplicate root path

        if proto == "ftp":
            return self._ftp_store(
                host, port, user, pw, passive, use_ssl, root,
                remote_rel, remote_full, content
            )
        if proto == "sftp":
            return self._sftp_store(
                host, port, user, pw, root, remote_rel, remote_full, content
            )
        raise RuntimeError(f"unknown protocol {proto}")

    # --------------------------------------------------------------- FTP
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
                log.debug("[FTP] CWD %s", root_path)
                ftp.cwd(root_path)
            except ftplib.error_perm:
                self._ftp_mkdirs(ftp, root_path.lstrip("/"))
                ftp.cwd(root_path)
        log.debug("[FTP] After root cwd. PWD=%s", ftp.pwd())

        self._ftp_mkdirs(ftp, os.path.dirname(remote_rel))
        log.debug("[FTP] STOR %s -> %s", remote_full, ftp.pwd())
        ftp.storbinary(f"STOR {os.path.basename(remote_full)}", io.BytesIO(content))
        log.debug("[FTP] Stored file %s", remote_full)
        ftp.quit()
        return remote_rel

    # -------------------------------------------------------------- SFTP
    def _sftp_store(self, host, port, user, pw,
                    root_path, remote_rel, remote_full, content):
        """
        Upload `content` to an SFTP server under `root_path` (relative to the user's home),
        creating any needed directories along the way.
        """
        if not paramiko:
            raise RuntimeError("paramiko missing – install for SFTP")
        log = self.flask_app.logger

        # Connect & authenticate
        log.debug("[SFTP] connect %s:%s user=%s", host, port, user)
        t = paramiko.Transport((host, port))
        t.connect(username=user, password=pw)
        sftp = paramiko.SFTPClient.from_transport(t)

        # Record initial working directory (may be None)
        try:
            cwd = sftp.getcwd()
        except IOError:
            cwd = None
        log.debug("[SFTP] Connected. initial cwd=%s", cwd)

        # ── Ensure root_path exists _relative_ to the SFTP home ───────────────────
        rel_root = root_path.lstrip("/")                  # e.g. "factory-lens"
        log.debug("[SFTP] Ensuring root_path exists (relative): %s", rel_root)
        self._sftp_mkdirs(sftp, rel_root)
        try:
            sftp.chdir(rel_root)
            log.debug("[SFTP] After root chdir. cwd=%s", sftp.getcwd())
        except Exception as e:
            log.error("[SFTP] Failed to chdir to %s: %s", rel_root, e)
            raise

        # ── Ensure the target subdirectory exists ────────────────────────────────
        target_dir = os.path.dirname(remote_full)
        log.debug("[SFTP] Ensuring remote directory for file exists: %s", target_dir)
        self._sftp_mkdirs(sftp, target_dir)
        try:
            log.debug("[SFTP] After target mkdirs/chdir. cwd=%s", sftp.getcwd())
        except Exception:
            pass

        # ── List directory contents before writing, for debugging ───────────────
        try:
            listing = sftp.listdir()
            log.debug("[SFTP] Directory listing before write: %s", listing)
        except Exception as e:
            log.warning("[SFTP] Could not list directory: %s", e)

        # ── Write the file content ───────────────────────────────────────────────
        log.debug("[SFTP] STOR %s (remote_full=%s)", os.path.basename(remote_full), remote_full)
        try:
            with sftp.open(remote_full, "wb") as fh:
                fh.write(content)
            log.debug("[SFTP] Write completed successfully")
        except Exception as e:
            log.error("[SFTP] Failed to write %s: %s", remote_full, e)
            raise

        # ── Final sanity check ──────────────────────────────────────────────────
        try:
            final_cwd = sftp.getcwd()
            final_list = sftp.listdir()
            log.debug("[SFTP] After write. cwd=%s, contents=%s", final_cwd, final_list)
        except Exception as e:
            log.warning("[SFTP] Could not verify after write: %s", e)

        # Close connections
        sftp.close()
        t.close()

        # Return the path relative to the MQTT payload expectations
        return remote_rel


    def _sftp_mkdirs(self, sftp, path):
        cwd = ""
        for part in path.strip("/").split("/"):
            cwd = f"{cwd}/{part}" if cwd else part
            try:
                sftp.mkdir(cwd)
            except IOError:
                pass

    # -------------------------------------------------------- success msg
    def _publish_success(self, prefix, client_id, rel_file):
        res_topic = f"{prefix}/{client_id}/file/created"
        self.client.publish(res_topic, json.dumps("success"))
        self.flask_app.logger.info("[StorageManager] Published success → %s", res_topic)

        self.client.publish(
            f"{prefix}/{client_id}/file/new",
            json.dumps({"path": rel_file}),
        )
        self.client.publish(
            f"{prefix}/{client_id}/log",
            json.dumps(
                {"event": "file_saved", "path": rel_file,
                 "timestamp": datetime.utcnow().isoformat()}
            ),
        )

    # ----------------------------------------------------------- heartbeat
    def _poll_loop(self):
        while True:
            ts = datetime.utcnow().isoformat()
            with self.flask_app.app_context():
                for d in Device.query.filter_by(enabled=True).all():
                    self.client.publish(
                        f"{d.topic_prefix}/{d.mqtt_client_id}/log",
                        json.dumps({"event": "heartbeat",
                                    "device_id": d.id,
                                    "timestamp": ts}),
                    )
            time.sleep(5)

    def handle_message(self, *_):
        pass


# ───────── Singleton helpers ─────────
_manager = None


def init_storage_manager(mqtt_client, status_interval=None, **_ignored):
    """
    Factory-lens calls this with a keyword arg `status_interval`.
    We don’t use it, but we must accept it to avoid a TypeError.
    """
    global _manager
    _manager = StorageManager(mqtt_client)


def get_storage_manager():
    return _manager

# controllers/camera_handler.py

import io
import json
import base64
import time
import threading
import subprocess
import requests
from datetime import datetime, timedelta
from requests.auth import HTTPDigestAuth, HTTPBasicAuth
import urllib.parse as urlparse

from flask import current_app
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from extensions import db
from models.device import Device
from models.camera import Camera

# ─── Constants ────────────────────────────────────────────────────────────

_UNIT_MULTIPLIERS = {
    'ms':    0.001,
    'sec':   1,
    'min':   60,
    'hour':  3600,
    'day':   86400,
}

# ─── Helpers ─────────────────────────────────────────────────────────────

def _ffmpeg_snapshot(rtsp_url: str, timeout: float = 5.0) -> bytes:
    """
    Grab one JPEG frame from RTSP via ffmpeg.
    Returns raw JPEG bytes or raises on timeout/error.
    """
    # log via Flask app logger
    flask_app = current_app._get_current_object()
    flask_app.logger.debug(f"[CameraManager] FFmpeg fetching frame from {rtsp_url}")

    cmd = [
        'ffmpeg', '-nostdin', '-rtsp_transport', 'tcp',
        '-probesize', '32', '-analyzeduration', '0',
        '-i', rtsp_url,
        '-frames:v', '1', '-q:v', '2',
        '-f', 'image2', 'pipe:1'
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    data, _ = proc.communicate(timeout=timeout)
    flask_app.logger.info(f"[CameraManager] FFmpeg snapshot size={len(data)} bytes")
    return data

def _to_pdf(jpeg_bytes: bytes) -> bytes:
    """
    Embed a JPEG into a single-page PDF.
    Returns raw PDF bytes.
    """
    flask_app = current_app._get_current_object()
    flask_app.logger.info(f"[CameraManager] Converting JPEG of size={len(jpeg_bytes)} to PDF")

    buf_in  = io.BytesIO(jpeg_bytes)
    img     = ImageReader(buf_in)
    w, h    = img.getSize()
    buf_out = io.BytesIO()
    c = canvas.Canvas(buf_out, pagesize=(w, h))
    c.drawImage(img, 0, 0, width=w, height=h)
    c.showPage()
    c.save()

    pdf_bytes = buf_out.getvalue()
    flask_app.logger.info(f"[CameraManager] PDF conversion size={len(pdf_bytes)} bytes")
    return pdf_bytes

# ─── CameraManager ──────────────────────────────────────────────────────

class CameraManager:
    """
    Coordinates camera snapshots and periodic health checks.

    Responsibilities
    ----------------
    • Subscribes to every “…/snapshot/exe” topic (per-camera + wildcard)
    • Handles snapshot commands (HTTP still-image or RTSP frame via ffmpeg)
    • Publishes JPEG/PDF back on “…/snapshot” and logs to “…/log”
    • Emits heartbeat / status for each camera in a poll loop
    • Automatically re-installs all subscriptions after an MQTT reconnect
    """

    # ─────────────────────────── initialisation ──────────────────────────
    def __init__(self, mqtt_client):
        self.client     = mqtt_client
        self.flask_app  = getattr(mqtt_client, "_userdata", None)

        # remember every topic we subscribe to so we can re-subscribe later
        self._topics: set[str] = set()

        # patch (chain) the broker’s on_connect so reconnects re-subscribe us
        prev_on_connect = mqtt_client.on_connect

        def _on_connect(client, userdata, flags, rc, properties=None):
            if prev_on_connect:
                prev_on_connect(client, userdata, flags, rc, properties)
            # after any reconnect, re-install all camera subscriptions
            self._install_subscriptions()

        mqtt_client.on_connect = _on_connect

        # first (initial) subscription install
        self._install_subscriptions()

        # start background poll loop
        threading.Thread(
            target=self._poll_loop,
            name="CameraManager-Poll",
            daemon=True
        ).start()

    # ───────────────────── subscription helpers ─────────────────────────
    def _install_subscriptions(self):
        """
        Subscribe to every enabled device’s snapshot/exe topic *once*, plus a
        wildcard fallback.  Safe to call repeatedly (duplicates are skipped).
        """
        with self.flask_app.app_context():
            # 1) per-device topics
            for dev in Device.query.filter_by(enabled=True).all():
                topic = f"{dev.topic_prefix}/{dev.mqtt_client_id}/snapshot/exe"
                if topic not in self._topics:
                    self.client.subscribe(topic)
                    self.client.message_callback_add(topic, self.on_snapshot)
                    self._topics.add(topic)
                    self.flask_app.logger.info(
                        f"[CameraManager] ↪ subscribed to {topic} (device {dev.id})"
                    )

            # 2) wildcard fallback
            wildcard = "cameras/+/snapshot/exe"
            if wildcard not in self._topics:
                self.client.subscribe(wildcard)
                self.client.message_callback_add(wildcard, self.on_snapshot)
                self._topics.add(wildcard)
                self.flask_app.logger.info(
                    f"[CameraManager] ↪ subscribed to {wildcard} (wildcard)"
                )

    # ───────────────────────── snapshot entrypoint ──────────────────────
    def on_snapshot(self, client, userdata, msg):
        """
        MQTT callback registered for every “…/snapshot/exe” topic.
        Spawns a worker thread so we never block the broker loop.
        """
        fmt = msg.payload.decode().strip().lower()
        self.flask_app.logger.info(
            f"[CameraManager] 📥 on_snapshot  topic={msg.topic}  payload={fmt!r}"
        )

        threading.Thread(
            target=self._handle_snapshot,
            args=(msg.topic, fmt),
            name="CameraManager-Snapshot",
            daemon=True
        ).start()

    # ───────────────────────── actual snapshot worker ───────────────────
    def _handle_snapshot(self, topic: str, fmt: str):
        banner = "═" * 60
        self.flask_app.logger.info(
            f"\n{banner}\n[CameraManager] 🔔 START snapshot → {topic}\n{banner}"
        )

        prefix, client_id, _ = topic.split("/", 2)
        want_pdf = (fmt == "pdf")

        with self.flask_app.app_context():
            # ── locate rows in DB ───────────────────────────────
            dev = Device.query.filter_by(
                topic_prefix=prefix, mqtt_client_id=client_id
            ).first()
            if not dev:
                self.flask_app.logger.error(f"No Device for {prefix}/{client_id}")
                return

            cam = Camera.query.filter_by(device_id=dev.id).first()
            if not cam:
                self.flask_app.logger.error(f"No Camera for Device {dev.id}")
                return
            self.flask_app.logger.debug("Device=%s  Camera=%s", dev.id, cam.id)

            # ── decide which URL (HTTP or RTSP) ─────────────────
            if cam.snapshot_url:
                input_url     = cam.snapshot_url
                input_is_http = input_url.lower().startswith(("http://", "https://"))
                self.flask_app.logger.info(f"Using HTTP URL: {input_url}")
            else:
                stream = (
                    cam.default_stream
                    or next((s for s in cam.streams if s.stream_type == "sub"), None)
                    or next((s for s in cam.streams if s.stream_type == "main"), None)
                )
                if not stream:
                    self.flask_app.logger.error(f"No stream for camera {cam.id}")
                    return
                input_url     = stream.full_url or stream.get_full_url(include_auth=True)
                input_is_http = False
                self.flask_app.logger.info(f"Using RTSP URL: {input_url}")

            # ── fetch JPEG frame ────────────────────────────────
            try:
                if input_is_http:
                    # optional HTTP-Digest → Basic fallback
                    auth = (
                        HTTPDigestAuth(cam.username, cam.password)
                        if cam.username and cam.password else None
                    )
                    verify = True
                    parsed = urlparse.urlparse(input_url)
                    if "insecure=1" in parsed.query.lower() or parsed.scheme == "http":
                        verify = False

                    self.flask_app.logger.debug(
                        f"HTTP GET {input_url} (auth={'Digest' if auth else 'None'}, "
                        f"verify={verify})"
                    )
                    resp = requests.get(input_url, auth=auth, timeout=5, verify=verify)
                    if resp.status_code == 401 and auth:
                        self.flask_app.logger.debug("Digest 401; retrying Basic")
                        resp = requests.get(
                            input_url,
                            auth=HTTPBasicAuth(cam.username, cam.password),
                            timeout=5,
                            verify=verify
                        )
                    resp.raise_for_status()
                    jpg = resp.content
                    self.flask_app.logger.info(
                        f"HTTP snapshot OK status={resp.status_code} bytes={len(jpg)}"
                    )
                else:
                    jpg = _ffmpeg_snapshot(input_url)

            except Exception as exc:
                self.flask_app.logger.error(f"Snapshot failed for cam {cam.id}: {exc}")
                return

            # ── convert to PDF if requested ─────────────────────
            if want_pdf:
                out, ext = _to_pdf(jpg), "pdf"
            else:
                out, ext = jpg, "jpg"

            # ── publish snapshot payload ────────────────────────
            b64       = base64.b64encode(out).decode()
            topic_out = f"{prefix}/{client_id}/snapshot"
            payload   = json.dumps({"ext": ext, "file": b64})
            self.client.publish(topic_out, payload)
            self.flask_app.logger.info(
                f"MQTT→ {topic_out} ext={ext} size={len(b64)} chars"
            )

            # ── audit log topic ─────────────────────────────────
            log_topic = f"{prefix}/{client_id}/log"
            self.client.publish(
                log_topic,
                json.dumps(
                    {
                        "event": "snapshot",
                        "camera_id": cam.id,
                        "ext": ext,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
            )

        # done
        self.flask_app.logger.info(
            f"[CameraManager] ✅ DONE snapshot → {topic}\n{banner}"
        )

    # ───────────────────────── MQTT injection helper ────────────────────
    def handle_message(self, device_id: int, topic: str, payload: str):
        """
        Called from mqtt.py so Actions can inject messages as if they came
        from the broker.  Converts to a pseudo-Paho message object.
        """
        self.flask_app.logger.debug(
            "[CameraManager] handle_message(dev=%s, topic=%s, payload=%r)",
            device_id, topic, payload
        )
        if topic.endswith("/snapshot/exe") and payload.lower() in ("jpg", "pdf"):
            class _Msg: pass
            msg = _Msg()
            msg.topic   = topic
            msg.payload = payload.encode()
            self.on_snapshot(self.client, None, msg)

    # ───────────────────────── periodic health poll ─────────────────────
    def _poll_loop(self):
        """
        Every second (configurable), probe each camera to update its .status
        and publish a heartbeat / status record to MQTT.
        """
        while True:
            now = datetime.utcnow()
            with self.flask_app.app_context():
                for dev in Device.query.filter_by(enabled=True).all():
                    unit     = dev.poll_interval_unit or "sec"
                    interval = dev.poll_interval or 60
                    delta    = timedelta(seconds=interval * _UNIT_MULTIPLIERS.get(unit, 1))

                    # honour per-device poll interval
                    if dev.last_seen and dev.last_seen + delta > now:
                        continue

                    cams = Camera.query.filter_by(device_id=dev.id).all()
                    device_status = "online"

                    for cam in cams:
                        # quick synthetic “online” for HTTP snapshot_url
                        if cam.snapshot_url:
                            cam.status = "online"
                        else:
                            stream = (
                                cam.default_stream
                                or (cam.streams[0] if cam.streams else None)
                            )
                            if not stream:
                                cam.status = "error"
                                device_status = "offline"
                            else:
                                url = stream.full_url or stream.get_full_url(include_auth=True)
                                try:
                                    subprocess.check_output(
                                        [
                                            "ffprobe", "-v", "error",
                                            "-rtsp_transport", "tcp",
                                            "-timeout", "1500000",
                                            "-analyzeduration", "0",
                                            "-probesize", "32",
                                            "-i", url,
                                        ],
                                        timeout=2,
                                    )
                                    cam.status = "online"
                                except Exception:
                                    cam.status = "offline"
                                    device_status = "offline"

                        cam.last_heartbeat = now

                        # per-camera MQTT log
                        log_topic = f"{dev.topic_prefix}/{dev.mqtt_client_id}/log"
                        self.client.publish(
                            log_topic,
                            json.dumps(
                                {
                                    "event": "status",
                                    "camera_id": cam.id,
                                    "status": cam.status,
                                    "timestamp": now.isoformat(),
                                }
                            ),
                        )

                    dev.last_seen = now
                    if dev.status != device_status:
                        dev.status = device_status

                    db.session.commit()

            time.sleep(1.0)

# ─── Singleton holder ───────────────────────────────────────────────────

_manager = None

def init_camera_manager(mqtt_client, status_interval=None):
    """
    Create (or replace) the global CameraManager instance.
    """
    global _manager
    _manager = CameraManager(mqtt_client)
    return _manager

def get_camera_manager():
    return _manager

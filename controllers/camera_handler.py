import io
import json
import base64
import time
import threading
import subprocess
import requests
from datetime import datetime, timedelta

from flask import current_app as app
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
    """Grab one JPEG frame from RTSP, return its raw bytes, or raise."""
    app.logger.debug(f"[CameraManager] FFmpeg fetching frame from {rtsp_url}")
    cmd = [
        'ffmpeg', '-nostdin', '-rtsp_transport', 'tcp',
        '-probesize', '32', '-analyzeduration', '0',
        '-i', rtsp_url,
        '-frames:v', '1', '-q:v', '2',
        '-f', 'image2', 'pipe:1'
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    data, _ = proc.communicate(timeout=timeout)
    app.logger.info(f"[CameraManager] FFmpeg snapshot size={len(data)} bytes")
    return data

def _to_pdf(jpeg_bytes: bytes) -> bytes:
    """Embed a JPEG into a single‐page PDF, return PDF bytes."""
    app.logger.info(f"[CameraManager] Converting JPEG of size={len(jpeg_bytes)} to PDF")
    buf_in  = io.BytesIO(jpeg_bytes)
    img     = ImageReader(buf_in)
    w, h    = img.getSize()
    buf_out = io.BytesIO()
    c = canvas.Canvas(buf_out, pagesize=(w, h))
    c.drawImage(img, 0, 0, width=w, height=h)
    c.showPage()
    c.save()
    pdf_bytes = buf_out.getvalue()
    app.logger.info(f"[CameraManager] PDF conversion size={len(pdf_bytes)} bytes")
    return pdf_bytes

# ─── CameraManager ──────────────────────────────────────────────────────

class CameraManager:
    def __init__(self, mqtt_client):
        self.client    = mqtt_client
        self.flask_app = getattr(mqtt_client, "_userdata", None)

        # subscribe & register callbacks for snapshot commands
        self._install_subscriptions()

        # start polling loop
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def _install_subscriptions(self):
        """
        Subscribe to each camera’s single command topic: …/snapshot/exe,
        and register our callback just for that topic.
        """
        with self.flask_app.app_context():
            for dev in Device.query.filter_by(enabled=True).all():
                base    = f"{dev.topic_prefix}/{dev.mqtt_client_id}"
                topic   = f"{base}/snapshot/exe"
                self.client.subscribe(topic)
                self.client.message_callback_add(topic, self.on_snapshot)

    def on_snapshot(self, client, userdata, msg):
        """
        Only called for “…/snapshot/exe”.
        Payload is 'jpg' or 'pdf' — spin off the actual work.
        """
        fmt = msg.payload.decode().strip().lower()
        self.flask_app.logger.info(f"[CameraManager] MQTT← {msg.topic} → {fmt!r}")
        threading.Thread(
            target=self._handle_snapshot,
            args=(msg.topic, fmt),
            daemon=True
        ).start()

    def _handle_snapshot(self, topic: str, fmt: str):
        """
        Grab a frame, convert if PDF requested, then publish back on “…/snapshot”
        with JSON `{ext:…, file:…}`.
        """
        prefix, client_id, _ = topic.split('/', 2)
        want_pdf = (fmt == "pdf")

        with self.flask_app.app_context():
            dev = Device.query.filter_by(
                topic_prefix=prefix,
                mqtt_client_id=client_id
            ).first()
            if not dev:
                self.flask_app.logger.error(f"No Device for {prefix}/{client_id}")
                return

            cam = Camera.query.filter_by(device_id=dev.id).first()
            if not cam:
                self.flask_app.logger.error(f"No Camera row for Device {dev.name}")
                return

            # Determine which URL to use: HTTP snapshot_url for Reolink, else RTSP
            if cam.snapshot_url:
                input_is_http = cam.snapshot_url.lower().startswith(('http://','https://'))
                input_url = cam.snapshot_url
                self.flask_app.logger.info(f"[CameraManager] Using HTTP snapshot_url for cam {cam.id}: {input_url}")
            else:
                # fall back to RTSP streams
                stream = (
                    cam.default_stream
                    or next((s for s in cam.streams if s.stream_type=='sub'), None)
                    or next((s for s in cam.streams if s.stream_type=='main'), None)
                )
                if not stream:
                    self.flask_app.logger.error(f"No stream or snapshot URL for camera {cam.id}")
                    return
                input_url = (stream.full_url or stream.get_full_url(include_auth=True))
                input_is_http = False
                self.flask_app.logger.info(f"[CameraManager] Using RTSP URL for cam {cam.id}: {input_url}")

            # fetch JPEG
            try:
                if input_is_http:
                    self.flask_app.logger.debug(f"[CameraManager] HTTP GET snapshot_url {input_url}")
                    resp = requests.get(input_url, timeout=5)
                    resp.raise_for_status()
                    jpg = resp.content
                    self.flask_app.logger.info(f"[CameraManager] HTTP snapshot returned status={resp.status_code}, bytes={len(jpg)}")
                else:
                    jpg = _ffmpeg_snapshot(input_url)
            except Exception as e:
                self.flask_app.logger.error(f"Snapshot failed for cam {cam.id}: {e}")
                return

            # convert if PDF requested
            if want_pdf:
                out, ext = _to_pdf(jpg), 'pdf'
            else:
                out, ext = jpg, 'jpg'

            # publish result
            b64       = base64.b64encode(out).decode()
            topic_out = f"{prefix}/{client_id}/snapshot"
            payload   = json.dumps({"ext": ext, "file": b64})
            self.client.publish(topic_out, payload)
            self.flask_app.logger.info(f"[CameraManager] MQTT→ {topic_out} ext={ext} size={len(b64)} chars")

            # also log to the camera log topic
            log_topic = f"{prefix}/{client_id}/log"
            log = {
                "event":     "snapshot",
                "camera_id": cam.id,
                "ext":       ext,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.client.publish(log_topic, json.dumps(log))

    def handle_message(self, device_id: int, topic: str, payload: str):
        """
        Legacy entrypoint: feed *every* message here.
        """
        if topic.endswith("/snapshot/exe") and payload.lower() in ("jpg","pdf"):
            class Msg: pass
            msg = Msg()
            msg.topic   = topic
            msg.payload = payload.encode()
            self.on_snapshot(self.client, None, msg)

    def _poll_loop(self):
        """
        Periodically probe each camera stream to update status & heartbeat,
        commit to DB, and log status over MQTT.
        """
        while True:
            now = datetime.utcnow()
            with self.flask_app.app_context():
                for dev in Device.query.filter_by(enabled=True).all():
                    unit     = dev.poll_interval_unit or 'sec'
                    interval = dev.poll_interval or 60
                    delta    = timedelta(seconds=interval * _UNIT_MULTIPLIERS.get(unit,1))

                    if dev.last_seen and (dev.last_seen + delta) > now:
                        continue

                    cams = Camera.query.filter_by(device_id=dev.id).all()
                    device_status = 'online'

                    for cam in cams:
                        if cam.snapshot_url:
                            cam.status = 'online'
                        else:
                            stream = (
                                cam.default_stream
                                or (cam.streams[0] if cam.streams else None)
                            )
                            if not stream:
                                cam.status = 'error'
                                device_status = 'offline'
                            else:
                                url = stream.full_url or stream.get_full_url(include_auth=True)
                                try:
                                    subprocess.check_output([
                                        "ffprobe", "-v", "error",
                                        "-rtsp_transport", "tcp",
                                        "-timeout", "1500000",
                                        "-analyzeduration", "0",
                                        "-probesize", "32",
                                        "-i", url
                                    ], timeout=2)
                                    cam.status = 'online'
                                except Exception:
                                    cam.status = 'offline'
                                    device_status = 'offline'

                        cam.last_heartbeat = now

                        log_topic = f"{dev.topic_prefix}/{dev.mqtt_client_id}/log"
                        log = {
                            "event":     "status",
                            "camera_id": cam.id,
                            "status":    cam.status,
                            "timestamp": now.isoformat()
                        }
                        self.client.publish(log_topic, json.dumps(log))

                    dev.last_seen = now
                    if dev.status != device_status:
                        dev.status = device_status

                    db.session.commit()
            time.sleep(1.0)


# ─── Singleton holder ───────────────────────────────────────────────────

_manager = None

def init_camera_manager(mqtt_client, status_interval=None):
    global _manager
    _manager = CameraManager(mqtt_client)
    return _manager

def get_camera_manager():
    return _manager
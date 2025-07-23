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

from controllers.queues         import CAMERA_Q
from controllers.queue_consumer import QueueConsumerMixin


# ─── Constants ────────────────────────────────────────────────────────────
_UNIT_MULTIPLIERS = {
    "ms": 0.001,
    "sec": 1,
    "min": 60,
    "hour": 3600,
    "day": 86400,
}


# ─── Helpers ──────────────────────────────────────────────────────────────
def _ffmpeg_snapshot(rtsp_url: str, timeout: float = 5.0) -> bytes:
    """
    Grab a single JPEG frame from an RTSP stream via ffmpeg.
    Returns raw JPEG bytes or raises on timeout/error.
    """
    flask_app = current_app._get_current_object()
    flask_app.logger.debug("[CameraManager] FFmpeg fetching frame from %s", rtsp_url)

    cmd = [
        "ffmpeg", "-nostdin", "-rtsp_transport", "tcp",
        "-probesize", "32", "-analyzeduration", "0",
        "-i", rtsp_url,
        "-frames:v", "1", "-q:v", "2",
        "-f", "image2", "pipe:1"
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    data, _ = proc.communicate(timeout=timeout)
    flask_app.logger.info("[CameraManager] FFmpeg snapshot size=%d bytes", len(data))
    return data


def _to_pdf(jpeg_bytes: bytes) -> bytes:
    """
    Embed a JPEG into a single-page PDF.
    Returns raw PDF bytes.
    """
    flask_app = current_app._get_current_object()
    flask_app.logger.info(
        "[CameraManager] Converting JPEG (%d bytes) to PDF", len(jpeg_bytes)
    )

    buf_in = io.BytesIO(jpeg_bytes)
    img = ImageReader(buf_in)
    w, h = img.getSize()
    buf_out = io.BytesIO()
    c = canvas.Canvas(buf_out, pagesize=(w, h))
    c.drawImage(img, 0, 0, width=w, height=h)
    c.showPage()
    c.save()
    return buf_out.getvalue()


# ─── CameraManager ────────────────────────────────────────────────────────
class CameraManager(QueueConsumerMixin):
    """
    Consumes “…/snapshot/exe” messages from CAMERA_Q, produces snapshots,
    and runs the periodic health-check poll loop.
    """
    _queue     = CAMERA_Q
    _tag       = "📸"
    _n_threads = 4  # ffmpeg/HTTP fetches are I/O-bound

    def __init__(self, mqtt_client):
        # Store references
        self.client    = mqtt_client
        self.flask_app = getattr(mqtt_client, "_userdata", None)

        # Topic suffix used for relevance testing
        self._topic_suffix = "/snapshot/exe"

        # ── DEBUG: show what topics we’re listening to ──────────────
        self.flask_app.logger.info(
            "📸 CameraManager listens for topics ending with %r",
            self._topic_suffix
        )
        with self.flask_app.app_context():
            topics = [
                f"{d.topic_prefix}/{d.mqtt_client_id}{self._topic_suffix}"
                for d in Device.query.filter_by(enabled=True).all()
            ]
            topics.append("cameras/+/snapshot/exe")
            self.flask_app.logger.info("📸 CameraManager topics: %s", topics)

        # Kick off the queue consumer
        self._start_consumer()

        # Start the periodic health-check loop
        threading.Thread(
            target=self._poll_loop,
            name="CameraManager-Poll",
            daemon=True
        ).start()

    # ────────────────────────────────────────────────────────────────
    # QueueConsumerMixin requirements
    # ────────────────────────────────────────────────────────────────
    def _is_relevant(self, topic: str) -> bool:
        """
        A message is relevant if its topic ends with '/snapshot/exe'.
        """
        return topic.endswith(self._topic_suffix)

    def _process(self, _dev_id: int, topic: str, payload: str):
        """
        Payload is either 'jpg' or 'pdf'.  Delegate to the snapshot handler.
        """
        fmt = payload.strip().lower()
        self._handle_snapshot(topic, fmt)

    # ────────────────────────────────────────────────────────────────
    # Snapshot worker (mostly unchanged)
    # ────────────────────────────────────────────────────────────────
    def _handle_snapshot(self, topic: str, fmt: str):
        banner = "═" * 60
        self.flask_app.logger.info(
            "\n%s\n[CameraManager] 🔔 START snapshot → %s\n%s",
            banner, topic, banner
        )

        prefix, client_id, _ = topic.split("/", 2)
        want_pdf = (fmt == "pdf")

        with self.flask_app.app_context():
            # Locate Device + Camera rows
            dev = Device.query.filter_by(
                topic_prefix=prefix, mqtt_client_id=client_id
            ).first()
            if not dev:
                self.flask_app.logger.error("No Device for %s/%s", prefix, client_id)
                return

            cam = Camera.query.filter_by(device_id=dev.id).first()
            if not cam:
                self.flask_app.logger.error("No Camera for Device %s", dev.id)
                return

            # Decide input URL (HTTP vs RTSP)
            if cam.snapshot_url:
                input_url, input_is_http = cam.snapshot_url, True
                self.flask_app.logger.info("Using HTTP URL: %s", input_url)
            else:
                stream = (
                    cam.default_stream
                    or next((s for s in cam.streams if s.stream_type == "sub"), None)
                    or next((s for s in cam.streams if s.stream_type == "main"), None)
                )
                if not stream:
                    self.flask_app.logger.error("No stream for camera %s", cam.id)
                    return
                input_url = stream.full_url or stream.get_full_url(include_auth=True)
                input_is_http = False
                self.flask_app.logger.info("Using RTSP URL: %s", input_url)

            # Fetch JPEG
            try:
                if input_is_http:
                    auth = (
                        HTTPDigestAuth(cam.username, cam.password)
                        if cam.username and cam.password else None
                    )
                    verify = not ("insecure=1" in urlparse.urlparse(input_url).query.lower()
                                  or input_url.lower().startswith("http://"))
                    resp = requests.get(input_url, auth=auth, timeout=5, verify=verify)
                    if resp.status_code == 401 and auth:
                        resp = requests.get(
                            input_url,
                            auth=HTTPBasicAuth(cam.username, cam.password),
                            timeout=5,
                            verify=verify
                        )
                    resp.raise_for_status()
                    jpg = resp.content
                else:
                    jpg = _ffmpeg_snapshot(input_url)
            except Exception as exc:
                self.flask_app.logger.error("Snapshot failed for cam %s: %s", cam.id, exc)
                return

            # Optional PDF conversion
            out, ext = (_to_pdf(jpg), "pdf") if want_pdf else (jpg, "jpg")

            # Publish snapshot back to MQTT
            b64 = base64.b64encode(out).decode()
            topic_out = f"{prefix}/{client_id}/snapshot"
            self.client.publish(topic_out, json.dumps({"ext": ext, "file": b64}))
            self.flask_app.logger.info(
                "MQTT→ %s ext=%s size=%d chars", topic_out, ext, len(b64)
            )

            # Audit log
            log_topic = f"{prefix}/{client_id}/log"
            self.client.publish(log_topic, json.dumps({
                "event":     "snapshot",
                "camera_id": cam.id,
                "ext":       ext,
                "timestamp": datetime.utcnow().isoformat(),
            }))

        self.flask_app.logger.info(
            "[CameraManager] ✅ DONE snapshot → %s\n%s", topic, banner
        )

    # ────────────────────────────────────────────────────────────────
    # Periodic health-check poll loop (unchanged)
    # ────────────────────────────────────────────────────────────────
    def _poll_loop(self):
        while True:
            now = datetime.utcnow()
            with self.flask_app.app_context():
                for dev in Device.query.filter_by(enabled=True).all():
                    unit     = dev.poll_interval_unit or "sec"
                    interval = dev.poll_interval or 60
                    delta    = timedelta(seconds=interval * _UNIT_MULTIPLIERS.get(unit, 1))

                    # Respect per-device interval
                    if dev.last_seen and dev.last_seen + delta > now:
                        continue

                    cams = Camera.query.filter_by(device_id=dev.id).all()
                    device_status = "online"

                    for cam in cams:
                        # HTTP snapshot_url cameras: assume online
                        if cam.snapshot_url:
                            cam.status = "online"
                        else:
                            stream = (
                                cam.default_stream
                                or (cam.streams[0] if cam.streams else None)
                            )
                            if not stream:
                                cam.status      = "error"
                                device_status   = "offline"
                            else:
                                url = stream.full_url or stream.get_full_url(include_auth=True)
                                try:
                                    subprocess.check_output([
                                        "ffprobe", "-v", "error",
                                        "-rtsp_transport", "tcp",
                                        "-timeout", "1500000",
                                        "-analyzeduration", "0",
                                        "-probesize", "32",
                                        "-i", url,
                                    ], timeout=2)
                                    cam.status = "online"
                                except Exception:
                                    cam.status    = "offline"
                                    device_status = "offline"

                        cam.last_heartbeat = now

                        # Per-camera log
                        self.client.publish(
                            f"{dev.topic_prefix}/{dev.mqtt_client_id}/log",
                            json.dumps({
                                "event":      "status",
                                "camera_id":  cam.id,
                                "status":     cam.status,
                                "timestamp":  now.isoformat(),
                            })
                        )

                    dev.last_seen = now
                    if dev.status != device_status:
                        dev.status = device_status

                    db.session.commit()

            time.sleep(1.0)


# ─── Singleton helpers ───────────────────────────────────────────────────
_manager = None


def init_camera_manager(mqtt_client, **_ignored):
    """
    Factory called from app.py to initialize the global CameraManager.
    """
    global _manager
    _manager = CameraManager(mqtt_client)
    return _manager


def get_camera_manager():
    return _manager

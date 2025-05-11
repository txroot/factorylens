import io
import json
import base64
import time
import threading
import subprocess
from datetime import datetime, timedelta

from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from extensions import db
from models.device        import Device
from models.camera        import Camera
from models.camera_stream import CameraStream

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
    cmd = [
        'ffmpeg', '-nostdin', '-rtsp_transport', 'tcp',
        '-probesize', '32', '-analyzeduration', '0',
        '-i', rtsp_url,
        '-frames:v', '1', '-q:v', '2',
        '-f', 'image2', 'pipe:1'
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    data, _ = proc.communicate(timeout=timeout)
    return data

def _to_pdf(jpeg_bytes: bytes) -> bytes:
    buf_in  = io.BytesIO(jpeg_bytes)
    img     = ImageReader(buf_in)
    w, h    = img.getSize()
    buf_out = io.BytesIO()
    c = canvas.Canvas(buf_out, pagesize=(w, h))
    c.drawImage(img, 0, 0, width=w, height=h)
    c.showPage()
    c.save()
    return buf_out.getvalue()

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
        Subscribe to each camera’s snapshot/exe and snapshot/exe/pdf topics,
        then attach our on_snapshot() callback to those topics only.
        """
        with self.flask_app.app_context():
            for dev in Device.query.filter_by(enabled=True).all():
                base = f"{dev.topic_prefix}/{dev.mqtt_client_id}"
                for suffix in ("snapshot/exe"):
                    topic = f"{base}/{suffix}"
                    self.client.subscribe(topic)
                    # register just for this topic
                    self.client.message_callback_add(topic, self.on_snapshot)

    def on_snapshot(self, client, userdata, msg):
        """
        Called only for topics matching “…/snapshot/exe” or “…/snapshot/exe/pdf”.
        Extract the desired format from payload, then spin off the handler.
        """
        payload = msg.payload.decode().strip().lower()  # 'jpg' or 'pdf'
        self.flask_app.logger.info(f"[CameraManager] MQTT← {msg.topic} → {payload!r}")
        threading.Thread(
            target=self._handle_snapshot,
            args=(msg.topic, payload),
            daemon=True
        ).start()

    def _handle_snapshot(self, topic: str, fmt: str):
        """
        Grab a frame, convert if needed, and publish back as JSON with ext+file.
        """
        parts     = topic.split('/')
        prefix    = parts[0]
        client_id = parts[1]
        want_pdf  = (fmt == "pdf")

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

            # build snapshot URL
            stream = (
                cam.default_stream
                or next((s for s in cam.streams if s.stream_type=='sub'), None)
                or next((s for s in cam.streams if s.stream_type=='main'), None)
            )
            input_url = (stream.full_url or stream.get_full_url(include_auth=True)
                         if stream else None) or cam.snapshot_url
            if not input_url:
                self.flask_app.logger.error(f"No snapshot URL for camera {cam.id}")
                return

            # capture JPEG
            try:
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
            msg = json.dumps({"ext": ext, "file": b64})
            self.client.publish(topic_out, msg)
            self.flask_app.logger.info(
                f"[CameraManager] MQTT→ {topic_out} ext={ext} size={len(b64)}"
            )

            # also log to the camera log topic
            log_topic = f"{prefix}/{client_id}/log"
            log = {
                "event":     "snapshot",
                "camera_id": cam.id,
                "ext":       ext,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.client.publish(log_topic, json.dumps(log))

    def _poll_loop(self):
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
                        stream = (
                            cam.default_stream
                            or (cam.streams[0] if cam.streams else None)
                        )
                        if not stream:
                            cam.status = 'error'
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

# ─── Initialization ────────────────────────────────────────────────────

_manager = None

def init_camera_manager(mqtt_client, status_interval=None):
    global _manager
    _manager = CameraManager(mqtt_client)
    return _manager

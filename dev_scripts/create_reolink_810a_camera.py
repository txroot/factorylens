#!/usr/bin/env python3
"""
Create a Reolink 810A Camera + matching Device entry,
linked to the DeviceModel in the database.
Streams are created for main/sub RTSP and a snapshot URL entry in the Camera model.
"""
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import func

# Ensure project root on path
top = Path(__file__).resolve().parents[1].as_posix()
if top not in sys.path:
    sys.path.insert(0, top)

from app import create_app
from extensions import db
from models.device        import Device
from models.device_model  import DeviceModel
from models.camera        import Camera
from models.camera_stream import CameraStream

# ── Customize these to your environment ────────────────────────────────
CAMERA_NAME     = 'Factory Lens Reolink 1'
SERIAL_NUMBER   = 'REO-810A-0001'
DESCRIPTION     = 'Front-door PoE camera'
MQTT_CLIENT_ID  = 'factory-cam-001'
TOPIC_PREFIX    = 'factory/cameras/001'
LOCATION        = 'Front Door'

# Authentication and host
USERNAME        = 'admin'
PASSWORD        = 'reolink'
HOST            = '10.20.1.157'
PORT            = 554

# RTSP Stream URLs per Reolink spec
def make_rtsp_url(codec: str, channel: int, quality: str) -> str:
    """Helper to build RTSP URL for main/sub streams"""
    return f"rtsp://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{codec}Preview_{channel:02d}_{quality}"

# Snapshot URL per Reolink spec
SNAPSHOT_URL_TEMPLATE = (
    "http://{host}/cgi-bin/api.cgi?cmd=Snap&channel=0"
    "&rs=abc123&user={user}&password={pwd}&width={w}&height={h}"
)

# Stream definitions - use 'main' to match the CameraStream enum
STREAMS = [
    {
        'stream_type': 'main',
        'full_url':    make_rtsp_url(codec='h264', channel=1, quality='main'),
        'description': 'High-quality main RTSP stream'
    },
    {
        'stream_type': 'sub',
        'full_url':    make_rtsp_url(codec='h264', channel=1, quality='sub'),
        'description': 'Lower-bandwidth sub RTSP stream'
    }
]

# Snapshot resolution defaults
SNAPSHOT_WIDTH  = 1920
SNAPSHOT_HEIGHT = 1080


def main():
    app = create_app()
    with app.app_context():
        # 1) Locate Reolink model
        model = DeviceModel.query.filter(
            func.lower(DeviceModel.name) == 'reolink 810a'
        ).first()
        if not model:
            raise RuntimeError("Reolink 810A model not found. Seed the device catalog first.")

        # 2) Upsert Device row
        device = Device.query.filter_by(serial_number=SERIAL_NUMBER).first()
        if not device:
            device = Device(
                name=CAMERA_NAME,
                serial_number=SERIAL_NUMBER,
                device_model_id=model.id,
                mqtt_client_id=MQTT_CLIENT_ID,
                topic_prefix=TOPIC_PREFIX,
                location=LOCATION,
                description=DESCRIPTION,
                enabled=True,
                poll_interval=60,
                poll_interval_unit='sec',
                status='offline',
                parameters={},
                values={},
                last_response_timestamp=datetime.utcnow(),
                tags=['factory','camera','reolink'],
            )
            db.session.add(device)
            db.session.flush()
            # Avoid broken __repr__; print fields explicitly
            print(f"✅ Created Device id={device.id!r} name={device.name!r}")
        else:
            print(f"ℹ️  Device exists id={device.id!r} name={device.name!r}")

        # 3) Upsert Camera entity with snapshot URL
        cam = Camera.query.filter_by(serial_number=SERIAL_NUMBER).first()
        snapshot_url = SNAPSHOT_URL_TEMPLATE.format(
            host=HOST, user=USERNAME, pwd=PASSWORD,
            w=SNAPSHOT_WIDTH, h=SNAPSHOT_HEIGHT
        )
        if not cam:
            cam = Camera(
                name=CAMERA_NAME,
                serial_number=SERIAL_NUMBER,
                address=HOST,
                port=PORT,
                username=USERNAME,
                password=PASSWORD,
                manufacturer='Reolink',
                model='810A',
                firmware=None,
                description=DESCRIPTION,
                notes='PoE, 8 MP',
                status='offline',
                location=LOCATION,
                device_id=device.id,
                snapshot_url=snapshot_url
            )
            db.session.add(cam)
            db.session.flush()
            print(f"✅ Created Camera id={cam.id!r} name={cam.name!r}")
        else:
            if getattr(cam, 'snapshot_url', None) != snapshot_url:
                cam.snapshot_url = snapshot_url
                print("🔄 Updated camera snapshot URL")
            else:
                print(f"ℹ️  Camera exists id={cam.id!r} name={cam.name!r}")

        # 4) Upsert streams
        streams = []
        for s in STREAMS:
            existing = CameraStream.query.filter_by(
                camera_id=cam.id,
                stream_type=s['stream_type']
            ).first()
            if existing:
                if existing.full_url != s['full_url']:
                    existing.full_url = s['full_url']
                    print(f"🔄 Updated stream URL for '{s['stream_type']}'")
                else:
                    print(f"ℹ️  Stream '{s['stream_type']}' exists")
                stream = existing
            else:
                stream = CameraStream(
                    camera_id=cam.id,
                    stream_type=s['stream_type'],
                    url_prefix=None,
                    stream_suffix=None,
                    full_url=s['full_url'],
                    resolution_w=None,
                    resolution_h=None,
                    fps=None,
                    codec=None,
                    bitrate_kbps=None,
                    bitrate_type=None,
                    is_active=True,
                    description=s['description']
                )
                db.session.add(stream)
                db.session.flush()
                print(f"✅ Created stream '{s['stream_type']}'")
            streams.append(stream)

        # 5) Set default stream to 'sub'
        sub = next((st for st in streams if st.stream_type=='sub'), None)
        if sub and getattr(cam, 'default_stream_id', None) != sub.id:
            cam.default_stream_id = sub.id
            print("✅ Set default stream to 'sub'")

        db.session.commit()
        print("🎉 Reolink 810A provisioning complete.")

if __name__ == '__main__':
    main()

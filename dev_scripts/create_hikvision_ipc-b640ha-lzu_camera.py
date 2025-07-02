#!/usr/bin/env python3
# create_hikvision_ipc-b640ha-lzu_camera.py
"""
Create a Hikvision IPC-B640HA-LZU Camera + matching Device entry,
linked to the DeviceModel in the database.

• Inserts/updates a Device row
• Inserts/updates a Camera row (with Digest-auth snapshot URL)
• Adds two CameraStream rows (main/sub) and sets *sub* as default
"""
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import func

# ── project import path ─────────────────────────────────────────────────
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
CAMERA_NAME     = 'Factory Lens Hikvision 1'
SERIAL_NUMBER   = 'HIK-B640HA-0001'
DESCRIPTION     = 'Warehouse loading-dock PoE camera'
MQTT_CLIENT_ID  = 'factory-cam-031'
TOPIC_PREFIX    = 'factory/cameras/031'
LOCATION        = 'Loading Dock'

# Authentication and host
USERNAME        = 'admin'
PASSWORD        = 'FactoryLens'
HOST            = '10.20.1.31'
PORT            = 554

# ── URL helpers ────────────────────────────────────────────────────────
def make_rtsp_url(channel: int = 1, stream: str = 'main') -> str:
    """
    Hikvision mapping:
      channel 1 main ⇒ 101
      channel 1 sub  ⇒ 102
      …
    """
    if stream not in ('main', 'sub'):
        raise ValueError("stream must be 'main' or 'sub'")
    stream_suffix = '01' if stream == 'main' else '02'
    return (
        f"rtsp://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/"
        f"Streaming/Channels/{channel}{stream_suffix}"
    )

SNAPSHOT_URL_TEMPLATE = (
    "http://{host}/ISAPI/Streaming/channels/1/picture"
    # Digest auth happens client-side; plain URL is fine in DB
)

STREAMS = [
    {
        'stream_type': 'main',
        'full_url':    make_rtsp_url(stream='main'),
        'description': 'High-quality main RTSP stream'
    },
    {
        'stream_type': 'sub',
        'full_url':    make_rtsp_url(stream='sub'),
        'description': 'Lower-bandwidth sub RTSP stream'
    }
]

# ── Seeder logic ───────────────────────────────────────────────────────
def main():
    app = create_app()
    with app.app_context():
        # 1) Locate the Hikvision model
        model = DeviceModel.query.filter(
            func.lower(DeviceModel.name) == 'hikvision ipc-b640ha-lzu'
        ).first()
        if not model:
            raise RuntimeError(
                "DeviceModel 'Hikvision IPC-B640HA-LZU' not found. "
                "Run seed_hikvision_ipc_b640ha_lzu.py first."
            )

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
                tags=['factory', 'camera', 'hikvision'],
            )
            db.session.add(device)
            db.session.flush()
            print(f"✅ Created Device id={device.id!r} name={device.name!r}")
        else:
            print(f"ℹ️  Device exists id={device.id!r} name={device.name!r}")

        # 3) Upsert Camera row
        snapshot_url = SNAPSHOT_URL_TEMPLATE.format(host=HOST)
        cam = Camera.query.filter_by(serial_number=SERIAL_NUMBER).first()
        if not cam:
            cam = Camera(
                name=CAMERA_NAME,
                serial_number=SERIAL_NUMBER,
                address=HOST,
                port=PORT,
                username=USERNAME,
                password=PASSWORD,        # stored hashed by the model
                manufacturer='Hikvision',
                model='IPC-B640HA-LZU',
                firmware=None,
                description=DESCRIPTION,
                notes='PoE, 4 MP, dual-light MD 2.0',
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
                    full_url=s['full_url'],
                    is_active=True,
                    description=s['description']
                )
                db.session.add(stream)
                db.session.flush()
                print(f"✅ Created stream '{s['stream_type']}'")
            streams.append(stream)

        # 5) Default to 'sub'
        sub = next((st for st in streams if st.stream_type == 'sub'), None)
        if sub and getattr(cam, 'default_stream_id', None) != sub.id:
            cam.default_stream_id = sub.id
            print("✅ Set default stream to 'sub'")

        db.session.commit()
        print("🎉 Hikvision IPC-B640HA-LZU provisioning complete.")

if __name__ == '__main__':
    main()

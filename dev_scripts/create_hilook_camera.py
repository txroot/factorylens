#!/usr/bin/env python3
"""
Create a Hilook IPC‑B140H Camera + matching Device entry,
linked to the DeviceModel in the database.
Streams are created manually for main (101) and sub (102).
"""
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import func

# Ensure project root on path
sys.path.insert(0, Path(__file__).resolve().parents[1].as_posix())

from app import create_app
from extensions import db
from models.device import Device
from models.device_model import DeviceModel
from models.camera import Camera
from models.camera_stream import CameraStream

# ----------------------------------------------------------------------
# Constants / Configuration
# ----------------------------------------------------------------------
CAMERA_NAME     = 'Factory Lens Cam 2'
SERIAL_NUMBER   = 'CAM1-0002'
DESCRIPTION     = 'Entrance hallway camera'
NOTES           = 'Mounted above door, covers main entry.'
MQTT_CLIENT_ID  = 'factory-cam-002'
TOPIC_PREFIX    = 'factory/cameras/002'
LOCATION        = 'Entrance'

# RTSP connection details (hardcoded)
USERNAME        = 'admin'
PASSWORD        = 'R0148636'
HOST            = 'anr.microlumin.com'
PORT            = 554

# Stream definitions
STREAMS = [
    {
        'stream_type': 'main',
        'url_prefix': '/Streaming/Channels/101',
        'resolution_w': 1920,
        'resolution_h': 1080,
        'fps': 30,
        'codec': 'H.264',
        'bitrate_kbps': 2048,
        'bitrate_type': 'CBR',
        'description': 'Main RTSP stream'
    },
    {
        'stream_type': 'sub',
        'url_prefix': '/Streaming/Channels/102',
        'resolution_w': 1280,
        'resolution_h': 720,
        'fps': 30,
        'codec': 'H.264',
        'bitrate_kbps': 1024,
        'bitrate_type': 'VBR',
        'description': 'Sub RTSP stream'
    }
]


def main():
    app = create_app()
    with app.app_context():
        # Lookup the DeviceModel
        model = DeviceModel.query.filter(
            func.lower(DeviceModel.name).like('hilook ipc%')
        ).first()
        if not model:
            raise RuntimeError("Hilook IPC-B140H model not found. Run seed script first.")
        # Create or retrieve Device
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
                tags=['factory', 'camera', 'entry'],
            )
            db.session.add(device)
            db.session.flush()

        # Create or retrieve Camera
        cam = Camera.query.filter_by(serial_number=SERIAL_NUMBER).first()
        if cam:
            print(f"Camera already exists: {cam}")
            return

        cam = Camera(
            name=CAMERA_NAME,
            serial_number=SERIAL_NUMBER,
            address=HOST,
            port=PORT,
            username=USERNAME,
            password=PASSWORD,
            manufacturer='Hilook',
            model='IPC‑B140H',
            firmware='1.0',
            description=DESCRIPTION,
            notes=NOTES,
            status='offline',
            location=LOCATION,
            device_id=device.id
        )
        db.session.add(cam)
        db.session.flush()

        # Create streams
        streams = []
        for s in STREAMS:
            stream = CameraStream(
                camera_id=cam.id,
                stream_type=s['stream_type'],
                url_prefix=s['url_prefix'],
                stream_suffix=None,
                full_url=None,
                resolution_w=s['resolution_w'],
                resolution_h=s['resolution_h'],
                fps=s['fps'],
                codec=s['codec'],
                bitrate_kbps=s['bitrate_kbps'],
                bitrate_type=s['bitrate_type'],
                is_active=True,
                description=s['description']
            )
            db.session.add(stream)
            streams.append(stream)
        db.session.flush()

        # Link default stream (use sub as default)
        sub_stream = next((st for st in streams if st.stream_type=='sub'), None)
        if sub_stream:
            cam.default_stream_id = sub_stream.id

        # Commit everything
        db.session.commit()

        print(f"Created camera {cam} with streams: {', '.join(s.stream_type for s in streams)}")


if __name__ == '__main__':
    main()

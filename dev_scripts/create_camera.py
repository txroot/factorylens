#!/usr/bin/env python3
"""
Script to create a default Camera entry linked to a Device in the database,
following the 'All Are Devices' architecture.
"""
import sys
import os
from urllib.parse import urlparse
from datetime import datetime

# Ensure project directory is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models.camera import Camera
from models.device import Device

# Example RTSP URL
RTSP_URL = 'rtsp://admin:R0148636@anr.microlumin.com:554/Streaming/Channels/101'

# Camera & Device metadata
CAMERA_NAME     = 'Factory Lens Cam 2'
SERIAL_NUMBER   = 'CAM1-0002'
DESCRIPTION     = 'Entrance hallway camera'
NOTES           = 'Mounted above door, covers main entry.'
CODIFICATION    = 'H.264'
QUALITY         = 'medium'
BITRATE_TYPE    = 'CBR'
BITRATE_MAX     = 2048
STREAM_TYPE     = 'substream'
DEVICE_TYPE     = 'generic'
CATEGORY        = 'camera'
MQTT_CLIENT_ID  = 'factory-cam-002'
TOPIC_PREFIX    = 'factory/cameras/002'

def parse_rtsp(url):
    parts = urlparse(url)
    username = parts.username or ''
    password = parts.password or ''
    host     = parts.hostname
    port     = parts.port or 554
    path     = parts.path or ''
    stream_url = f"rtsp://{host}:{port}{path}"
    return username, password, host, port, stream_url, path


def create_camera():
    app = create_app()
    with app.app_context():
        # Check for existing camera
        existing = Camera.query.filter_by(serial_number=SERIAL_NUMBER).first()
        if existing:
            print(f"Camera with serial '{SERIAL_NUMBER}' already exists: {existing}")
            return

        # Check for existing device
        device = Device.query.filter_by(serial_number=SERIAL_NUMBER).first()
        if not device:
            device = Device(
                name=CAMERA_NAME,
                serial_number=SERIAL_NUMBER,
                device_type=DEVICE_TYPE,
                category=CATEGORY,
                mqtt_client_id=MQTT_CLIENT_ID,
                topic_prefix=TOPIC_PREFIX,
                status='offline',
                enabled=True,
                location='Entrance',
                description=DESCRIPTION,
                poll_interval=60,
                poll_interval_unit='sec',
                values={},
                parameters={},
                tags=["factory", "camera", "entry"],
                last_response_timestamp=datetime.utcnow()
            )
            db.session.add(device)
            db.session.flush()  # ensure device.id is available

        # Parse RTSP URL
        username, password, host, port, stream_url, suffix = parse_rtsp(RTSP_URL)

        # Create camera
        cam = Camera(
            name=CAMERA_NAME,
            serial_number=SERIAL_NUMBER,
            address=host,
            port=port,
            username=username,
            password=password,
            stream_url=stream_url,
            stream_url_suffix=suffix,
            stream_type=STREAM_TYPE,
            manufacturer='Generic',
            model='Generic Cam',
            firmware='1.0',
            description=DESCRIPTION,
            notes=NOTES,
            resolution_w=1920,
            resolution_h=1080,
            fps=30,
            protocol='RTSP',
            codification=CODIFICATION,
            quality=QUALITY,
            bitrate_type=BITRATE_TYPE,
            bitrate_max=BITRATE_MAX,
            status='offline',
            device_id=device.id  # Link the device
        )

        db.session.add(cam)
        db.session.commit()
        print(f"Created camera: {cam}")
        print(f"Linked to device: {device}")


if __name__ == '__main__':
    create_camera()
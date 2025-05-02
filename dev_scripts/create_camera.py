#!/usr/bin/env python3
"""
Script to create a default Camera entry in the database for development,
updated to match the extended Camera model.
"""
import sys
import os
from urllib.parse import urlparse

# Ensure project directory is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models.camera import Camera

# Example RTSP URL
RTSP_URL = 'rtsp://admin:R0148636@192.168.1.9:554/Streaming/Channels/302'

# Default camera data
CAMERA_NAME     = 'Factory Lens Cam 1'
SERIAL_NUMBER   = 'CAM1-0001'
DESCRIPTION     = 'Entrance hallway camera'
NOTES           = 'Mounted above door, covers main entry.'
CODIFICATION    = 'H.264'
QUALITY         = 'medium'
BITRATE_TYPE    = 'CBR'
BITRATE_MAX     = 2048  # in kbps
STREAM_TYPE     = 'substream'  # options: primary, substream, events


def parse_rtsp(url):
    """
    Parse an RTSP URL into components: username, password, host, port, path
    and derive stream_url and stream_url_suffix.
    """
    parts = urlparse(url)
    username = parts.username or ''
    password = parts.password or ''
    host     = parts.hostname
    port     = parts.port or 554
    path     = parts.path or ''
    # Base stream_url without credentials
    stream_url = f"rtsp://{host}:{port}{path}"
    # Store only suffix (path)
    stream_url_suffix = path
    return username, password, host, port, stream_url, stream_url_suffix


def create_camera():
    app = create_app()
    with app.app_context():
        # Check if camera already exists
        existing = Camera.query.filter_by(serial_number=SERIAL_NUMBER).first()
        if existing:
            print(f"Camera with serial '{SERIAL_NUMBER}' already exists: {existing}")
            return

        # Parse the RTSP URL
        username, password, host, port, stream_url, stream_url_suffix = parse_rtsp(RTSP_URL)

        # Create new Camera instance using extended model fields
        cam = Camera(
            name               = CAMERA_NAME,
            serial_number      = SERIAL_NUMBER,
            address            = host,
            port               = port,
            username           = username,
            password           = password,
            stream_url         = stream_url,
            stream_url_suffix  = stream_url_suffix,
            stream_type        = STREAM_TYPE,
            manufacturer       = 'Generic',
            model              = 'Generic Cam',
            firmware           = '1.0',
            description        = DESCRIPTION,
            notes              = NOTES,
            resolution_w       = 1920,
            resolution_h       = 1080,
            fps                = 30,
            protocol           = 'RTSP',
            codification       = CODIFICATION,
            quality            = QUALITY,
            bitrate_type       = BITRATE_TYPE,
            bitrate_max        = BITRATE_MAX,
            status             = 'offline'
        )

        db.session.add(cam)
        db.session.commit()
        print(f"Created camera: {cam}")


if __name__ == '__main__':
    create_camera()

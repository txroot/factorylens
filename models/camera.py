# models/camera.py

from extensions import db
from datetime import datetime
from sqlalchemy.orm import relationship

class Camera(db.Model):
    __tablename__ = 'cameras'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to Device table (if applicable)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    device = relationship('Device', backref='cameras')

    # Human-friendly name
    name = db.Column(db.String(100), nullable=False, unique=True)

    # Network settings: address can be IP or DNS name
    address         = db.Column(db.String(255), nullable=False)
    port            = db.Column(db.Integer, default=554)  # default RTSP port
    username        = db.Column(db.String(50))
    password        = db.Column(db.String(255))           # encrypted or hashed

    # Stream configuration
    stream_url      = db.Column(db.String(255), nullable=False)
    stream_url_suffix = db.Column(db.String(255), comment="Suffix for stream URL, e.g. /Streaming/Channels/102")
    stream_type     = db.Column(
        db.Enum('primary','substream','events', name='stream_type'),
        default='primary', nullable=False
    )

    # Camera metadata
    manufacturer    = db.Column(db.String(100))
    model           = db.Column(db.String(100))
    firmware        = db.Column(db.String(50))
    serial_number   = db.Column(db.String(100), unique=True)

    # Descriptive fields
    description     = db.Column(db.Text, comment="Optional description of the camera")
    notes           = db.Column(db.Text, comment="Additional notes or comments")

    # Desired capture settings
    resolution_w    = db.Column(db.Integer, default=1920)
    resolution_h    = db.Column(db.Integer, default=1080)
    fps             = db.Column(db.Integer, default=30)
    protocol        = db.Column(
        db.Enum('RTSP','HTTP','ONVIF','MJPEG', name='camera_protocol'),
        default='RTSP', nullable=False
    )

    # Encoding / bitrate
    codification    = db.Column(db.String(50), comment="e.g. H.264, H.265, MJPEG")
    quality         = db.Column(db.String(50), comment="Quality preset or description")
    bitrate_type    = db.Column(db.String(50), comment="Type of bitrate control, e.g. CBR, VBR")
    bitrate_max     = db.Column(db.Integer, comment="Maximum bitrate in kbps")

    # Runtime status
    status          = db.Column(
        db.Enum('online','offline','error', name='camera_status'),
        default='offline', nullable=False
    )
    last_heartbeat  = db.Column(db.DateTime, default=datetime.utcnow)
    last_error      = db.Column(db.String(255))

    # Optional physical location
    location        = db.Column(db.String(255), comment="Physical location or area of the camera")

    # Audit timestamps
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self):
        return (
            f"<Camera {self.name} ({self.address}:{self.port}) ["  \
            f"{self.stream_type}] – {self.status}>"
        )

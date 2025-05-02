# models/camera.py

from extensions import db
from datetime import datetime

class Camera(db.Model):
    __tablename__ = 'cameras'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Human-friendly name
    name = db.Column(db.String(100), nullable=False, unique=True)

    # Network settings
    ip_address    = db.Column(db.String(45), nullable=False)  # IPv4 or IPv6
    port          = db.Column(db.Integer, default=554)        # default RTSP port
    username      = db.Column(db.String(50))
    password      = db.Column(db.String(255))                 # encrypted or hashed

    # Stream endpoint (e.g. rtsp://…)
    stream_url    = db.Column(db.String(255), nullable=False)

    # Camera metadata
    manufacturer  = db.Column(db.String(100))
    model         = db.Column(db.String(100))
    firmware      = db.Column(db.String(50))
    serial_number = db.Column(db.String(100), unique=True)

    # Desired capture settings
    resolution_w  = db.Column(db.Integer, default=1920)
    resolution_h  = db.Column(db.Integer, default=1080)
    fps           = db.Column(db.Integer, default=30)
    protocol      = db.Column(db.Enum('RTSP','HTTP','ONVIF','MJPEG', name='camera_protocol'), default='RTSP')

    # Runtime status
    status        = db.Column(db.Enum('online','offline','error', name='camera_status'), default='offline')
    last_heartbeat = db.Column(db.DateTime, default=datetime.utcnow)
    last_error    = db.Column(db.String(255))

    # Optional physical location
    location      = db.Column(db.String(255))

    # Audit timestamps
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Camera {self.name} ({self.ip_address}:{self.port}) – {self.status}>"
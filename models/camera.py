# models/camera.py

from extensions import db
from datetime import datetime
from sqlalchemy.orm import relationship

class Camera(db.Model):
    __tablename__ = 'cameras'

    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to Device table (if applicable)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    device = relationship('Device', backref='cameras')

    # Human-friendly name
    name = db.Column(db.String(100), nullable=False, unique=True)

    # Network settings
    address = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, default=554)
    username = db.Column(db.String(50))
    password = db.Column(db.String(255))

    # Camera metadata
    manufacturer = db.Column(db.String(100))
    model = db.Column(db.String(100))
    firmware = db.Column(db.String(50))
    serial_number = db.Column(db.String(100), unique=True)

    # Descriptive fields
    description = db.Column(db.Text, comment="Optional description of the camera")
    notes = db.Column(db.Text, comment="Additional notes or comments")

    # Default stream reference
    default_stream_id = db.Column(db.Integer, db.ForeignKey('camera_streams.id'))
    default_stream = relationship('CameraStream', foreign_keys=[default_stream_id])

    # Snapshot settings
    snapshot_url = db.Column(db.String(255), comment="Direct full URL to fetch a snapshot image")
    snapshot_prefix = db.Column(db.String(255), default="/cgi-bin/api.cgi", comment="Prefix for snapshot CGI endpoint")
    snapshot_type = db.Column(
        db.Enum('manual', 'schedule', 'motion_event', name='snapshot_type'),
        default='manual',
        nullable=False,
        comment="When snapshots are expected to be taken"
    )
    snapshot_interval_seconds = db.Column(db.Integer, comment="Interval in seconds for scheduled snapshots")

    # Event capabilities
    supports_motion_detection = db.Column(db.Boolean, default=False)
    supports_person_detection = db.Column(db.Boolean, default=False)
    supports_vehicle_detection = db.Column(db.Boolean, default=False)
    motion_detection_enabled = db.Column(db.Boolean, default=False)

    # Alert and automation
    alert_via_email = db.Column(db.Boolean, default=False)
    alert_via_ftp = db.Column(db.Boolean, default=False)
    alert_via_http = db.Column(db.Boolean, default=False)

    # Runtime status
    status = db.Column(
        db.Enum('online', 'offline', 'error', name='camera_status'),
        default='offline',
        nullable=False
    )
    last_heartbeat = db.Column(db.DateTime, default=datetime.utcnow)
    last_error = db.Column(db.String(255))

    # Optional physical location
    location = db.Column(db.String(255), comment="Physical location or area of the camera")

    # Audit timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Camera {self.name} ({self.address}:{self.port}) – {self.status}>"

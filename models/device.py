# models/device.py

from extensions import db
from datetime import datetime

class Device(db.Model):
    __tablename__ = 'devices'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Human-friendly name
    name = db.Column(db.String(100), nullable=False, unique=True)

    # (Optional) Serial number or hardware ID
    serial_number = db.Column(db.String(100), unique=True)

    # What kind of device this is
    device_type = db.Column(
        db.Enum('shelly1', 'shelly2', 'generic', name='device_type'),
        nullable=False,
        default='generic'
    )

    # MQTT specifics
    mqtt_client_id  = db.Column(db.String(100), nullable=False, unique=True)
    topic_prefix    = db.Column(db.String(200), nullable=False,
                                comment="Root topic, e.g. 'shelly/1ABC23'")
    # If you need to store more settings per‐device:
    config = db.Column(db.JSON, comment="Arbitrary JSON blob for extra settings")

    # Runtime
    status         = db.Column(
        db.Enum('online','offline','error', name='device_status'),
        default='offline'
    )
    last_seen      = db.Column(db.DateTime, default=datetime.utcnow)
    last_error     = db.Column(db.String(255))

    # Audit
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime,
                               default=datetime.utcnow,
                               onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Device {self.name} ({self.device_type}) – {self.status}>"
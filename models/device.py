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
    serial_number = db.Column(db.String(100), nullable=True)

    # Device FK -> concrete model
    device_model_id = db.Column(db.Integer,
                                db.ForeignKey("device_models.id"),
                                nullable=False)
    model           = db.relationship("DeviceModel", back_populates="devices")
    '''# models/actions.py
from extensions import db
from datetime import datetime

class Action(db.Model):
    __tablename__ = "actions"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)

    # JSON blobs – keep them flexible
    trigger     = db.Column(db.JSON, nullable=False)   # e.g. {device,event,…}
    result      = db.Column(db.JSON, nullable=False)   # e.g. [{device,action,…}, …]

    enabled     = db.Column(db.Boolean, default=True, nullable=False)

    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime,
                            default=datetime.utcnow,
                            onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Action {self.name} enabled={self.enabled}>"

    device_type = db.Column(
        db.Enum('shelly1', 'shelly2', 'generic', name='device_type'),
        nullable=False,
        default='generic'
    )
    category = db.Column(
        db.Enum('camera', 'logger', 'messenger', 'processor', 'module', 'iot', 'storage', name='device_category'),
        nullable=False,
        default='iot'
    )    
    
    '''


    # Polling settings
    poll_interval = db.Column(db.Integer, default=60, comment="Polling frequency value")
    poll_interval_unit = db.Column(
        db.Enum('ms', 'sec', 'min', 'hour', 'day', name='poll_unit'),
        default='sec',
        nullable=False,
        comment="Polling interval unit"
    )

    # Runtime and diagnostic
    values = db.Column(db.JSON, comment="Runtime values such as state, ip, etc.")
    last_response_timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # MQTT specifics
    mqtt_client_id = db.Column(db.String(100), nullable=False, unique=True)
    topic_prefix = db.Column(db.String(200), nullable=False,
                             comment="Root topic, e.g. 'shellies'")

    # General control and metadata
    parameters = db.Column(db.JSON, comment="Arbitrary JSON blob for extra settings")
    tags = db.Column(db.JSON, comment="List of tags for classification and filtering")
    description = db.Column(db.Text, comment="Optional device description")
    image = db.Column(db.String(255), comment="Optional image URL or path")
    location = db.Column(db.String(255), comment="Logical or physical location of the device")
    qr_code = db.Column(db.String(255), comment="QR code string or image URL")
    
    # Status and audit
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    status = db.Column(
        db.Enum('online','offline','error', name='device_status'),
        default='offline'
    )
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_error = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime,
                           default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Device {self.name} ({self.device_type}) – {self.status}>"
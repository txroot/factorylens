# models/device_action_schema.py
from extensions import db
from datetime import datetime

class DeviceActionSchema(db.Model):
    """
    One JSON blob that enumerates every MQTT topic / command topic
    that a concrete *DeviceModel* understands, plus metadata the UI
    needs to build drop‑downs and validate values.
    """
    __tablename__ = "device_action_schemas"

    id         = db.Column(db.Integer, primary_key=True)
    model_id   = db.Column(db.Integer,
                           db.ForeignKey("device_models.id"),
                           unique=True, nullable=False)
    schema     = db.Column(db.JSON, nullable=False)     # see spec in the doc
    version    = db.Column(db.String(20), default="1.0.0")

    updated_at = db.Column(db.DateTime,
                           default=datetime.utcnow,
                           onupdate=datetime.utcnow)

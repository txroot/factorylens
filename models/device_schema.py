# models/device_schema.py

from __future__ import annotations
from datetime import datetime
from extensions import db

class DeviceSchema(db.Model):
    """
    Stores every *kind* of schema a DeviceModel may need.

    ┌─────────┬─────────┬──────────────────────────────────────────────────────┐
    │ kind    │ purpose │ stored JSON structure                                │
    ├─────────┼─────────┼──────────────────────────────────────────────────────┤
    │ config  │ UI form │ JSON‑Schema for the Settings → “Config” tab         │
    │ topic   │ Actions │ { topics:{}, command_topics:{} }  (old action schema)│
    │ function│ Flow    │ { functions:[{name, args, returns,…}, …] }           │
    └─────────┴─────────┴──────────────────────────────────────────────────────┘
    """
    __tablename__ = "device_schemas"

    id          = db.Column(db.Integer, primary_key=True)
    model_id    = db.Column(db.Integer,
                            db.ForeignKey("device_models.id"),
                            nullable=False)
    kind        = db.Column(
        db.Enum("config", "topic", "function", name="schema_kind"),
        default="config", nullable=False
    )
    schema      = db.Column(db.JSON, nullable=False)
    version     = db.Column(db.String(20), default="1.0.0")
    updated_at  = db.Column(db.DateTime,
                            default=datetime.utcnow,
                            onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("model_id", "kind",
                            name="uq_model_kind"),  # one‑per‑kind
    )

    def __repr__(self):
        return f"<DeviceSchema {self.model_id}:{self.kind} v{self.version}>"
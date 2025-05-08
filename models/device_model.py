# models/device_model.py

from extensions import db
from models.device_schema       import DeviceSchema

class DeviceModel(db.Model):
    """
    One concrete hardware product – Shelly 1, Reolink 810A …
    """
    __tablename__ = "device_models"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, comment="Optional description of the device model")
    serial_number = db.Column(db.String(100), unique=True, comment="Serial number or hardware ID")
    firmware    = db.Column(db.String(50), comment="Firmware version")
    manufacturer = db.Column(db.String(100))
    notes       = db.Column(db.Text)

    # FK → category
    category_id = db.Column(db.Integer,
                             db.ForeignKey("device_categories.id"),
                             nullable=False)
    category    = db.relationship("DeviceCategory", back_populates="models")

    # ── Schemas (one row per *kind*) ───────────────────────────────────────
    schemas = db.relationship(
        "DeviceSchema",
        backref="model",
        cascade="all, delete-orphan",
        single_parent=True
    )

    # nice helpers
    def get_schema(self, kind: str):
        return next((s for s in self.schemas if s.kind == kind), None)

    devices     = db.relationship("Device", back_populates="model")

    def __repr__(self):
        return f"<DeviceModel {self.name} in {self.category.name}>"
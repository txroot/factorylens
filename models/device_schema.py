# models/device_schema.py

from extensions import db

class DeviceSchema(db.Model):
    __tablename__ = "device_schemas"
    id          = db.Column(db.Integer, primary_key=True)
    json_schema = db.Column("schema", db.JSON, nullable=False)
    ui_hints    = db.Column(db.JSON)
    version     = db.Column(db.String(20), default="1.0.0")

    # one‑to‑one to DeviceModel
    model = db.relationship("DeviceModel", back_populates="schema", uselist=False)

    def __repr__(self):
        return f"<DeviceSchema {self.id} v{self.version}>"
    

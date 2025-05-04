# models/device_model.py

from extensions import db

class DeviceModel(db.Model):
    """
    One concrete hardware product – Shelly 1, Reolink 810A …
    """
    __tablename__ = "device_models"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)
    manufacturer = db.Column(db.String(100))
    notes       = db.Column(db.Text)

    # FK → category
    category_id = db.Column(db.Integer,
                             db.ForeignKey("device_categories.id"),
                             nullable=False)
    category    = db.relationship("DeviceCategory", back_populates="models")

    # optional FK → JSON schema
    schema_id   = db.Column(db.Integer,
                             db.ForeignKey("device_schemas.id"),
                             unique=True)
    schema = db.relationship(
        "DeviceSchema",
        back_populates="model",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
    )

    devices     = db.relationship("Device", back_populates="model")

    def __repr__(self):
        return f"<DeviceModel {self.name} in {self.category.name}>"
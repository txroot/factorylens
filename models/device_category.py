# models/device_category.py

from extensions import db

class DeviceCategory(db.Model):
    __tablename__ = "device_categories"
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)   # "camera", "iot", ...

    # Human-friendly display name (can include emoji)
    label = db.Column(db.String(100), nullable=False)

    models = db.relationship("DeviceModel", back_populates="category",
                             cascade="all, delete-orphan")

    def __repr__(self):
        return f"<DeviceCategory {self.name}>"

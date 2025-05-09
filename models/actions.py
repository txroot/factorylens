# models/actions.py
from extensions import db
from datetime import datetime

class Action(db.Model):
    __tablename__ = "actions"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)

    # JSON blobs – keep them flexible
    chain       = db.Column(db.JSON, nullable=False)

    enabled     = db.Column(db.Boolean, default=True, nullable=False)

    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime,
                            default=datetime.utcnow,
                            onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Action {self.name} enabled={self.enabled}>"

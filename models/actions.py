# models/actions.py
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

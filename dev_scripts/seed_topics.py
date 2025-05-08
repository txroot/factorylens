#!/usr/bin/env python3
# dev_scripts/seed_topics.py

import os, sys
from datetime import datetime

# make sure project root is on your PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from extensions import db
from models.device_model    import DeviceModel
from models.device_schema   import DeviceSchema

# this is the exact name you have in your device_models table
SHELLY_MODEL_NAME = "Shelly 2.5 MQTT"

# your topic-schema JSON (example trimmed for brevity)
SHELLY_TOPIC_SCHEMA = {
    "topics": {
        "input/0": {"label":"Input 0",   "type":"bool", "true":1, "false":0},
        "input_event/0": {
            "label":"Button 0 event","type":"enum",
            "values":["S","L"], "display":{"S":"Short Press","L":"Long Press"}
        },
        "relay/0": {"label":"Relay 0","type":"enum","values":["on","off"]},
        "relay/0/power": {
            "label":"Power","type":"number","units":"W",
            "range":[0,None],"comparators":["<","<=","==","!="," >=",">"]
        },
        "temperature": {
            "label":"Temperature","type":"number","units":"°C",
            "range":[-50,150],"comparators":["<","<=","==","!="," >=",">"]
        }
    },
    "command_topics": {
        "relay/0/command": {"label":"Relay 0 command","type":"enum","values":["on","off"]}
    }
}

def main():
    app = create_app()
    with app.app_context():
        mdl = DeviceModel.query.filter_by(name=SHELLY_MODEL_NAME).first()
        if not mdl:
            print(f"ERROR: Model '{SHELLY_MODEL_NAME}' not found in device_models!")
            print("Available models are:")
            for m in DeviceModel.query.order_by(DeviceModel.id):
                print(f"  • {m.name!r}")
            sys.exit(1)

        # remove any existing topic‐schema
        existing = DeviceSchema.query.filter_by(
            model_id=mdl.id,
            kind="topic"
        ).first()
        if existing:
            db.session.delete(existing)
            db.session.flush()

        # insert new one
        new_schema = DeviceSchema(
            model_id=mdl.id,
            kind="topic",
            schema=SHELLY_TOPIC_SCHEMA,
            version="1.0.0",
            updated_at=datetime.utcnow()
        )
        db.session.add(new_schema)
        db.session.commit()
        print(f"Seeded topic‐schema for model '{mdl.name}' (id={mdl.id}).")

if __name__ == "__main__":
    main()

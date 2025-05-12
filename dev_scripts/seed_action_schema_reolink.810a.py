# dev_scripts/seed_reolink_810a_action_schema.py
import os
import sys
import json

# ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models.device_model  import DeviceModel
from models.device_schema import DeviceSchema

REOLINK_810A_ACTION_SCHEMA = {
    "topics": {
        # camera emits snapshots on this topic; payload is raw JPEG file
        "snapshot": {
            "label":       "Snapshot",
            "tooltip":     "Camera snapshot event",
            "hint":        "The payload is a binary JPEG snapshot",
            "explanation": "Publishes a binary snapshot; use Evaluate to check its format",
            "type":        "file",
            "values":      ["jpg", "pdf"],
            "poll_interval":      0,
            "poll_interval_unit": "sec",
            "poll_topic":         "",
            "poll_payload":       ""
        }
    },
    "command_topics": {
        # trigger the camera to take a new snapshot;
        # command payload chooses desired output
        "snapshot/exe": {
            "label":         "Take Snapshot",
            "tooltip":       "Request a new snapshot",
            "hint":          "Choose 'jpg' or 'pdf' output",
            "explanation":   "Sends a command to capture an image; publishes file on 'snapshot'",
            "type":          "enum",
            "values":        ["jpg", "pdf"],
            "timeout":       30,
            "timeout_unit":  "sec",
            "result_topic":  "snapshot",
            "result_payload": {
                "options": [
                    {
                        "label":       "Snapshot Format",
                        "tooltip":     "Format of the returned snapshot",
                        "hint":        "Indicates whether the snapshot was jpg or pdf",
                        "type":        "file",
                        "values":      ["jpg", "pdf"]
                    }
                ]
            }
        }
    }
}

def main():
    app = create_app()
    with app.app_context():
        mdl = DeviceModel.query.filter_by(name="Reolink 810A").first()
        if not mdl:
            print("❌ Reolink 810A model not found")
            sys.exit(1)

        # upsert a single DeviceSchema row of kind='topic'
        row = DeviceSchema.query.filter_by(model_id=mdl.id, kind="topic").first()
        if row:
            row.schema = REOLINK_810A_ACTION_SCHEMA
            print("🔄 Updated Reolink 810A action schema")
        else:
            row = DeviceSchema(
                model_id=mdl.id,
                kind="topic",
                schema=REOLINK_810A_ACTION_SCHEMA
            )
            db.session.add(row)
            print("✅ Created Reolink 810A action schema")

        db.session.commit()
        print("🎉 Reolink 810A action schema committed")

if __name__ == "__main__":
    main()

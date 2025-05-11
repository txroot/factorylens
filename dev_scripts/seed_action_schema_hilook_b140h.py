import os
import sys
import json

# ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models.device_model  import DeviceModel
from models.device_schema import DeviceSchema

HILOOK_IPC_B140H_ACTION_SCHEMA = {
    "topics": {
        # camera emits snapshots on this topic, payload is raw file but tagged with extension
        "snapshot": {
            "label":              "Snapshot",
            "tooltip":            "Camera snapshot event",
            "hint":               "The file format is indicated by its extension",
            "explanation":        "Publishes a binary snapshot; use Evaluate to check its extension",
            "type":               "file",
            "values":             ["jpg", "pdf"],
            "poll_interval":      0,
            "poll_interval_unit": "sec",
            "poll_topic":         "",
            "poll_payload":       ""
        }
    },
    "command_topics": {
        # trigger the camera to take a new snapshot;
        # command payload chooses desired format
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
        mdl = DeviceModel.query.filter_by(name="Hilook IPC-B140H").first()
        if not mdl:
            print("❌ Hilook IPC-B140H model not found")
            sys.exit(1)

        # upsert a single DeviceSchema row of kind='topic'
        row = DeviceSchema.query.filter_by(model_id=mdl.id, kind="topic").first()
        if row:
            row.schema = HILOOK_IPC_B140H_ACTION_SCHEMA
            print("🔄 Updated Hilook IPC-B140H action schema")
        else:
            row = DeviceSchema(
                model_id=mdl.id,
                kind="topic",
                schema=HILOOK_IPC_B140H_ACTION_SCHEMA
            )
            db.session.add(row)
            print("✅ Created Hilook IPC-B140H action schema")

        db.session.commit()
        print("🎉 Hilook IPC-B140H action schema committed")

if __name__ == "__main__":
    main()

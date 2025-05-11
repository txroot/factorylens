# dev_scripts/seed_storage_actions.py

import os
import sys
import json

# Add project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models.device_model import DeviceModel
from models.device_schema import DeviceSchema

STORAGE_UNIT_ACTION_SCHEMA = {
    "topics": {
        "file/created": {
            "label":              "File Saved",
            "tooltip":            "Indicates a new file was saved",
            "hint":               "Relative path under the storage unit",
            "explanation":        "Emitted after a successful save; payload is file path",
            "type":               "enum",
            "values":             ["success","error"],
            "display": {
                "success": "✅ Success",
                "error":   "❌ Error"
            },
            "poll_interval":      0,
            "poll_interval_unit": "sec",
            "poll_topic":         "",
            "poll_payload":       ""
        }
    },
    "command_topics": {
        "file/image/create": {
            "label":         "Save File",
            "tooltip":       "Save a file to this storage unit",
            "hint":          "Payload must include a base64 file and extension",
            "explanation":   "Receives `{ext: 'jpg'|'pdf', file: '...'}` and stores it on disk",
            "type":          "file",
            "values":        ["jpg", "pdf"],
            "timeout":       30,
            "timeout_unit":  "sec",
            "result_topic":  "file/created",
            "result_payload": {
                    "options": [
                    {
                    "label":   "Outcome",
                    "tooltip": "Whether the save succeeded or failed",
                    "hint":    "Use this to route success vs error",
                    "type":    "enum",
                    "values":  ["success","error"],
                    "display": {
                        "success": "✅ Success",
                        "error":   "❌ Error"
                    }
                    }
                ],
                "details": {
                    "label":   "Stored File Path",
                    "tooltip": "Relative path under the storage unit",
                    "hint":    "Available after a successful save",
                    "type":    "string"
                }
            }
        }
    }
}

def main():
    app = create_app()
    with app.app_context():
        mdl = DeviceModel.query.filter_by(name="Local storage").first()
        if not mdl:
            print("❌ Storage model not found")
            sys.exit(1)

        # upsert schema row
        row = DeviceSchema.query.filter_by(model_id=mdl.id, kind="topic").first()
        if row:
            row.schema = STORAGE_UNIT_ACTION_SCHEMA
            print("🔄 Updated Storage Unit action schema")
        else:
            row = DeviceSchema(
                model_id=mdl.id,
                kind="topic",
                schema=STORAGE_UNIT_ACTION_SCHEMA
            )
            db.session.add(row)
            print("✅ Created Storage Unit action schema")

        db.session.commit()
        print("🎉 Storage Unit action schema committed")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Seed the *FTP / SFTP storage* device model with the same action / command
topics used by the local-storage model.

Run:
    python dev_scripts/seed_ftp_storage_actions.py
"""

import os
import sys
import json

# Add project root to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from extensions import db
from models.device_model import DeviceModel
from models.device_schema import DeviceSchema

# ---------------------------------------------------------------------------
# Topic / command-topic schema (identical to local storage)
# ---------------------------------------------------------------------------

FTP_STORAGE_ACTION_SCHEMA = {
    "topics": {
        "file/created": {
            "label":              "File Saved",
            "tooltip":            "Indicates a new file was saved",
            "hint":               "Relative path under the storage unit",
            "explanation":        "Emitted after a successful save; payload is file path",
            "type":               "enum",
            "values":             ["success", "error"],
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
            "explanation":   "Receives `{ext: 'jpg'|'pdf', file: '...'}` and stores it on the server",
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
                        "values":  ["success", "error"],
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

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    app = create_app()
    with app.app_context():
        # Look up the FTP / SFTP storage device model seeded by your main device-model script
        mdl = DeviceModel.query.filter_by(name="FTP / SFTP storage").first()
        if not mdl:
            print("❌ FTP / SFTP Storage model not found – seed the device models first.")
            sys.exit(1)

        # Upsert the topic schema row
        row = DeviceSchema.query.filter_by(model_id=mdl.id, kind="topic").first()
        if row:
            row.schema = FTP_STORAGE_ACTION_SCHEMA
            print("🔄 Updated FTP Storage action schema")
        else:
            row = DeviceSchema(
                model_id=mdl.id,
                kind="topic",
                schema=FTP_STORAGE_ACTION_SCHEMA
            )
            db.session.add(row)
            print("✅ Created FTP Storage action schema")

        db.session.commit()
        print("🎉 FTP Storage action schema committed")

if __name__ == "__main__":
    main()

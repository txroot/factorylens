#!/usr/bin/env python3
"""
Seed an MQTT-style action schema for the
Hikvision IPC-B640HA-LZU (4 MP Dual-Light MD 2.0) camera.

• Adds/updates a DeviceSchema row of kind='topic'
• Defines:
    – a 'snapshot' event topic that publishes raw JPEGs
    – a 'motion' event topic (Hikvision MD 2.0)
    – a 'snapshot/exe' command topic to trigger still images
"""

import os
import sys
import json

# ensure project root on sys.path
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from app import create_app
from extensions import db
from models.device_model  import DeviceModel
from models.device_schema import DeviceSchema

HIKVISION_B640HA_ACTION_SCHEMA = {
    "topics": {
        # ─── Event: snapshot published by the camera ─────────────────────
        "snapshot": {
            "label":       "Snapshot",
            "tooltip":     "Camera snapshot event",
            "hint":        "Payload is a binary JPEG image",
            "explanation": "Camera publishes a JPEG each time a snapshot is taken.",
            "type":        "file",
            "values":      ["jpg"],
            "poll_interval":      0,
            "poll_interval_unit": "sec",
            "poll_topic":         "",
            "poll_payload":       ""
        },

        # ─── Event: motion-detection (MD 2.0) ───────────────────────────
        "motion": {
            "label":       "Motion",
            "tooltip":     "Smart motion detection event",
            "hint":        "Boolean JSON payload: {\"motion\": true}",
            "explanation": "Publishes when the camera detects a person/vehicle.",
            "type":        "json",
            "values":      ["object"],
            "poll_interval":      0,
            "poll_interval_unit": "sec"
        }
    },

    "command_topics": {
        # ─── Command: trigger a new snapshot ─────────────────────────────
        "snapshot/exe": {
            "label":         "Take Snapshot",
            "tooltip":       "Request a new snapshot",
            "hint":          "No payload needed",
            "explanation":   "Camera captures a still image and publishes it on 'snapshot'.",
            "type":          "void",
            "values":        [],
            "timeout":       30,
            "timeout_unit":  "sec",
            "result_topic":  "snapshot",
            "result_payload": {
                "options": []
            }
        }
    }
}


def main():
    app = create_app()
    with app.app_context():
        mdl = DeviceModel.query.filter_by(name="Hikvision IPC-B640HA-LZU").first()
        if not mdl:
            print("❌ Hikvision IPC-B640HA-LZU model not found "
                  "(run seed_hikvision_ipc_b640ha_lzu.py first).")
            sys.exit(1)

        # upsert a single DeviceSchema row of kind='topic'
        row = DeviceSchema.query.filter_by(model_id=mdl.id, kind="topic").first()
        if row:
            row.schema = HIKVISION_B640HA_ACTION_SCHEMA
            print("🔄 Updated Hikvision B640HA action schema")
        else:
            row = DeviceSchema(
                model_id=mdl.id,
                kind="topic",
                schema=HIKVISION_B640HA_ACTION_SCHEMA
            )
            db.session.add(row)
            print("✅ Created Hikvision B640HA action schema")

        db.session.commit()
        print("🎉 Hikvision IPC-B640HA-LZU action schema committed")


if __name__ == "__main__":
    main()

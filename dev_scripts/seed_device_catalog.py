#!/usr/bin/env python3
"""
Seed initial DeviceCategory, DeviceModel and DeviceSchema rows.
Run once (or repeatedly) after the tables exist.
"""
import os
import sys
from pathlib import Path

# Add project root to import path
top = Path(__file__).resolve().parents[1].as_posix()
if top not in sys.path:
    sys.path.insert(0, top)

from app import create_app
from extensions import db
from models.device_category import DeviceCategory
from models.device_model    import DeviceModel
from models.device_schema   import DeviceSchema

# Define your categories (slug, label)
CATEGORIES = [
    ("camera",   "📷 Camera"),
    ("iot",      "🌐 IoT Device"),
    ("storage",  "💾 Storage Unit"),
    ("messenger","✉️ Messenger"),
    ("module",   "📦 Module"),
    ("logger",   "📝 Logger"),
    ("processor","🧠 AI Processor"),
]

# Map of category slug → list of (model name, notes)
MODELS = {
    "camera": [
        ("Reolink 810A",     "Reolink 8 MP PoE camera"),
        ("Hilook IPC-B140H", "Hilook 4 MP bullet camera"),
    ],
    "iot": [
        ("Shelly 1", "Shelly 1 Wi-Fi relay"),
        ("Shelly 2", "Shelly 2 dual relay"),
    ],
}

# JSON-Schema for Reolink 810A configuration
REOLINK_810A_CONFIG = {
  "type": "object",
  "title": "Reolink 810A configuration",
  "properties": {
    "address": {
      "type": "string",
      "title": "Camera IP / Host",
      "format": "hostname",
      "minLength": 7
    },
    "port": {
      "type": "integer",
      "title": "RTSP Port",
      "default": 554,
      "minimum": 1,
      "maximum": 65535
    },
    "username": {
      "type": "string",
      "title": "Username"
    },
    "password": {
      "type": "string",
      "title": "Password",
      "format": "password"
    },
    "main_stream_url": {
      "type": "string",
      "title": "Main RTSP Stream URL",
      "format": "uri",
      "default": "rtsp://{username}:{password}@{address}:{port}/h264Preview_01_main"
    },
    "sub_stream_url": {
      "type": "string",
      "title": "Sub RTSP Stream URL",
      "format": "uri",
      "default": "rtsp://{username}:{password}@{address}:{port}/h264Preview_01_sub"
    },
    "snapshot_url": {
      "type": "string",
      "title": "Snapshot URL",
      "format": "uri",
      "default": "http://{address}/cgi-bin/api.cgi?cmd=Snap&channel=0&rs=<token>&user={username}&password={password}"
    },
    "snapshot_width": {
      "type": "integer",
      "title": "Snapshot Width (px)",
      "default": 1920,
      "minimum": 1
    },
    "snapshot_height": {
      "type": "integer",
      "title": "Snapshot Height (px)",
      "default": 1080,
      "minimum": 1
    }
  },
  "required": ["address", "username", "password", "main_stream_url", "snapshot_url"]
}

# JSON-Schema for Hilook IPC-B140H configuration
HILOOK_IPC_B140H_CONFIG = {
  "type": "object",
  "title": "Hilook IPC-B140H configuration",
  "properties": {
    "address":  { "type": "string",  "title": "IP / host", "minLength": 1 },
    "port":     { "type": "integer", "default": 554, "minimum": 1, "maximum": 65535 },
    "username": { "type": "string" },
    "password": { "type": "string", "format": "password" },
    "stream_type": {
      "type": "string",
      "enum": ["primary","sub","fluent","custom"],
      "default": "primary"
    },
    "stream_url_suffix": {
      "type": "string",
      "default": "/Streaming/Channels/102"
    },
    "resolution": {
      "type": "string",
      "enum": ["1920x1080","1280x720","640x360"],
      "default": "1920x1080"
    },
    "fps": { "type": "integer", "default": 30, "minimum": 1, "maximum": 60 },
    "snapshot_url":      { "type": "string", "format": "uri" },
    "snapshot_interval_seconds": { "type": "integer", "default": 0 },
    "motion_detection_enabled":  { "type": "boolean", "default": False }
  },
  "required": ["address","stream_url_suffix"]
}


def upsert(instance, uniq_attrs):
    """
    Insert or update a row so script can be run repeatedly.
    Returns: (instance, True if inserted, False if updated)
    """
    cls = type(instance)
    filters = {attr: getattr(instance, attr) for attr in uniq_attrs}
    existing = cls.query.filter_by(**filters).first()
    if existing:
        pk = {c.name for c in cls.__table__.primary_key}
        for col in cls.__table__.columns.keys():
            if col in uniq_attrs or col in pk:
                continue
            setattr(existing, col, getattr(instance, col))
        return existing, False
    db.session.add(instance)
    return instance, True


def seed():
    app = create_app()
    with app.app_context():
        # 1) Seed categories
        cat_map = {}
        for slug, label in CATEGORIES:
            cat, created = upsert(DeviceCategory(name=slug, label=label), ["name"])
            cat_map[slug] = cat
        db.session.flush()

        # 2) Seed models
        for cat_slug, models in MODELS.items():
            for name, notes in models:
                mdl, created = upsert(
                    DeviceModel(
                        name=name,
                        notes=notes,
                        category_id=cat_map[cat_slug].id
                    ),
                    ["name"]
                )
        db.session.flush()

        # 3) Attach config schemas for camera models
        # Reolink 810A
        reolink = DeviceModel.query.filter_by(name="Reolink 810A").first()
        if reolink and not reolink.get_schema("config"):
            cfg, _ = upsert(
                DeviceSchema(
                    model_id=reolink.id,
                    kind="config",
                    schema=REOLINK_810A_CONFIG,
                    version="1.0.0"
                ),
                ["model_id","kind"]
            )
            print("✅ Seeded Reolink 810A config schema")

        # Hilook IPC-B140H
        hilook = DeviceModel.query.filter_by(name="Hilook IPC-B140H").first()
        if hilook and not hilook.get_schema("config"):
            cfg, _ = upsert(
                DeviceSchema(
                    model_id=hilook.id,
                    kind="config",
                    schema=HILOOK_IPC_B140H_CONFIG,
                    version="1.0.0"
                ),
                ["model_id","kind"]
            )
            print("✅ Seeded Hilook IPC-B140H config schema")

        db.session.commit()
        print("🎉 Device catalog seed completed successfully.")


if __name__ == "__main__":
    seed()
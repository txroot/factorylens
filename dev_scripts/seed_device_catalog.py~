#!/usr/bin/env python3

# dev_scripts/seed_device_catalog.py
"""
Seed initial DeviceCategory, DeviceModel and DeviceSchema rows.

Run once (or make idempotent by default) after the tables exist.
"""
import os
import sys
import json
from pathlib import Path

# Add project root to import path
sys.path.insert(0, Path(__file__).resolve().parents[1].as_posix())

from app import create_app
from extensions import db
from models.device_category import DeviceCategory
from models.device_model    import DeviceModel
from models.device_schema   import DeviceSchema

# Define your categories (slug, label)
CATEGORIES = [
    ("camera",        "📷 Camera"),
    ("messenger",     "✉️ Messenger"),
    ("module",        "📦 Module"),
    ("iot",           "🌐 IoT Device"),
    ("logger",        "📝 Logger"),
    ("storage",       "💾 Storage Unit"),
    ("processor",     "🧠 AI Processor"),
]

# Map of category slug → list of (model name, notes)
MODELS = {
    "iot": [
        ("Shelly 1",     "Shelly 1 Wi-Fi relay"),
        ("Shelly 2",     "Shelly 2 dual relay"),
    ],
    "camera": [
        ("Reolink 810A",     "Reolink 8 MP PoE camera"),
        ("Hilook IPC-B140H", "Hilook 4 MP bullet camera"),
    ],
}

# JSON-Schema for Hilook IPC-B140H
HILOOK_SCHEMA = {
  "type": "object",
  "title": "Camera configuration",
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
    - instance: a new model instance (not yet in session)
    - uniq_attrs: list of attribute names that uniquely identify the row
    Returns: (existing_or_new_instance, True_if_inserted)
    """
    model = type(instance)
    filters = {a: getattr(instance, a) for a in uniq_attrs}
    existing = model.query.filter_by(**filters).first()

    if existing:
        # avoid touching primary key or unique attrs
        pk_cols = {c.name for c in instance.__table__.primary_key}
        for col in instance.__table__.columns.keys():
            if col in uniq_attrs or col in pk_cols:
                continue
            setattr(existing, col, getattr(instance, col))
        return existing, False

    db.session.add(instance)
    return instance, True


def seed():
    app = create_app()
    with app.app_context():
        # 1. Seed categories
        cat_map = {}
        for slug, label in CATEGORIES:
            cat, created = upsert(DeviceCategory(name=slug, label=label), ["name"])
            cat_map[slug] = cat
        db.session.flush()

        # 2. Seed models
        hilook_model = None
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
                if name.startswith("Hilook"):
                    hilook_model = mdl
        db.session.flush()

        # 3. Attach schema to Hilook model
        if hilook_model and not hilook_model.schema:
            schema = DeviceSchema(
                json_schema=HILOOK_SCHEMA,
                ui_hints={},
                version="1.0.0"
            )
            hilook_model.schema = schema
            db.session.add(schema)

        db.session.commit()
        print("Seed completed successfully.")


if __name__ == "__main__":
    seed()

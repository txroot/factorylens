#!/usr/bin/env python3
"""
Seed Shelly 2.5 MQTT model without any JSON-schema (no Config tab).
"""
import sys
from pathlib import Path
from argparse import ArgumentParser

# bootstrap so we can import your Flask app
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from extensions import db
from models.device_category import DeviceCategory
from models.device_model    import DeviceModel

def upsert(instance, uniq_cols: list[str]):
    """
    Insert or update `instance` by its unique columns.
    Returns (row, created_bool).
    """
    model = type(instance)
    filters = {c: getattr(instance, c) for c in uniq_cols}
    row = model.query.filter_by(**filters).first()
    if row:
        # copy over all non-PK, non-uniq columns
        pks = {c.name for c in row.__table__.primary_key}
        for col in row.__table__.columns.keys():
            if col in pks or col in uniq_cols:
                continue
            setattr(row, col, getattr(instance, col))
        return row, False
    db.session.add(instance)
    return instance, True

def main():
    parser = ArgumentParser(description="Seed Shelly 2.5 MQTT model (no schema)")
    parser.parse_args()

    app = create_app()
    with app.app_context():
        # 1) Ensure “iot” category
        cat, created_cat = upsert(
            DeviceCategory(name="iot", label="🔌 IoT Device"),
            ["name"]
        )
        db.session.flush()

        # 2) Ensure Shelly 2.5 MQTT model
        mdl, created_mdl = upsert(
            DeviceModel(
                name="Shelly 2.5 MQTT",
                description="Shelly 2.5 via MQTT",
                category_id=cat.id
            ),
            ["name"]
        )
        db.session.flush()

        # 3) Delete any existing schema so no Config‐tab appears
        if getattr(mdl, "schema", None):
            db.session.delete(mdl.schema)

        db.session.commit()
        print(f"{'Created' if created_cat else 'Updated'} category “{cat.name}”")
        print(f"{'Created' if created_mdl else 'Updated'} model “{mdl.name}” (schema removed)")

if __name__ == "__main__":
    main()

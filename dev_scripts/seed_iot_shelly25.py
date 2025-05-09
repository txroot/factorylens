#!/usr/bin/env python3

# dev_scripts/seed_iot_shelly25.py
"""
Seed Shelly 2.5 MQTT model and one demo Shelly 2.5 device,
with topic_prefix set to the shared “shellies” root.
"""
import sys
from pathlib import Path
from argparse import ArgumentParser
from datetime import datetime

# bootstrap so we can import your Flask app
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from extensions import db
from models.device_category import DeviceCategory
from models.device_model    import DeviceModel
from models.device          import Device

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
    parser = ArgumentParser(description="Seed Shelly 2.5 MQTT model and demo device")
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

        # 3) Remove any existing schema (no Config‐tab)
        if getattr(mdl, "schema", None):
            db.session.delete(mdl.schema)
        db.session.flush()

        # 4) Upsert a demo Shelly 2.5 device
        shelly_values = {
            "relay": {
                "0": {"state": "off", "power": {}, "energy": 0},
                "1": {"state": "off", "power": {}, "energy": 0}
            },
            "input": {"0": 0, "1": 0},
            "input_event": {
                "0": {"event": "L", "event_cnt": 1},
                "1": {"event": "S", "event_cnt": 2}
            },
            "temperature": 44.58,
            "temperature_f": 112.24,
            "overtemperature": 0,
            "temperature_status": "Normal",
            "voltage": 0.14,
            "online": True,
            "announce": {
                "id": "switch-0081F2",
                "model": "SHSW-25",
                "mac": "2462AB0081F2",
                "ip": "10.20.1.99",
                "new_fw": False,
                "fw_ver": "20230913-112234/v1.14.0-gcb84623",
                "mode": "relay"
            },
            "info": {
                "wifi_sta": {
                    "connected": True,
                    "ssid": "microlumin-wifi",
                    "ip": "10.20.1.99",
                    "rssi": -68
                },
                "cloud": None
            }
        }

        dev, created_dev = upsert(
            Device(
                name="switch-0081F2",
                mqtt_client_id="switch-0081F2",
                topic_prefix="shellies",
                device_model_id=mdl.id,
                enabled=True,
                status="online",
                last_seen=datetime.utcnow(),
                poll_interval=60,
                poll_interval_unit="sec",
                values=shelly_values,
                # point at your device icon under public/img/...
                image="img/devices/iot/SHSW-25.png",
            ),
            ["mqtt_client_id"]
        )
        db.session.flush()

        # 5) Commit everything
        db.session.commit()

        print(f"{'Created' if created_cat else 'Updated'} category “{cat.name}”")
        print(f"{'Created' if created_mdl else 'Updated'} model “{mdl.name}” (schema removed)")
        print(f"{'Created' if created_dev else 'Updated'} device “{dev.name}”")

if __name__ == "__main__":
    main()

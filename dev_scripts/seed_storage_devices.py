#!/usr/bin/env python3
"""
Seed **Storage Unit** device models & (optionally) insert a sample device for one
of the four supported back‑ends:

  1. Local file system  
  2. FTP/SFTP space  
  3. Network share (SMB/NFS)  
  4. Cloud storage (GDrive, Dropbox, OneDrive, Mega)
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
from argparse import ArgumentParser
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if PROJECT_ROOT.as_posix() not in sys.path:
    sys.path.insert(0, PROJECT_ROOT.as_posix())

from app import create_app
from extensions import db
from models.device_category import DeviceCategory
from models.device_model import DeviceModel
from models.device_schema import DeviceSchema
from models.device import Device

# ---------------------------------------------------------------------------
# Utility: INSERT or UPDATE row so we can run the script more than once.
# ---------------------------------------------------------------------------

def upsert(instance, uniq_attrs):
    model = type(instance)
    filters = {a: getattr(instance, a) for a in uniq_attrs}
    row = model.query.filter_by(**filters).first()
    if row:
        pk_cols = {c.name for c in row.__table__.primary_key}
        for col in row.__table__.columns.keys():
            if col in uniq_attrs or col in pk_cols:
                continue
            setattr(row, col, getattr(instance, col))
        return row, False
    db.session.add(instance)
    return instance, True

# ---------------------------------------------------------------------------
# JSON‑Schema definitions
# ---------------------------------------------------------------------------

LOCAL_SCHEMA = {
    "type": "object",
    "title": "Local storage configuration",
    "properties": {
        "base_path": {"type": "string", "title": "Base directory", "minLength": 1},
        "max_size_gb": {"type": "number", "title": "Max size (GB)", "default": 100},
        "retention_days": {"type": "integer", "title": "Retention (days)", "default": 30}
    },
    "required": ["base_path"]
}

FTP_SCHEMA = {
    "type": "object",
    "title": "FTP / SFTP storage configuration",
    "properties": {
        "protocol": {"type": "string", "enum": ["ftp", "sftp"], "default": "ftp"},
        "host": {"type": "string", "title": "Host", "minLength": 1},
        "port": {"type": "integer", "title": "Port", "default": 21},
        "username": {"type": "string"},
        "password": {"type": "string", "format": "password"},
        "root_path": {"type": "string", "title": "Root path", "default": "/"},
        "passive_mode": {"type": "boolean", "title": "Passive mode", "default": True},
        "ssl": {"type": "boolean", "title": "Use SSL/TLS", "default": False}
    },
    "required": ["protocol", "host"]
}

NETWORK_SCHEMA = {
    "type": "object",
    "title": "Network share (SMB/NFS) configuration",
    "properties": {
        "share_type": {"type": "string", "enum": ["smb", "nfs"], "default": "smb"},
        "path": {"type": "string", "title": "UNC / NFS path", "minLength": 1},
        "username": {"type": "string"},
        "password": {"type": "string", "format": "password"},
        "mount_options": {"type": "string", "title": "Mount options"}
    },
    "required": ["share_type", "path"]
}

CLOUD_SCHEMA = {
    "type": "object",
    "title": "Cloud storage configuration",
    "properties": {
        "provider": {
            "type": "string",
            "enum": ["gdrive", "dropbox", "onedrive", "mega"],
            "default": "gdrive"
        },
        "credentials": {
            "type": "string",
            "title": "Credentials JSON / token",
            "format": "textarea"
        },
        "root_folder": {"type": "string", "title": "Root folder", "default": ""},
        "cache_ttl": {"type": "integer", "title": "Cache TTL (seconds)", "default": 300}
    },
    "required": ["provider", "credentials"]
}

MODELS: dict[str, dict] = {
    "Local storage": LOCAL_SCHEMA,
    "FTP / SFTP storage": FTP_SCHEMA,
    "Network share": NETWORK_SCHEMA,
    "Cloud storage": CLOUD_SCHEMA,
}

CATEGORY_SLUG = "storage"
CATEGORY_LABEL = "💾 Storage Unit"

# ---------------------------------------------------------------------------
# Sample‑device helpers
# ---------------------------------------------------------------------------

def create_sample_device(cat_id: int, model: DeviceModel, opts):
    name = opts.name or f"{model.name} device"
    serial = f"STOR-{name.replace(' ', '-').upper()}"

    parameters = {}
    if model.name == "Local storage":
        parameters = {
            "base_path": opts.base_path,
            "max_size_gb": opts.max_size_gb,
            "retention_days": opts.retention_days,
        }
    elif model.name == "FTP / SFTP storage":
        parameters = {
            "protocol": opts.protocol,
            "host": opts.host,
            "port": opts.port,
            "username": opts.username,
            "password": opts.password,
            "root_path": opts.root_path,
            "passive_mode": opts.passive_mode,
            "ssl": opts.ssl,
        }
    elif model.name == "Network share":
        parameters = {
            "share_type": opts.share_type,
            "path": opts.path,
            "username": opts.username,
            "password": opts.password,
            "mount_options": opts.mount_options,
        }
    elif model.name == "Cloud storage":
        parameters = {
            "provider": opts.provider,
            "credentials": opts.credentials,
            "root_folder": opts.root_folder,
            "cache_ttl": opts.cache_ttl,
        }

    dev, created = upsert(
        Device(
            name=name,
            serial_number=serial,
            device_model_id=model.id,
            mqtt_client_id=f"{serial}-MQTT",
            topic_prefix=f"factory/storage/{serial.lower()}",
            location=opts.location,
            description=f"{model.name} created by seed script",
            enabled=True,
            poll_interval=300,
            poll_interval_unit="sec",
            status="offline",
            parameters=parameters,
            values={},
            last_response_timestamp=datetime.utcnow(),
            tags=["storage"],
        ),
        ["serial_number"],
    )
    return dev, created

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = ArgumentParser(description="Seed storage device models and (optionally) create a sample device.")
    parser.add_argument("--sample", choices=[None, "local", "ftp", "network", "cloud"], help="Insert a sample device of the given type")

    parser.add_argument("--name", help="Device name")
    parser.add_argument("--location", default="", help="Logical / physical location")
    parser.add_argument("--base-path", default="/var/factorylens/archive")
    parser.add_argument("--max-size-gb", type=float, default=100.0)
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--protocol", choices=["ftp", "sftp"], default="ftp")
    parser.add_argument("--host", default="ftp.example.com")
    parser.add_argument("--port", type=int, default=21)
    parser.add_argument("--username", default="user")
    parser.add_argument("--password", default="pass")
    parser.add_argument("--root-path", default="/")
    parser.add_argument("--passive-mode", action="store_true", default=True)
    parser.add_argument("--ssl", action="store_true", default=False)
    parser.add_argument("--share-type", choices=["smb", "nfs"], default="smb")
    parser.add_argument("--path", default="\\\\SERVER\\SHARE" if os.name == "nt" else "/mnt/nfs/share")
    parser.add_argument("--mount-options", default="")
    parser.add_argument("--provider", choices=["gdrive", "dropbox", "onedrive", "mega"], default="gdrive")
    parser.add_argument("--credentials", default="<paste‑token‑or‑json‑here>")
    parser.add_argument("--root-folder", default="")
    parser.add_argument("--cache-ttl", type=int, default=300)

    opts = parser.parse_args()

    app = create_app()
    with app.app_context():
        category, _ = upsert(DeviceCategory(name=CATEGORY_SLUG, label=CATEGORY_LABEL), ["name"])
        db.session.flush()

        model_map: dict[str, DeviceModel] = {}
        for model_name, schema in MODELS.items():
            mdl, _ = upsert(
                DeviceModel(
                    name=model_name,
                    description=f"{model_name} for storing files",
                    category_id=category.id,
                ),
                ["name"],
            )
            model_map[model_name] = mdl
            db.session.flush()

            existing_schema = mdl.get_schema("config")
            if not existing_schema:
                db.session.add(DeviceSchema(
                    model_id=mdl.id,
                    kind="config",
                    schema=schema,
                    version="1.0.0"
                ))
            else:
                existing_schema.schema = schema

        db.session.flush()

        if opts.sample:
            sample_model_name = {
                "local": "Local storage",
                "ftp": "FTP / SFTP storage",
                "network": "Network share",
                "cloud": "Cloud storage",
            }[opts.sample]
            dev, created = create_sample_device(category.id, model_map[sample_model_name], opts)
            print(f"{'Created' if created else 'Updated'} sample device: {dev.name} (ID {dev.id})")

        db.session.commit()
        print("Seed completed successfully.")

if __name__ == "__main__":
    main()

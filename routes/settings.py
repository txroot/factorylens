# routes/settings.py  (only the device parts shown)
from flask import Blueprint, render_template, jsonify, request, abort
from extensions import db
from models.device import Device

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

# ── PAGE ─────────────────────────────────────────────────────────────
@settings_bp.route("/devices")
def devices_page():
    return render_template("settings/devices.hbs")

# ── DATA SOURCE FOR BOOTSTRAP‑TABLE ──────────────────────────────────
@settings_bp.route("/devices/data")
def devices_data():
    rows = [
        {
            "id": d.id,
            "name": d.name,
            "type": d.device_type,
            "category": d.category,
            "status": d.status,
            "last_seen": d.last_seen.strftime("%Y‑%m‑%d %H:%M"),
        }
        for d in Device.query.order_by(Device.id.desc())
    ]
    return jsonify(rows)

# ── CREATE DEVICE (AJAX POST) ────────────────────────────────────────
@settings_bp.route("/devices", methods=["POST"])
def add_device():
    data = request.json or {}
    # basic validation
    required = ("name", "mqtt_client_id", "topic_prefix")
    if not all(key in data and data[key] for key in required):
        abort(400, "Missing required fields")
    dev = Device(
        name=data["name"],
        serial_number=data.get("serial_number"),
        device_type=data.get("device_type", "generic"),
        category=data.get("category", "iot"),
        mqtt_client_id=data["mqtt_client_id"],
        topic_prefix=data["topic_prefix"],
        location=data.get("location"),
        enabled=True,
    )
    db.session.add(dev)
    db.session.commit()
    return jsonify({"ok": True, "id": dev.id})

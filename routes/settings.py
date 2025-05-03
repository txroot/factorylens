# routes/settings.py  (only the device parts shown)
from flask import Blueprint, render_template, jsonify, request, abort
from extensions import db
from models.device import Device
from flask import Blueprint, render_template, jsonify, request, abort
from extensions import db
from models.device import Device

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

# ── page ──────────────────────────────────────────────────────────────
@settings_bp.route("/devices")
def devices_page():
    return render_template("settings/devices.hbs")

# ── table data ────────────────────────────────────────────────────────
@settings_bp.route("/devices/data")
def devices_data():
    rows = [
        {
            "id": d.id,
            "name": d.name,
            "type": d.device_type,
            "category": d.category,
            "status": d.status,
            "last_seen": d.last_seen.strftime("%Y-%m-%d %H:%M"),
        }
        for d in Device.query.order_by(Device.id.desc())
    ]
    return jsonify(rows)

# ── single device (GET/PUT/DELETE) ────────────────────────────────────
@settings_bp.route("/devices/<int:dev_id>", methods=["GET", "PUT", "DELETE"])
def device_item(dev_id):
    dev = Device.query.get_or_404(dev_id)

    if request.method == "GET":
        return jsonify({
            "id": dev.id,
            "name": dev.name,
            "serial_number": dev.serial_number,
            "device_type": dev.device_type,
            "category": dev.category,
            "mqtt_client_id": dev.mqtt_client_id,
            "topic_prefix": dev.topic_prefix,
            "location": dev.location,
            "poll_interval": dev.poll_interval,
            "poll_interval_unit": dev.poll_interval_unit,
            "description": dev.description,
            "parameters": dev.parameters or {}
        })

    if request.method == "PUT":
        data = request.json or {}
        for f in (
            "name", "serial_number", "device_type", "category",
            "mqtt_client_id", "topic_prefix", "location",
            "poll_interval", "poll_interval_unit", "description"
        ):
            if f in data:
                setattr(dev, f, data[f])
                
        if "parameters" in data:
            dev.parameters = data["parameters"]
        db.session.commit()
        return jsonify(ok=True)

    # DELETE
    db.session.delete(dev)
    db.session.commit()
    return jsonify(ok=True)

# ── create device ─────────────────────────────────────────────────────
@settings_bp.route("/devices", methods=["POST"])
def add_device():
    data = request.json or {}
    required = ("name", "mqtt_client_id", "topic_prefix")
    if not all(data.get(k) for k in required):
        abort(400, "Missing required fields")

    dev = Device(
        name=data["name"],
        serial_number=data.get("serial_number"),
        device_type=data.get("device_type", "generic"),
        category=data.get("category", "iot"),
        mqtt_client_id=data["mqtt_client_id"],
        topic_prefix=data["topic_prefix"],
        location=data.get("location"),
        poll_interval=data.get("poll_interval", 60),
        poll_interval_unit=data.get("poll_interval_unit", "sec"),
        description=data.get("description"),
        parameters=data.get("parameters", {}),
        enabled=True,
    )
    db.session.add(dev)
    db.session.commit()
    return jsonify(ok=True, id=dev.id)

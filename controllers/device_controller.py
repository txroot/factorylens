from flask import jsonify, request, abort
from extensions import db
from models.device import Device
from models.device_model import DeviceModel
from models.device_category import DeviceCategory
from models.device_schema import DeviceSchema


# ── DEVICE TABLE DATA ─────────────────────────────────────────────
def list_devices():
    rows = [
        {
            "id": d.id,
            "name": d.name,
            "model": d.model.name if d.model else "—",
            "category": d.model.category.name if d.model and d.model.category else "—",
            "status": d.status,
            "last_seen": d.last_seen.strftime("%Y-%m-%d %H:%M") if d.last_seen else "",
        }
        for d in Device.query.order_by(Device.id.desc())
    ]
    return jsonify(rows)


# ── SINGLE DEVICE (GET) ───────────────────────────────────────────
def get_device(dev_id):
    dev = Device.query.get_or_404(dev_id)
    return jsonify({
        "id": dev.id,
        "name": dev.name,
        "serial_number": dev.serial_number,
        "device_model_id": dev.device_model_id,
        "category_id": dev.model.category_id if dev.model else None,
        "mqtt_client_id": dev.mqtt_client_id,
        "topic_prefix": dev.topic_prefix,
        "location": dev.location,
        "poll_interval": dev.poll_interval,
        "poll_interval_unit": dev.poll_interval_unit,
        "description": dev.description,
        "parameters": dev.parameters or {},
        "enabled": dev.enabled,
        "image": dev.image,
        "qr_code": dev.qr_code,
    })


# ── CREATE DEVICE ─────────────────────────────────────────────────
def create_device():
    data = request.json or {}
    required = ("name", "mqtt_client_id", "topic_prefix", "device_model_id")
    if not all(data.get(k) for k in required):
        abort(400, "Missing required fields")

    dev = Device(
        name=data["name"],
        serial_number=data.get("serial_number"),
        device_model_id=data["device_model_id"],
        mqtt_client_id=data["mqtt_client_id"],
        topic_prefix=data["topic_prefix"],
        location=data.get("location"),
        poll_interval=data.get("poll_interval", 60),
        poll_interval_unit=data.get("poll_interval_unit", "sec"),
        description=data.get("description"),
        parameters=data.get("parameters", {}),
        enabled=data.get("enabled", True),
        image=data.get("image"),
        qr_code=data.get("qr_code"),
    )
    db.session.add(dev)
    db.session.commit()
    return jsonify(ok=True, id=dev.id)


# ── UPDATE DEVICE ────────────────────────────────────────────────
def update_device(dev_id):
    dev = Device.query.get_or_404(dev_id)
    data = request.json or {}

    fields = (
        "name", "serial_number", "device_model_id", "mqtt_client_id", "topic_prefix",
        "location", "poll_interval", "poll_interval_unit", "description",
        "image", "qr_code", "enabled"
    )
    for f in fields:
        if f in data:
            setattr(dev, f, data[f])

    if "parameters" in data:
        dev.parameters = data["parameters"]

    db.session.commit()
    return jsonify(ok=True)


# ── DELETE DEVICE ────────────────────────────────────────────────
def delete_device(dev_id):
    dev = Device.query.get_or_404(dev_id)
    db.session.delete(dev)
    db.session.commit()
    return jsonify(ok=True)


# ── GET DEVICE SCHEMA BY MODEL ───────────────────────────────────
def get_device_schema(model_id):
    model = DeviceModel.query.get_or_404(model_id)
    if model.schema:
        return jsonify(model.schema.json_schema)
    return jsonify({})


# ── LIST CATEGORIES FOR <select> ─────────────────────────────────
def list_categories():
    rows = DeviceCategory.query.order_by(DeviceCategory.name).all()
    return jsonify([{"id": c.id, "name": c.name} for c in rows])


# ── LIST MODELS FOR <select> (optionally filtered) ───────────────
def list_models():
    cat_id = request.args.get("cat", type=int)
    query = DeviceModel.query
    if cat_id:
        query = query.filter_by(category_id=cat_id)
    rows = query.order_by(DeviceModel.name).all()
    return jsonify([{"id": m.id, "name": m.name} for m in rows])

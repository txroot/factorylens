# controllers/device.py

from flask import jsonify, request, abort
from extensions import db
from datetime import datetime

from models.device import Device
from models.device_model import DeviceModel
from models.device_category import DeviceCategory
from models.device_schema import DeviceSchema
from models.camera import Camera
from models.camera_stream import CameraStream

# ── LIST DEVICES FOR TABLE ───────────────────────────────────────────
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


# ── GET A SINGLE DEVICE (for edit form) ─────────────────────────────
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


# ── CREATE A NEW DEVICE ─────────────────────────────────────────────
def create_device():
    data = request.json or {}
    required = ("name", "mqtt_client_id", "topic_prefix", "device_model_id")
    if not all(data.get(k) for k in required):
        abort(400, "Missing required fields")

    if "serial_number" in data:
        data["serial_number"] = data["serial_number"] or None

    # 1) Create Device
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
    db.session.flush()  # so dev.id is set

    # 2) If this is a camera model → create Camera + one Stream
    model = DeviceModel.query.get(dev.device_model_id)
    if model and model.category.name.lower() == "camera":
        params = data.get("parameters", {})

        if "serial_number" in cam:
            cam["serial_number"] = cam["serial_number"] or None

        # 2a) Camera record
        cam = Camera(
            device_id=dev.id,
            name=dev.name,
            serial_number=dev.serial_number,
            address=params.get("address", ""),
            port=params.get("port", 554),
            username=params.get("username"),
            password=params.get("password"),
            manufacturer=params.get("manufacturer"),
            model=params.get("model") or model.name,
            firmware=params.get("firmware"),
            description=params.get("description"),
            notes=params.get("notes"),
            snapshot_url=params.get("snapshot_url"),
            snapshot_interval_seconds=params.get("snapshot_interval_seconds", 0),
            motion_detection_enabled=params.get("motion_detection_enabled", False),
            location=dev.location,
            status="offline",
        )
        db.session.add(cam)
        db.session.flush()  # so cam.id is set

        # 2b) Build a single CameraStream
        raw_type = params.get("stream_type", "")
        # UI uses "primary" → DB expects "main"
        stype = "main" if raw_type == "primary" else raw_type

        # resolution string
        res = (params.get("resolution") or "1920x1080").split("x")
        try:
            w, h = int(res[0]), int(res[1])
        except:
            w = h = None

        stream = CameraStream(
            camera_id=cam.id,
            stream_type=stype,
            url_prefix=params.get("stream_url_suffix", ""),
            stream_suffix=None,
            full_url=None,
            resolution_w=w,
            resolution_h=h,
            fps=params.get("fps"),
            codec=None,
            bitrate_kbps=None,
            bitrate_type=None,
            is_active=True,
            description="Configured via UI",
        )
        db.session.add(stream)
        db.session.flush()

        # 2c) Make it the default
        cam.default_stream_id = stream.id

    db.session.commit()
    return jsonify(ok=True, id=dev.id)


# ── UPDATE AN EXISTING DEVICE ──────────────────────────────────────
def update_device(dev_id):
    dev = Device.query.get_or_404(dev_id)
    data = request.json or {}

    if "serial_number" in data:
        data["serial_number"] = data["serial_number"] or None

    # 1) Update the generic Device fields
    for f in (
        "name",
        "serial_number",
        "device_model_id",
        "mqtt_client_id",
        "topic_prefix",
        "location",
        "poll_interval",
        "poll_interval_unit",
        "description",
        "image",
        "qr_code",
        "enabled",
    ):
        if f in data:
            setattr(dev, f, data[f])

    if "parameters" in data:
        dev.parameters = data["parameters"]

    # 2) If camera model → sync Camera + its single Stream
    model = DeviceModel.query.get(dev.device_model_id)
    if model and model.category.name.lower() == "camera":
        params = data.get("parameters", {})

        # fetch or create Camera record
        cam = Camera.query.filter_by(device_id=dev.id).first()
        if not cam:
            cam = Camera(device_id=dev.id)
            db.session.add(cam)

        if "serial_number" in cam:
            cam["serial_number"] = cam["serial_number"] or None

        # update camera fields
        cam.name = dev.name
        cam.serial_number = params.get("serial_number", cam.serial_number)
        cam.address = params.get("address", cam.address)
        cam.port = params.get("port", cam.port)
        cam.username = params.get("username", cam.username)
        cam.password = params.get("password", cam.password)
        cam.description = params.get("description", cam.description)
        cam.notes = params.get("notes", cam.notes)
        cam.snapshot_url = params.get("snapshot_url", cam.snapshot_url)
        cam.snapshot_interval_seconds = params.get(
            "snapshot_interval_seconds", cam.snapshot_interval_seconds
        )
        cam.motion_detection_enabled = params.get(
            "motion_detection_enabled", cam.motion_detection_enabled
        )

        # ——— remove old streams safely ———
        # clear default_stream_id to avoid FK error
        cam.default_stream_id = None
        db.session.flush()
        # delete all old streams
        CameraStream.query.filter_by(camera_id=cam.id).delete()
        db.session.flush()

        # ——— recreate a single stream from form ———
        raw_type = params.get("stream_type", "")
        stype = "main" if raw_type == "primary" else raw_type
        res = (params.get("resolution") or "1920x1080").split("x")
        try:
            w, h = int(res[0]), int(res[1])
        except:
            w = h = None

        stream = CameraStream(
            camera_id=cam.id,
            stream_type=stype,
            url_prefix=params.get("stream_url_suffix", ""),
            stream_suffix=None,
            full_url=None,
            resolution_w=w,
            resolution_h=h,
            fps=params.get("fps"),
            codec=None,
            bitrate_kbps=None,
            bitrate_type=None,
            is_active=True,
            description="Configured via UI",
        )
        db.session.add(stream)
        db.session.flush()

        # mark it default
        cam.default_stream_id = stream.id

    db.session.commit()
    return jsonify(ok=True)


# ── DELETE DEVICE (cascades to Camera + Streams if your FKs are set ON DELETE CASCADE) ───
def delete_device(dev_id):
    dev = Device.query.get_or_404(dev_id)
    db.session.delete(dev)
    db.session.commit()
    return jsonify(ok=True)


# ── JSON‐SCHEMA FOR THE CONFIG TAB ─────────────────────────────────
def get_device_schema(model_id):
    model = DeviceModel.query.get_or_404(model_id)
    if model.schema:
        return jsonify(model.schema.json_schema)
    return jsonify({})


# ── HELPERS FOR SELECTS ─────────────────────────────────────────────
def list_categories():
    rows = DeviceCategory.query.order_by(DeviceCategory.name).all()
    return jsonify([{"id": c.id, "name": c.name} for c in rows])

def list_models():
    cat_id = request.args.get("cat", type=int)
    query = DeviceModel.query
    if cat_id:
        query = query.filter_by(category_id=cat_id)
    rows = query.order_by(DeviceModel.name).all()
    return jsonify([{"id": m.id, "name": m.name} for m in rows])

'''
Shelly 2.5 MQTT Schema

{
  "shellies": {
    "switch-0081F2": {
      "relay": {
        "0": {
          "state": "off",
          "power": {},
          "energy": 0
        },
        "1": {
          "state": "off",
          "power": {},
          "energy": 0
        }
      },
      "input": {
        "0": 0,
        "1": 0
      },
      "input_event": {
        "0": {
          "event": "",
          "event_cnt": 0
        },
        "1": {
          "event": "",
          "event_cnt": 0
        }
      },
      "temperature": 44.58,
      "temperature_f": 112.24,
      "overtemperature": 0,
      "temperature_status": "Normal",
      "voltage": 0.14,
      "online": true,
      "announce": {
        "id": "switch-0081F2",
        "model": "SHSW-25",
        "mac": "2462AB0081F2",
        "ip": "10.20.1.99",
        "new_fw": false,
        "fw_ver": "20230913-112234/v1.14.0-gcb84623",
        "mode": "relay"
      },
      "info": {
        "wifi_sta": {
          "connected": true,
          "ssid": "microlumin-wifi",
          "ip": "10.20.1.99",
          "rssi": -68
        },
        "cloud": null
      }
    }
  }
}

'''
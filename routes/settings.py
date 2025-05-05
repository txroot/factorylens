# routes/settings.py

from flask import Blueprint, render_template, request
from controllers.device import (
    list_devices,
    get_device,
    create_device,
    update_device,
    delete_device,
    get_device_schema,
    list_categories,
    list_models,
)

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

# ── PAGE ──────────────────────────────────────────────────────────────
@settings_bp.route("/devices")
def devices_page():
    return render_template("settings/devices.hbs")

# ── TABLE DATA ────────────────────────────────────────────────────────
@settings_bp.route("/devices/data")
def devices_data():
    return list_devices()

# ── JSON-SCHEMA FOR CONFIG TAB ────────────────────────────────────────
@settings_bp.route("/devices/schema/<int:model_id>")
def device_schema(model_id):
    return get_device_schema(model_id)

# ── SINGLE DEVICE CRUD ────────────────────────────────────────────────
@settings_bp.route("/devices/<int:dev_id>", methods=["GET", "PUT", "DELETE"])
def device_item(dev_id):
    if request.method == "GET":
        return get_device(dev_id)
    if request.method == "PUT":
        return update_device(dev_id)
    return delete_device(dev_id)

# ── CREATE DEVICE ─────────────────────────────────────────────────────
@settings_bp.route("/devices", methods=["POST"])
def add_device():
    return create_device()

# ── DEVICE CATEGORY / MODEL LOOKUPS ───────────────────────────────────
@settings_bp.route("/device-categories")
def device_categories():
    return list_categories()

@settings_bp.route("/device-models")
def device_models():
    return list_models()

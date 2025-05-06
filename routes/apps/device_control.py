# routes/apps/device_control.py
from flask import Blueprint, render_template, jsonify, request
from controllers.apps.device_control import list_shelly_devices, publish_relay
from models.device import Device

apps_ctrl_bp = Blueprint("apps_device_control", __name__, url_prefix="/apps")


# ── page ────────────────────────────────────────────────────────────────
@apps_ctrl_bp.route("/device-control")
def device_control():
    devices = list_shelly_devices()
    return render_template("apps/device-control.hbs", devices=devices)


# ── ajax: current values ────────────────────────────────────────────────
@apps_ctrl_bp.route("/device-control/state/<int:dev_id>")
def device_state(dev_id):
    dev = Device.query.get_or_404(dev_id)
    return jsonify(dev.values or {})


# ── ajax: toggle relay ──────────────────────────────────────────────────
@apps_ctrl_bp.route("/device-control/relay/<int:dev_id>/<int:ch>", methods=["POST"])
def device_relay(dev_id, ch):
    dev      = Device.query.get_or_404(dev_id)
    turn_on  = bool((request.get_json(silent=True) or {}).get("on"))
    publish_relay(dev, ch, turn_on)
    return ("", 204)

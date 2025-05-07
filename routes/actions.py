# routes/actions.py
from models.device import Device
from flask import Blueprint, render_template, request, jsonify
from controllers.actions import (
    list_actions, get_action, create_action, update_action,
    delete_action, ensure_agent_exists
)

actions_bp = Blueprint("actions", __name__, url_prefix="/actions")

# ── PAGE ───────────────────────────────────────────────────────────────
@actions_bp.route("/", endpoint="list")
def actions_page():
    agent_ok = ensure_agent_exists()
    return render_template("settings/actions.hbs", agent_ok=agent_ok)

# ── TABLE DATA ────────────────────────────────────────────────────────
@actions_bp.route("/data")
def actions_data():
    return list_actions()

# ── SINGLE ACTION CRUD ────────────────────────────────────────────────
@actions_bp.route("/<int:action_id>", methods=["GET", "PUT", "DELETE"])
def action_item(action_id):
    if request.method == "GET":
        return get_action(action_id)
    if request.method == "PUT":
        return update_action(action_id)
    return delete_action(action_id)

# ── CREATE ACTION ─────────────────────────────────────────────────────
@actions_bp.route("/", methods=["POST"])
def add_action():
    return create_action()

# ── DEVICE ACTION SCHEMA ───────────────────────────────────────────────
@actions_bp.route("/schema/<int:device_id>")
def action_schema(device_id):
    """
    Return the Device‑specific action schema so the front‑end can build
    drop‑downs.  Empty JSON when no schema exists.
    """
    dev = Device.query.get_or_404(device_id)
    return jsonify(dev.model.action_schema.schema
                   if dev.model.action_schema else {})
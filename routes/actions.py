# routes/actions.py
# ════════════════════════════════════════════════════════════════════════════
#  “Actions” feature – UI page + AJAX helpers + CRUD
#  --------------------------------------------------------------------------
#  ▸ /actions/                     – HTML page with the table / modal builder
#  ▸ /actions/data                 – JSON rows for the table
#  ▸ /actions/<id>                 – GET PUT DELETE single action
#  ▸ /actions/                     – POST  create new action
#  ▸ /actions/schema/<device_id>   – JSON schema for that device (topics + cmds)
#  ▸ /actions/topics/<device_id>   – Convenience: list of topic strings only
# ════════════════════════════════════════════════════════════════════════════
from __future__ import annotations

from flask import Blueprint, render_template, request, jsonify, abort
from models.device         import Device
from controllers.actions   import (
    list_actions, get_action, create_action,
    update_action, delete_action, ensure_agent_exists
)

actions_bp = Blueprint("actions", __name__, url_prefix="/actions")


# ────────────────────────────────────────────────────────────────────
#  PAGE
# ────────────────────────────────────────────────────────────────────
@actions_bp.route("/", endpoint="list")
def actions_page():
    """Render the Actions list (or empty‑state when no Action‑Agent)."""
    return render_template(
        "settings/actions.hbs",
        agent_ok=ensure_agent_exists()
    )


# ────────────────────────────────────────────────────────────────────
#  DATATABLE JSON
# ────────────────────────────────────────────────────────────────────
@actions_bp.route("/data")
def actions_data():
    return list_actions()


# ────────────────────────────────────────────────────────────────────
#  CRUD: single Action
# ────────────────────────────────────────────────────────────────────
@actions_bp.route("/<int:action_id>", methods=["GET", "PUT", "DELETE"])
def action_item(action_id: int):
    if request.method == "GET":
        return get_action(action_id)
    if request.method == "PUT":
        return update_action(action_id)
    return delete_action(action_id)          # DELETE


@actions_bp.route("/", methods=["POST"])
def add_action():
    return create_action()


# ────────────────────────────────────────────────────────────────────
#  DEVICE‑AWARE HELPER ENDPOINTS (used by the Action‑builder modal)
# ────────────────────────────────────────────────────────────────────
@actions_bp.route("/schema/<int:device_id>")
def action_schema(device_id: int):
    """
    Return the device‑specific **topic‑schema** (kind ='topic') so the
    front‑end can populate drop‑downs and validate values.

    If a model has **no** topic schema defined we return `{}`.
    """
    dev = Device.query.get_or_404(device_id)
    schema_row = dev.model.get_schema("topic")
    return jsonify(schema_row.schema if schema_row else {})


@actions_bp.route("/topics/<int:device_id>")
def list_topics_for_device(device_id: int):
    """
    Convenience helper: return a **flat list** of topic strings for the
    selected device – easier for quick populating a <select>.
    """
    dev = Device.query.get_or_404(device_id)
    schema_row = dev.model.get_schema("topic")
    if not schema_row:
        return jsonify([])

    topics = list((schema_row.schema or {}).get("topics", {}).keys())
    return jsonify(sorted(topics))

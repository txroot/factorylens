# controllers/actions.py
from flask import jsonify, request, abort
from extensions import db
from models.actions import Action
from models.device import Device
from models.device_model import DeviceModel
from models.device_category import DeviceCategory

# ---------- helper: make sure an Action Agent device exists ----------
AGENT_MODEL_NAME = "Action Agent"   # model name for the action agent device

def ensure_agent_exists():
    """Return **True** only when there is *exactly one* enabled Action‑Agent
    **and** it is online.

    ‑ enabled flag  = True
    ‑ status column = 'online'
    """
    cat = DeviceCategory.query.filter_by(name="processor").first()
    if not cat:
        return False

    model = DeviceModel.query.filter_by(
        name=AGENT_MODEL_NAME,
        category_id=cat.id
    ).first()
    if not model:
        return False

    # one active agent (enabled & online)
    agent = Device.query.filter_by(
        device_model_id=model.id,
        enabled=True,
        status="online"
    ).first()
    return bool(agent)

# ---------- CRUD ------------------------------------------------------
def list_actions():
    rows = [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description or "",
            "enabled": a.enabled,
        }
        for a in Action.query.order_by(Action.id.desc())
    ]
    return jsonify(rows)

def get_action(action_id):
    a = Action.query.get_or_404(action_id)
    return jsonify({
        "id": a.id,
        "name": a.name,
        "description": a.description,
        "trigger": a.trigger,
        "result": a.result,
        "enabled": a.enabled,
    })

def create_action():
    if not ensure_agent_exists():
        abort(412, "No Action Agent configured")

    data = request.json or {}
    if not data.get("name") or not data.get("trigger") or not data.get("result"):
        abort(400, "Missing required fields")

    # Enforce unique name
    if Action.query.filter_by(name=data["name"]).first():
        abort(409, "Action with that name exists")

    a = Action(
        name=data["name"],
        description=data.get("description"),
        trigger=data["trigger"],
        result=data["result"],
        enabled=data.get("enabled", True),
    )
    db.session.add(a)
    db.session.commit()
    return jsonify(ok=True, id=a.id)

def update_action(action_id):
    a = Action.query.get_or_404(action_id)
    data = request.json or {}
    for f in ("name", "description", "trigger", "result", "enabled"):
        if f in data:
            setattr(a, f, data[f])
    db.session.commit()
    return jsonify(ok=True)

def delete_action(action_id):
    a = Action.query.get_or_404(action_id)
    db.session.delete(a)
    db.session.commit()
    return jsonify(ok=True)

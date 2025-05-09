# controllers/actions.py
# ════════════════════════════════════════════════════════════════════════
#  Light‑weight CRUD + helpers for the “Actions” feature
#  – validates trigger / result against the Device‑Model topic‑schema
# ════════════════════════════════════════════════════════════════════════
from __future__ import annotations

from flask import jsonify, request, abort
from extensions import db
from models.actions import Action
from models.device           import Device
from models.device_model     import DeviceModel
from models.device_category  import DeviceCategory


# ────────────────────────────────────────────────────────────────────
#  0. Utilities
# ────────────────────────────────────────────────────────────────────
AGENT_MODEL_NAME = "Action Agent"                 # the sole agent model

def ensure_agent_exists() -> bool:
    """
    There must be **one** enabled *Action Agent* device *and* it must be online.
    Return *True* when everything is OK.
    """
    cat = DeviceCategory.query.filter_by(name="processor").first()
    if not cat:
        return False

    mdl = DeviceModel.query.filter_by(
        name=AGENT_MODEL_NAME, category_id=cat.id).first()
    if not mdl:
        return False

    agent = Device.query.filter_by(
        device_model_id=mdl.id, enabled=True, status="online").first()
    return bool(agent)

VALID_BRANCHES = ('success', 'error')

def _validate_node(node: dict, is_trigger=False, is_eval=False):
    # triggers: match source/io
    if is_trigger:
        _validate_trigger(node)
    # THEN: simple command
    elif not is_eval:
        _validate_result(node)
    # EVAL branches: same as commands but require branch field
    else:
        if node.get('branch') not in VALID_BRANCHES:
            abort(400, f"Invalid branch {node.get('branch')}")
        _validate_result(node)

# --------------------------------------------------------------------
#  Helpers for schema‑aware validation
# --------------------------------------------------------------------
def _topic_schema(device_id: int) -> dict:
    dev = Device.query.get(device_id)
    if not dev:
        abort(400, f"Device ID {device_id} does not exist")

    row = dev.model.get_schema("topic")
    return row.schema if row else {}


def _validate_trigger(trg: dict):
    """Ensure trigger {device_id, topic, value …} matches the model schema."""
    dev_id = trg.get("device_id")
    topic  = trg.get("topic")
    if dev_id is None or topic is None:
        abort(400, "Trigger needs device_id and topic")

    sch = _topic_schema(dev_id)
    meta = (sch.get("topics") or {}).get(topic)
    if not meta:
        abort(400, f"Topic “{topic}” not allowed for that device")

    # value & comparator checks
    v = str(trg.get("value", ""))
    if meta["type"] in ("enum", "bool"):
        allowed = meta["values"] if meta["type"] == "enum" else ["true", "false", "1", "0"]
        if v not in map(str, allowed):
            abort(400, f"Value “{v}” is not valid for topic {topic}")
    elif meta["type"] == "number":
        try:
            float(v)
        except ValueError:
            abort(400, f"Numeric value required for topic {topic}")


def _validate_result(res: dict):
    """Ensure result {device_id, topic, command …} is valid."""
    dev_id = res.get("device_id")
    topic  = res.get("topic")
    if dev_id is None or topic is None:
        abort(400, "Result needs device_id and topic")

    sch = _topic_schema(dev_id)
    meta = (sch.get("command_topics") or {}).get(topic)
    if not meta:
        abort(400, f"Command topic “{topic}” not allowed for that device")

    cmd = str(res.get("command", ""))
    if meta["type"] == "enum" and cmd not in meta["values"]:
        abort(400, f"Command “{cmd}” not valid for topic {topic}")


# ────────────────────────────────────────────────────────────────────
#  1. Read – list / single
# ────────────────────────────────────────────────────────────────────
def list_actions():
    rows = [
        {"id": a.id, "name": a.name,
         "description": a.description or "", "enabled": a.enabled}
        for a in Action.query.order_by(Action.id.desc())
    ]
    return jsonify(rows)


def get_action(action_id: int):
    a = Action.query.get_or_404(action_id)
    
    action = {
        "id":          a.id,
        "name":        a.name,
        "description": a.description,
        "chain":       a.chain,
        "enabled":     a.enabled,
    }

    print("Action: ", action)

    return jsonify(action)


# ────────────────────────────────────────────────────────────────────
#  2. Create
# ────────────────────────────────────────────────────────────────────
def create_action():
    if not ensure_agent_exists():
        abort(412, "No Action Agent device is enabled & online")

    data = request.get_json(silent=True) or {}
    # basic sanity
    for f in ('name','trigger','result','evaluate'):
        if f not in data:
            abort(400, f"{f} is required")

    # unique name check
    if Action.query.filter_by(name=data['name'].strip()).first():
        abort(409, "An Action with that name already exists")

    trg = data['trigger']
    res = data['result']
    ev  = data['evaluate']

    # validate individual pieces
    _validate_trigger(trg)
    _validate_result(res)
    # build core chain
    chain = []
    # IF node
    chain.append({
        'device_id': trg['device_id'],
        'source':    'io',
        'topic':     trg['topic'],
        'cmp':       trg.get('cmp','=='),
        'match':     {'value': trg.get('value','')}
    })
    # THEN node
    chain.append({
        'device_id':   res['device_id'],
        'command':     res['command'],
        'topic':       res['topic'],
        'ignore_input':bool(res.get('ignore_input',False))
    })
    # EVALUATE branches
    mode = ev.get('mode','ignore')
    if mode in ('success','both') and ev.get('success'):
        sb = ev['success']
        _validate_result(sb)
        chain.append({**sb, 'branch':'success'})
    if mode in ('error','both') and ev.get('error'):
        eb = ev['error']
        _validate_result(eb)
        chain.append({**eb, 'branch':'error'})

    # persist
    a = Action(
        name=data['name'].strip(),
        description=data.get('description','').strip(),
        chain=chain,
        enabled=bool(data.get('enabled',True))
    )
    db.session.add(a)
    db.session.commit()
    return jsonify(ok=True, id=a.id)


# ────────────────────────────────────────────────────────────────────
#  3. Update
# ────────────────────────────────────────────────────────────────────
def update_action(action_id: int):
    a    = Action.query.get_or_404(action_id)
    data = request.get_json(silent=True) or {}

    if 'name' in data and data['name'].strip() != a.name:
        if Action.query.filter_by(name=data['name'].strip()).first():
            abort(409, "Another Action already has that name")
        a.name = data['name'].strip()
    if 'description' in data:
        a.description = data['description'].strip()
    if 'enabled' in data:
        a.enabled = bool(data['enabled'])
    if any(k in data for k in ('trigger','result','evaluate')):
        # rebuild the chain exactly as in create_action
        # (reuse the same steps as above)
        ...  # repeat chain-building logic
        a.chain = new_chain

    db.session.commit()
    return jsonify(ok=True)


# ────────────────────────────────────────────────────────────────────
#  4. Delete
# ────────────────────────────────────────────────────────────────────
def delete_action(action_id: int):
    a = Action.query.get_or_404(action_id)
    db.session.delete(a)
    db.session.commit()
    return jsonify(ok=True)


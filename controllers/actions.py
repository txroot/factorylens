from __future__ import annotations

from flask import jsonify, request, abort
from extensions import db
from models.actions       import Action
from models.device        import Device
from models.device_model  import DeviceModel
from models.device_category import DeviceCategory
from controllers.actions_handler import get_action_manager

AGENT_MODEL_NAME = "Action Agent"
VALID_BRANCHES   = ('success', 'error')


# ────────────────────────────────────────────────────────────────────
#  Utilities
# ────────────────────────────────────────────────────────────────────
def ensure_agent_exists() -> bool:
    cat = DeviceCategory.query.filter_by(name="processor").first()
    if not cat:
        return False
    mdl = DeviceModel.query.filter_by(
        name=AGENT_MODEL_NAME, category_id=cat.id
    ).first()
    if not mdl:
        return False
    agent = Device.query.filter_by(
        device_model_id=mdl.id, enabled=True, status="online"
    ).first()
    return bool(agent)


# ────────────────────────────────────────────────────────────────────
#  Schema Helpers
# ────────────────────────────────────────────────────────────────────
def _topic_schema(device_id: int) -> dict:
    dev = Device.query.get(device_id)
    if not dev:
        abort(400, f"Device ID {device_id} does not exist")
    row = dev.model.get_schema("topic")
    return row.schema if row else {}

def _validate_trigger(trg: dict):
    dev_id = trg.get("device_id")
    topic  = trg.get("topic")
    if dev_id is None or topic is None:
        abort(400, "Trigger needs device_id and topic")
    sch  = _topic_schema(dev_id)
    meta = (sch.get("topics") or {}).get(topic)
    if not meta:
        abort(400, f"Topic “{topic}” not allowed for that device")
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
    dev_id = res.get("device_id")
    topic  = res.get("topic")
    if dev_id is None or topic is None:
        abort(400, "Result needs device_id and topic")
    sch  = _topic_schema(dev_id)
    meta = (sch.get("command_topics") or {}).get(topic)
    if not meta:
        abort(400, f"Command topic “{topic}” not allowed for that device")
    cmd = str(res.get("command", ""))
    if meta["type"] == "enum" and cmd not in meta["values"]:
        abort(400, f"Command “{cmd}” not valid for topic {topic}")

def _unpack_time(source: dict, field: str, target: dict):
    """
    Safely read a time-like field. Accepts either:
      - source[field] = { "value": X, "unit": U }
      - or source[field] = X and source[f"{field}_unit"] = U
    Always sets target[field] and target[f"{field}_unit"].
    """
    raw = source.get(field)
    if isinstance(raw, dict):
        # old style
        v = raw.get("value", 0)
        u = raw.get("unit", "sec")
    else:
        # flat style
        v = raw or 0
        u = source.get(f"{field}_unit", "sec")
    target[field]         = v
    target[f"{field}_unit"] = u

# ────────────────────────────────────────────────────────────────────
#  CRUD
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
    return jsonify({
        "id":          a.id,
        "name":        a.name,
        "description": a.description,
        "chain":       a.chain,
        "enabled":     a.enabled,
    })


def create_action():
    if not ensure_agent_exists():
        abort(412, "No Action Agent device is enabled & online")

    data = request.get_json(silent=True) or {}
    for field in ('name', 'trigger', 'result', 'evaluate'):
        if field not in data:
            abort(400, f"{field} is required")

    base_name = data['name'].strip()
    new_name = base_name
    counter = 1

    # Keep appending " Copy", " Copy 2", etc., until a unique name is found
    while Action.query.filter_by(name=new_name).first():
        counter += 1
        if counter == 2:
            new_name = f"{base_name} Copy"
        else:
            new_name = f"{base_name} Copy {counter - 1}"

    data['name'] = new_name

    trg = data['trigger']
    res = data['result']
    ev  = data['evaluate']

    _validate_trigger(trg)
    _validate_result(res)

    schema_map = _topic_schema(trg['device_id'])
    chain = []

    # IF node
    tmeta = schema_map.get("topics", {}).get(trg['topic'], {})
    node_if = {
        "device_id": trg['device_id'],
        "source":    "io",
        "topic":     trg['topic'],
        "cmp":       trg.get('cmp','=='),
        "match":     {"value": trg.get('value','')},
        "poll_topic": trg.get("poll_topic", ""),
        "poll_payload": tmeta.get("poll_payload","")
    }
    _unpack_time(trg, "poll_interval", node_if)
    chain.append(node_if)

    # THEN node
    cmeta = schema_map.get("command_topics", {}).get(res['topic'], {})
    node_then = {
        "device_id":   res['device_id'],
        "topic":       res['topic'],
        "command":     res['command'],
        "ignore_input": bool(res.get('ignore_input', False)),
        "result_topic": res.get("result_topic", ""),
        "result_payload": cmeta.get("result_payload", {})
    }
    _unpack_time(res, "timeout", node_then)
    chain.append(node_then)

    # EVALUATE
    mode = ev.get('mode','ignore')
    if mode in ('success','both') and ev.get('success'):
        sb = ev['success']
        _validate_result(sb)
        sb_meta  = schema_map.get("command_topics",{}).get(sb['topic'],{})
        sb_node = {
            **sb,
            "branch":         "success",
            "result_topic":   sb.get("result_topic",""),
            "result_payload": sb_meta.get("result_payload",{})
        }
        _unpack_time(sb, "timeout", sb_node)
        chain.append(sb_node)

    if mode in ('error','both') and ev.get('error'):
        eb = ev['error']
        _validate_result(eb)
        eb_meta  = schema_map.get("command_topics",{}).get(eb['topic'],{})
        eb_node = {
            **eb,
            "branch":         "error",
            "result_topic":   eb.get("result_topic",""),
            "result_payload": eb_meta.get("result_payload",{})
        }
        _unpack_time(eb, "timeout", eb_node)
        chain.append(eb_node)

    a = Action(
        name=data['name'].strip(),
        description=data.get('description','').strip(),
        chain=chain,
        enabled=bool(data.get('enabled',True))
    )
    db.session.add(a)
    db.session.commit()

    # --- hot-reload into running ActionManager as a wrapper, not raw model ---
    from controllers.actions_handler import get_action_manager, ActionWrapper
    mgr = get_action_manager()
    if mgr:
        if a.enabled:
            mgr.actions[a.id] = ActionWrapper(a)
            # re-subscribe to any new topics
            mgr._install_subscriptions()
        else:
            mgr.actions.pop(a.id, None)

    return jsonify(ok=True, id=a.id)


def update_action(action_id: int):
    a    = Action.query.get_or_404(action_id)
    data = request.get_json(silent=True) or {}

    print(f"Update action {action_id}: {data}")

    if 'name' in data and data['name'].strip() != a.name:
        if Action.query.filter_by(name=data['name'].strip()).first():
            abort(409, "Another Action already has that name")
        a.name = data['name'].strip()
    if 'description' in data:
        a.description = data['description'].strip()
    if 'enabled' in data:
        a.enabled = bool(data['enabled'])

    if any(k in data for k in ('trigger','result','evaluate')):
        trg = data['trigger']
        res = data['result']
        ev  = data['evaluate']

        _validate_trigger(trg)
        _validate_result(res)
        schema_map = _topic_schema(trg['device_id'])
        new_chain = []

        tmeta = schema_map.get("topics", {}).get(trg['topic'], {})
        node_if = {
            "device_id": trg['device_id'],
            "source":    "io",
            "topic":     trg['topic'],
            "cmp":       trg.get('cmp','=='),
            "match":     {"value": trg.get('value','')},
            "poll_topic": trg.get("poll_topic", ""),
            "poll_payload": tmeta.get("poll_payload","")
        }
        _unpack_time(trg, "poll_interval", node_if)
        new_chain.append(node_if)

        cmeta = schema_map.get("command_topics", {}).get(res['topic'], {})
        node_then = {
            "device_id":   res['device_id'],
            "topic":       res['topic'],
            "command":     res['command'],
            "ignore_input": bool(res.get('ignore_input', False)),
            "result_topic": res.get("result_topic", ""),
            "result_payload": cmeta.get("result_payload", {})
        }
        _unpack_time(res, "timeout", node_then)
        new_chain.append(node_then)

        mode = ev.get('mode','ignore')
        if mode in ('success','both') and ev.get('success'):
            sb = ev['success']
            _validate_result(sb)
            sb_meta  = schema_map.get("command_topics",{}).get(sb['topic'],{})
            sb_node = {
                **sb,
                "branch":         "success",
                "result_topic":   sb.get("result_topic",""),
                "result_payload": sb_meta.get("result_payload",{})
            }
            _unpack_time(sb, "timeout", sb_node)
            new_chain.append(sb_node)

        if mode in ('error','both') and ev.get('error'):
            eb = ev['error']
            _validate_result(eb)
            eb_meta  = schema_map.get("command_topics",{}).get(eb['topic'],{})
            eb_node = {
                **eb,
                "branch":         "error",
                "result_topic":   eb.get("result_topic",""),
                "result_payload": eb_meta.get("result_payload",{})
            }
            _unpack_time(eb, "timeout", eb_node)
            new_chain.append(eb_node)

        a.chain = new_chain

    db.session.commit()

    # --- update live ActionManager as a wrapper, not raw model ---
    from controllers.actions_handler import get_action_manager, ActionWrapper
    mgr = get_action_manager()
    if mgr:
        if a.enabled:
            mgr.actions[a.id] = ActionWrapper(a)
            mgr._install_subscriptions()
        else:
            mgr.actions.pop(a.id, None)

    return jsonify(ok=True)


def delete_action(action_id: int):
    a = Action.query.get_or_404(action_id)
    db.session.delete(a)
    db.session.commit()

    # --- remove from live ActionManager ---
    mgr = get_action_manager()
    if mgr:
        mgr.actions.pop(action_id, None)

    return jsonify(ok=True)

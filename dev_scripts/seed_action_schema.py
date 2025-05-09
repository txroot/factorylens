# dev_scripts/seed_action_schema.py

import os
import sys

# ensure project root (one level up) is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models.device_model import DeviceModel
from models.device_schema import DeviceSchema

# Define the full Shelly 2.5 schema
SHELLY_SCHEMA = {
    "topics": {
        "input/0": {"label": "Input 0", "type": "bool", "true": 1, "false": 0},
        "input/1": {"label": "Input 1", "type": "bool", "true": 1, "false": 0},
        "input_event/0/event": {
            "label": "Button 0 Event", "type": "enum",
            "values": ["S", "L"],
            "display": {"S": "Short Press", "L": "Long Press"}
        },
        "input_event/1/event": {
            "label": "Button 1 Event", "type": "enum",
            "values": ["", "S", "L"],
            "display": {"": "None", "S": "Short Press", "L": "Long Press"}
        },
        "relay/0": {"label": "Relay 0", "type": "enum", "values": ["on", "off"]},
        "relay/0/power": {
            "label": "Relay 0 Power", "type": "number", "units": "W",
            "range": [0, None], "comparators": ["<", "<=", "==", "!=", ">=", ">"]
        },
        "relay/0/energy": {"label": "Relay 0 Energy", "type": "number", "units": "Wh"},
        "relay/1": {"label": "Relay 1", "type": "enum", "values": ["on", "off"]},
        "relay/1/power": {
            "label": "Relay 1 Power", "type": "number", "units": "W",
            "range": [0, None], "comparators": ["<", "<=", "==", "!=", ">=", ">"]
        },
        "relay/1/energy": {"label": "Relay 1 Energy", "type": "number", "units": "Wh"},
        "temperature": {
            "label": "Temperature (°C)", "type": "number", "units": "°C",
            "range": [-50, 150], "comparators": ["<", "<=", "==", "!=", ">=", ">"]
        },
        "temperature_f": {
            "label": "Temperature (°F)", "type": "number", "units": "°F",
            "range": [-58, 302]
        },
        "temperature_status": {
            "label": "Temperature Status", "type": "enum",
            "values": ["Normal", "Overheated"]
        },
        "overtemperature": {"label": "Overtemperature", "type": "bool", "true": 1, "false": 0},
        "voltage": {"label": "Voltage", "type": "number", "units": "V"},
        "online": {"label": "Device Online", "type": "bool"},
        "info/wifi_sta/rssi": {"label": "WiFi RSSI", "type": "number", "units": "dBm"}
    },
    "command_topics": {
        "relay/0/command": {"label": "Relay 0 Command", "type": "enum", "values": ["on", "off"]},
        "relay/1/command": {"label": "Relay 1 Command", "type": "enum", "values": ["on", "off"]}
    }
}

app = create_app()
with app.app_context():
    shelly_mdl = DeviceModel.query.filter_by(name='Shelly 2.5 MQTT').first()

    if not shelly_mdl:
        print("Device model 'Shelly 2.5 MQTT' not found ❌")
        sys.exit(1)

    topic_schema = DeviceSchema.query.filter_by(model_id=shelly_mdl.id, kind='topic').first()

    if not topic_schema:
        topic_schema = DeviceSchema(model_id=shelly_mdl.id, kind='topic', schema=SHELLY_SCHEMA)
        db.session.add(topic_schema)
        print("Created new topic schema for Shelly 2.5 MQTT ✅")
    else:
        topic_schema.schema = SHELLY_SCHEMA
        print("Updated existing topic schema for Shelly 2.5 MQTT 🔄")

    db.session.commit()
    print("Shelly 2.5 MQTT topic schema committed to DB 🗃")

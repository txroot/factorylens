# dev_scripts/seed_shelly25_action_schema.py

import os
import sys

# ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models.device_model  import DeviceModel
from models.device_schema import DeviceSchema

# Shelly 2.5 “action” schema:
# — topics include default poll_interval (0 = no polling) and poll_topic
# — command_topics include default timeout (in seconds)
SHELLY_ACTION_SCHEMA = {
    "topics": {
        "input/0": {
            "label":               "Input 0",
            "type":                "bool",
            "true":                1,
            "false":               0,
            "poll_interval":       0,
            "poll_interval_unit":  "sec",
            "poll_topic":          ""
        },
        "input/1": {
            "label":               "Input 1",
            "type":                "bool",
            "true":                1,
            "false":               0,
            "poll_interval":       0,
            "poll_interval_unit":  "sec",
            "poll_topic":          ""
        },
        "input_event/0/event": {
            "label":               "Button 0 Event",
            "type":                "enum",
            "values":              ["S","L"],
            "display":             {"S":"Short Press","L":"Long Press"},
            "poll_interval":       0,
            "poll_interval_unit":  "sec",
            "poll_topic":          ""
        },
        "input_event/1/event": {
            "label":               "Button 1 Event",
            "type":                "enum",
            "values":              ["","S","L"],
            "display":             {"":"None","S":"Short Press","L":"Long Press"},
            "poll_interval":       0,
            "poll_interval_unit":  "sec",
            "poll_topic":          ""
        },
        "relay/0": {
            "label":               "Relay 0",
            "type":                "enum",
            "values":              ["on","off"],
            "poll_interval":       0,
            "poll_interval_unit":  "sec",
            "poll_topic":          ""
        },
        "relay/0/power": {
            "label":               "Relay 0 Power",
            "type":                "number",
            "units":               "W",
            "range":               [0,None],
            "comparators":         ["<","<=","==","!=",">=",">"],
            "poll_interval":       60,
            "poll_interval_unit":  "sec",
            "poll_topic":          "relay/0/power"
        },
        "relay/0/energy": {
            "label":               "Relay 0 Energy",
            "type":                "number",
            "units":               "Wh",
            "poll_interval":       60,
            "poll_interval_unit":  "sec",
            "poll_topic":          "relay/0/energy"
        },
        "relay/1": {
            "label":               "Relay 1",
            "type":                "enum",
            "values":              ["on","off"],
            "poll_interval":       0,
            "poll_interval_unit":  "sec",
            "poll_topic":          ""
        },
        "relay/1/power": {
            "label":               "Relay 1 Power",
            "type":                "number",
            "units":               "W",
            "range":               [0,None],
            "comparators":         ["<","<=","==","!=",">=",">"],
            "poll_interval":       60,
            "poll_interval_unit":  "sec",
            "poll_topic":          "relay/1/power"
        },
        "relay/1/energy": {
            "label":               "Relay 1 Energy",
            "type":                "number",
            "units":               "Wh",
            "poll_interval":       60,
            "poll_interval_unit":  "sec",
            "poll_topic":          "relay/1/energy"
        },
        "temperature": {
            "label":               "Temperature (°C)",
            "type":                "number",
            "units":               "°C",
            "range":               [-50,150],
            "comparators":         ["<","<=","==","!=",">=",">"],
            "poll_interval":       60,
            "poll_interval_unit":  "sec",
            "poll_topic":          "temperature"
        },
        "temperature_f": {
            "label":               "Temperature (°F)",
            "type":                "number",
            "units":               "°F",
            "range":               [-58,302],
            "poll_interval":       60,
            "poll_interval_unit":  "sec",
            "poll_topic":          "temperature_f"
        },
        "temperature_status": {
            "label":               "Temperature Status",
            "type":                "enum",
            "values":              ["Normal","Overheated"],
            "poll_interval":       60,
            "poll_interval_unit":  "sec",
            "poll_topic":          "temperature_status"
        },
        "overtemperature": {
            "label":               "Overtemperature",
            "type":                "bool",
            "true":                1,
            "false":               0,
            "poll_interval":       60,
            "poll_interval_unit":  "sec",
            "poll_topic":          "overtemperature"
        },
        "voltage": {
            "label":               "Voltage",
            "type":                "number",
            "units":               "V",
            "poll_interval":       60,
            "poll_interval_unit":  "sec",
            "poll_topic":          "voltage"
        },
        "online": {
            "label":               "Device Online",
            "type":                "bool",
            "poll_interval":       30,
            "poll_interval_unit":  "sec",
            "poll_topic":          "online"
        },
        "info/wifi_sta/rssi": {
            "label":               "WiFi RSSI",
            "type":                "number",
            "units":               "dBm",
            "poll_interval":       60,
            "poll_interval_unit":  "sec",
            "poll_topic":          "info/wifi_sta/rssi"
        }
    },
    "command_topics": {
        "relay/0/command": {
            "label":         "Relay 0 Command",
            "type":          "enum",
            "values":        ["on","off"],
            "timeout":       10,
            "timeout_unit":  "sec",
            "result_topic":  "relay/0"
        },
        "relay/1/command": {
            "label":         "Relay 1 Command",
            "type":          "enum",
            "values":        ["on","off"],
            "timeout":       10,
            "timeout_unit":  "sec",
            "result_topic":  "relay/1"
        }
    }
}

def main():
    app = create_app()
    with app.app_context():
        mdl = DeviceModel.query.filter_by(name="Shelly 2.5 MQTT").first()
        if not mdl:
            print("❌ Shelly 2.5 MQTT model not found")
            sys.exit(1)

        # upsert a single DeviceSchema row of kind='topic'
        row = DeviceSchema.query.filter_by(model_id=mdl.id, kind="topic").first()
        if row:
            row.schema = SHELLY_ACTION_SCHEMA
            print("🔄 Updated Shelly 2.5 action schema")
        else:
            row = DeviceSchema(
                model_id=mdl.id,
                kind="topic",
                schema=SHELLY_ACTION_SCHEMA
            )
            db.session.add(row)
            print("✅ Created Shelly 2.5 action schema")

        db.session.commit()
        print("🎉 Shelly 2.5 action schema committed")

if __name__ == "__main__":
    main()

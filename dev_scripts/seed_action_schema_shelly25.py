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
# — command_topics include default timeout
# — tooltips, hints, explanations

SHELLY_ACTION_SCHEMA = {
    "topics": {
        "input/0": {
            "label":              "Input 0",
            "tooltip":            "Digital input channel 0 state",
            "hint":               "True when the input is active (e.g. button pressed)",
            "explanation":        "Reports the boolean state of input 0; 1=pressed, 0=released",
            "type":               "bool",
            "true":               1,
            "false":              0,
            "poll_interval":      0,
            "poll_interval_unit": "sec",
            "poll_topic":         ""
        },
        "input/1": {
            "label":              "Input 1",
            "tooltip":            "Digital input channel 1 state",
            "hint":               "True when the input is active",
            "explanation":        "Reports the boolean state of input 1; 1=pressed, 0=released",
            "type":               "bool",
            "true":               1,
            "false":              0,
            "poll_interval":      0,
            "poll_interval_unit": "sec",
            "poll_topic":         ""
        },
        "input_event/0/event": {
            "label":              "Button 0 Event",
            "tooltip":            "Type of event on button 0",
            "hint":               "Select short or long press",
            "explanation":        "Emitted when button 0 is pressed: 'S'=short, 'L'=long",
            "type":               "enum",
            "values":             ["S","L"],
            "display":            {"S":"Short Press","L":"Long Press"},
            "poll_interval":      0,
            "poll_interval_unit": "sec",
            "poll_topic":         ""
        },
        "input_event/1/event": {
            "label":              "Button 1 Event",
            "tooltip":            "Type of event on button 1",
            "hint":               "Select short or long press",
            "explanation":        "Emitted when button 1 is pressed: 'S'=short, 'L'=long, ''=none",
            "type":               "enum",
            "values":             ["","S","L"],
            "display":            {"":"None","S":"Short Press","L":"Long Press"},
            "poll_interval":      0,
            "poll_interval_unit": "sec",
            "poll_topic":         ""
        },
        "relay/0": {
            "label":              "Relay 0 State",
            "tooltip":            "Current on/off state of relay 0",
            "hint":               "Use Evaluate to check on/off",
            "explanation":        "Indicates whether relay 0 is currently on or off",
            "type":               "enum",
            "values":             ["on","off"],
            "poll_interval":      0,
            "poll_interval_unit": "sec",
            "poll_topic":         ""
        },
        "relay/0/power": {
            "label":              "Relay 0 Power",
            "tooltip":            "Instantaneous power draw of relay 0",
            "hint":               "Enter a watt threshold",
            "explanation":        "Reports power consumption in watts for relay 0",
            "type":               "number",
            "units":              "W",
            "range":              [0, None],
            "comparators":        ["<","<=","==","!="," >=",">"],
            "poll_interval":      60,
            "poll_interval_unit": "sec",
            "poll_topic":         "relay/0/power"
        },
        "relay/0/energy": {
            "label":              "Relay 0 Energy",
            "tooltip":            "Cumulative energy usage of relay 0",
            "hint":               "Enter watt‐hour limit",
            "explanation":        "Total energy consumed by relay 0 in Wh",
            "type":               "number",
            "units":              "Wh",
            "poll_interval":      60,
            "poll_interval_unit": "sec",
            "poll_topic":         "relay/0/energy"
        },
        "relay/1": {
            "label":              "Relay 1 State",
            "tooltip":            "Current on/off state of relay 1",
            "hint":               "Use Evaluate to check on/off",
            "explanation":        "Indicates whether relay 1 is currently on or off",
            "type":               "enum",
            "values":             ["on","off"],
            "poll_interval":      0,
            "poll_interval_unit": "sec",
            "poll_topic":         ""
        },
        "relay/1/power": {
            "label":              "Relay 1 Power",
            "tooltip":            "Instantaneous power draw of relay 1",
            "hint":               "Enter a watt threshold",
            "explanation":        "Reports power consumption in watts for relay 1",
            "type":               "number",
            "units":              "W",
            "range":              [0, None],
            "comparators":        ["<","<=","==","!="," >=",">"],
            "poll_interval":      60,
            "poll_interval_unit": "sec",
            "poll_topic":         "relay/1/power"
        },
        "relay/1/energy": {
            "label":              "Relay 1 Energy",
            "tooltip":            "Cumulative energy usage of relay 1",
            "hint":               "Enter watt‐hour limit",
            "explanation":        "Total energy consumed by relay 1 in Wh",
            "type":               "number",
            "units":              "Wh",
            "poll_interval":      60,
            "poll_interval_unit": "sec",
            "poll_topic":         "relay/1/energy"
        },
        "temperature": {
            "label":              "Temperature (°C)",
            "tooltip":            "Device internal temperature",
            "hint":               "Enter °C threshold",
            "explanation":        "Shows the current temperature inside the device in Celsius",
            "type":               "number",
            "units":              "°C",
            "range":              [-50,150],
            "comparators":        ["<","<=","==","!="," >=",">"],
            "poll_interval":      60,
            "poll_interval_unit": "sec",
            "poll_topic":         "temperature"
        },
        "temperature_f": {
            "label":              "Temperature (°F)",
            "tooltip":            "Device internal temperature",
            "hint":               "Enter °F threshold",
            "explanation":        "Shows the current temperature inside the device in Fahrenheit",
            "type":               "number",
            "units":              "°F",
            "range":              [-58,302],
            "poll_interval":      60,
            "poll_interval_unit": "sec",
            "poll_topic":         "temperature_f"
        },
        "temperature_status": {
            "label":              "Temperature Status",
            "tooltip":            "Overtemperature indicator",
            "hint":               "Check for 'Overheated'",
            "explanation":        "Indicates if the device temperature is normal or overheated",
            "type":               "enum",
            "values":             ["Normal","Overheated"],
            "poll_interval":      60,
            "poll_interval_unit": "sec",
            "poll_topic":         "temperature_status"
        },
        "overtemperature": {
            "label":              "Overtemperature",
            "tooltip":            "Boolean overtemperature flag",
            "hint":               "True if over temperature",
            "explanation":        "Reports a boolean flag when device temperature exceeds safe limits",
            "type":               "bool",
            "true":               1,
            "false":              0,
            "poll_interval":      60,
            "poll_interval_unit": "sec",
            "poll_topic":         "overtemperature"
        },
        "voltage": {
            "label":              "Voltage",
            "tooltip":            "Supply voltage reading",
            "hint":               "Enter V threshold",
            "explanation":        "Reports the device’s supply voltage in volts",
            "type":               "number",
            "units":              "V",
            "poll_interval":      60,
            "poll_interval_unit": "sec",
            "poll_topic":         "voltage"
        },
        "online": {
            "label":              "Device Online",
            "tooltip":            "Connectivity status",
            "hint":               "True if device is online",
            "explanation":        "Indicates whether the device is currently reachable via MQTT",
            "type":               "bool",
            "poll_interval":      30,
            "poll_interval_unit": "sec",
            "poll_topic":         "online"
        },
        "info/wifi_sta/rssi": {
            "label":              "WiFi RSSI",
            "tooltip":            "WiFi signal strength",
            "hint":               "Enter minimum RSSI (dBm)",
            "explanation":        "Shows the received signal strength indicator of the WiFi connection",
            "type":               "number",
            "units":              "dBm",
            "poll_interval":      60,
            "poll_interval_unit": "sec",
            "poll_topic":         "info/wifi_sta/rssi"
        }
    },
    "command_topics": {
        "relay/0/command": {
            "label":         "Relay 0 Command",
            "tooltip":       "Turn relay 0 on or off",
            "hint":          "Choose 'on' to energize, 'off' to de-energize",
            "explanation":   "Sends a command to switch relay channel 0",
            "type":          "enum",
            "values":        ["on","off"],
            "timeout":       10,
            "timeout_unit":  "sec",
            "result_topic":  "relay/0"
        },
        "relay/1/command": {
            "label":         "Relay 1 Command",
            "tooltip":       "Turn relay 1 on or off",
            "hint":          "Choose 'on' or 'off'",
            "explanation":   "Sends a command to switch relay channel 1",
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

# dev_scripts/seed_action_schema.py

import os
import sys
# ensure project root (one level up) is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models.device_category import DeviceCategory
from models.device_model import DeviceModel
from models.device_action_schema import DeviceActionSchema

SHELLY_SCHEMA = {
    "topics": {
        "input/0":   {"label":"Input 0","type":"bool","true":1,"false":0},
        "input_event/0": {
            "label":"Button 0 event","type":"enum",
            "values":["S","L"], "display":{"S":"Short Press","L":"Long Press"}
        },
        "relay/0":   {"label":"Relay 0","type":"enum","values":["on","off"]},
        "relay/0/power":{
            "label":"Power","type":"number","units":"W",
            "range":[0,None],"comparators":["<","<=","==","!="," >=",">"]
        },
        "temperature":{
            "label":"Temperature","type":"number","units":"°C",
            "range":[-50,150],"comparators":["<","<=","==","!="," >=",">"]
        }
    },
    "command_topics":{
        "relay/0/command":{
            "label":"Relay 0 command","type":"enum","values":["on","off"]
        }
    }
}

app = create_app()
with app.app_context():
    proc_cat = DeviceCategory.query.filter_by(name='processor').first()
    shelly_mdl = DeviceModel.query.filter_by(name='Shelly 2.5 MQTT').first()
    if shelly_mdl:
        if not shelly_mdl.action_schema:
            shelly_mdl.action_schema = DeviceActionSchema(schema=SHELLY_SCHEMA)
        else:
            shelly_mdl.action_schema.schema = SHELLY_SCHEMA
        db.session.commit()
        print("Shelly 2.5 MQTT action schema seeded ✅")

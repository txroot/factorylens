import os
import sys
# ensure project root (one level up) is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from extensions import db
from models.device_category import DeviceCategory
from models.device_model import DeviceModel
from models.device import Device
from app import create_app

AGENT_MODELS = ["Action Agent", "Automation Agent"]

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # 1) ensure processor category exists
        cat = DeviceCategory.query.filter_by(name="processor").first()
        if not cat:
            cat = DeviceCategory(name="processor", label="🧠 Processor")
            db.session.add(cat)
            db.session.flush()

        # 2) ensure both models exist under processor
        for mdl_name in AGENT_MODELS:
            mdl = DeviceModel.query.filter_by(name=mdl_name).first()
            if not mdl:
                mdl = DeviceModel(name=mdl_name, category_id=cat.id)
                db.session.add(mdl)
                db.session.flush()

            # 3) one-and-only-one device of each model
            dev = Device.query.filter_by(device_model_id=mdl.id).first()
            if not dev:
                dev = Device(
                    name=f"Main {mdl_name}",
                    device_model_id=mdl.id,
                    mqtt_client_id=mdl_name.lower().replace(" ", "-"),
                    topic_prefix=f"factory/{mdl_name.split()[0].lower()}",
                    enabled=True
                )
                db.session.add(dev)
        db.session.commit()
        print("Processor agents ready ✅")

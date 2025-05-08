# app.py

import os
os.environ.setdefault("FLASK_APP", __name__)

# Flask
from flask import Flask
from flask_migrate import Migrate
from flask import session, request

from extensions import db, login_manager

from dotenv import load_dotenv
load_dotenv()

# Import Models
from models import User, Camera, Device
from models.user import User
from models.device_category import DeviceCategory
from models.device_model import DeviceModel
from models.device_schema import DeviceSchema
from models.device import Device
from models.camera import Camera
from models.camera_stream import CameraStream
from models.actions import Action

# Import Blueprints
from middleware.auth import auth_bp
from routes.users import users_bp
from routes.home import home_bp
from routes.dashboard import dashboard_bp
from routes.help import help_bp
from routes.language import language_bp
from routes.notifications import notifications_bp
from routes.settings import settings_bp
from routes.apps.apps import apps_bp
from routes.storage import storage_bp
from routes.apps.storage import apps_storage_bp
from routes.apps.elfinder_connector import elfinder_bp
from routes.apps.device_control import apps_ctrl_bp
from routes.actions import actions_bp

# from routes.automations import automations_bp   # enable when ready

# Import Mail Client
from utils.mail_client import mail

# Import Configurations
from config.settings import Config

# Import Tasks
from apscheduler.schedulers.background import BackgroundScheduler
from utils.tasks import poll_camera_status

# Import MQTT
from controllers.mqtt import init_mqtt

# Internationalization
from flask_babel import Babel
babel = Babel()

def get_locale():
    # 1) if they’ve set it in session, use that
    if 'lang' in session:
        return session['lang']
    # 2) otherwise auto-detect from the Accept-Language header
    print (request.accept_languages)
    print (request.accept_languages.best_match(['en', 'pt']))
    return request.accept_languages.best_match(['en', 'pt'])

def create_app():
    app = Flask(
        __name__,
        template_folder="views",
        static_folder="public",
        static_url_path="/assets"   # now public/ ↔ /assets
    )
    app.config.from_object(Config)
    
    # Bind database
    db.init_app(app)
    
    # Initialize Flask-Migrate
    Migrate(app, db)
    login_manager.init_app(app)
    
    with app.app_context():
        
        db.create_all()

    # Initialize Flask-Mail with the app config
    mail.init_app(app)
    # Initialize Babel *with* your selector
    babel.init_app(app,
                   locale_selector=get_locale,
                   default_locale='en',
                   default_timezone='UTC')
    @app.context_processor
    def inject_locale():
        return {'current_locale': session.get('lang', 'en')}

    # Register template context
    @app.context_processor
    def inject_translation():
        from flask_babel import gettext as t
        return dict(t=t)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(help_bp)
    app.register_blueprint(language_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(apps_bp)
    app.register_blueprint(storage_bp)
    app.register_blueprint(apps_storage_bp)
    app.register_blueprint(elfinder_bp)
    app.register_blueprint(apps_ctrl_bp)
    app.register_blueprint(actions_bp)
    # app.register_blueprint(automations_bp)

    # ——— START POLLING SCHEDULER ———
    scheduler = BackgroundScheduler()
    # run our poll job every 30 seconds (you can tune this to your smallest unit)
    scheduler.add_job(
        func=poll_camera_status,
        trigger='interval',
        seconds=300,
        id='poll_camera_status',
        replace_existing=True
    )
    #scheduler.start()

    # ---------- MQTT worker ----------
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        with app.app_context():
            init_mqtt(app)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8082)

# app.py

import os

# Flask
from flask import Flask
from flask_migrate import Migrate

from extensions import db, login_manager

from dotenv import load_dotenv
load_dotenv()

# Import Models
from models import User, Camera, Device
from models.user import User
from models.device import Device
from models.camera import Camera

# Import Blueprints
from middleware.auth import auth_bp
from routes.users import users_bp
from routes.home import home_bp
from routes.dashboard import dashboard_bp
from routes.help import help_bp

# Import Mail Client
from utils.mail_client import mail

# Import Configurations
from config.settings import Config

# Internationalization
from flask_babel import Babel
babel = Babel()

def create_app():
    app = Flask(__name__, template_folder="views", static_folder="public")
    app.config.from_object(Config)
    
    # Bind database
    db.init_app(app)
    login_manager.init_app(app)
    
    # Initialize Flask-Migrate
    migrate = Migrate(app, db)

    with app.app_context():
        
        db.create_all()

    # Initialize Flask-Mail with the app config
    mail.init_app(app)
    # Initialize Flask-Babel with the app config
    babel.init_app(app)

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

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=8082)

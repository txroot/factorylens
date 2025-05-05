# config/settings.py

import os
from datetime import timedelta

def str_to_bool(value):
    truthy = ("true", "1", "yes", "on")
    falsey = ("false", "0", "no", "off")

    val = str(value).strip().lower()
    
    if val in truthy:
        return True
    elif val in falsey:
        return False
    else:
        raise ValueError(f"Invalid boolean string: '{value}'")

# Database settings
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "flaskdb")
DB_USER = os.environ.get("DB_USER", "flaskuser")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "flaskpass")

# Session settings
SESSION_PERMANENT_SESSION_LIFETIME_HOURS = int(os.environ.get("SESSION_PERMANENT_SESSION_LIFETIME_HOURS", 24))
SESSION_INNACTIVITY_TIMEOUT = int(os.environ.get("SESSION_INNACTIVITY_TIMEOUT", 300))

# Application version
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")

# Mail configuration
MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.example.com")
MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
MAIL_TLS = str_to_bool(os.environ.get("MAIL_TLS", "False"))
MAIL_SSL = str_to_bool(os.environ.get("MAIL_SSL", "True"))
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "your-email@example.com")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "your-email-password")
MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", MAIL_USERNAME)

class Config:
    SQLALCHEMY_DATABASE_URI = f"mysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(24)
    
    PERMANENT_SESSION_LIFETIME = timedelta(hours=SESSION_PERMANENT_SESSION_LIFETIME_HOURS)
    INNACTIVITY_TIMEOUT = SESSION_INNACTIVITY_TIMEOUT

    # Additional configuration
    APP_VERSION = APP_VERSION

    # Mail configuration
    MAIL_SERVER = MAIL_SERVER
    MAIL_PORT = MAIL_PORT
    MAIL_USE_TLS = MAIL_TLS
    MAIL_USE_SSL = MAIL_SSL
    MAIL_USERNAME = MAIL_USERNAME
    MAIL_PASSWORD = MAIL_PASSWORD
    MAIL_DEFAULT_SENDER = MAIL_DEFAULT_SENDER

    # MQTT
    MQTT_BROKER   = os.getenv("MQTT_HOST", "localhost")
    MQTT_PORT     = int(os.getenv("MQTT_PORT", 1883))
    MQTT_USER     = os.getenv("MQTT_USER", None)
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", None)

    # BABEL
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_DEFAULT_TIMEZONE = 'UTC'

    STORAGE_ROOT = os.getenv('STORAGE_ROOT', '/app/storage')
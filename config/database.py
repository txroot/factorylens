# config/database.py

import os
from flask_sqlalchemy import SQLAlchemy

class Config:
    # ----- Database (SQLAlchemy) -----
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
        f"@{os.getenv('DB_HOST', 'db')}:{os.getenv('DB_PORT', '3306')}/"
        f"{os.getenv('MYSQL_DATABASE')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ----- MQTT -----
    MQTT_HOST     = os.getenv('MQTT_HOST', 'localhost')
    MQTT_PORT     = int(os.getenv('MQTT_PORT', 1883))
    MQTT_USER     = os.getenv('MQTT_USER', None)
    MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', None)

db = SQLAlchemy()

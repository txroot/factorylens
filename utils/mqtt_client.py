# utils/mqtt_client.py

from paho.mqtt.client import Client
from config.settings import Config 
from controllers.mqtt import init_mqtt

client = Client()
init_mqtt(client)
client.connect(Config.MQTT_BROKER, Config.MQTT_PORT)
client.loop_start()

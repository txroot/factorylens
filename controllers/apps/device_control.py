"""
Helper functions used by the blueprint + front‑end JS
"""
from flask import current_app
from models.device import Device

def list_shelly_devices():
    """All *enabled* Shelly 2.5 devices."""
    return (
        Device.query
        .join(Device.model)
        .filter(
            Device.enabled == True,
            Device.model.has(name="Shelly 2.5 MQTT")
        )
        .order_by(Device.id)
        .all()
    )

# ---------- MQTT publish wrappers ----------
def publish_relay(device: Device, channel: int, turn_on: bool):
    """
    Publish MQTT command to switch channel 0/1 on/off.
    Topic: shellies/<clientId>/relay/<ch>/command
    Payload: "on" / "off"
    """
    topic = f"shellies/{device.mqtt_client_id}/relay/{channel}/command"
    payload = "on" if turn_on else "off"
    current_app.mqtt.publish(topic, payload, qos=1, retain=False)

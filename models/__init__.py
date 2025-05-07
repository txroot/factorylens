# models/__init__.py

from .device import Device
from .camera_stream import CameraStream
from .camera import Camera
from .user import User
from .device_category import DeviceCategory
from .device_model import DeviceModel
from .device_schema import DeviceSchema
from .actions import Action
from .device_action_schema import DeviceActionSchema

# For migrations or Flask shell usage
__all__ = [
    "Camera",
    "Device",
    "User",
    "DeviceCategory",
    "DeviceModel",
    "DeviceSchema",
    "DeviceActionSchema",
    "Action",
    "CameraStream"
]
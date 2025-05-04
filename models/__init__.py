# models/__init__.py

from .device import Device
from .camera_stream import CameraStream
from .camera import Camera
from .user import User
from .device_category import DeviceCategory
from .device_model import DeviceModel
from .device_schema import DeviceSchema  # if you want it exposed here

# For migrations or Flask shell usage
__all__ = [
    "Camera",
    "Device",
    "User",
    "DeviceCategory",
    "DeviceModel",
    "DeviceSchema"
]
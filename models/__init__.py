# models/__init__.py

from .camera import Camera
from .device import Device
from .user import User

# For migrations or Flask shell usage
__all__ = ["Camera", "Device", "User"]
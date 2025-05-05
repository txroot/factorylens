# controllers/apps/storage.py

from models.device import Device
from models.device_model import DeviceModel
from models.device_category import DeviceCategory

def get_storage_devices():
    """
    Return all *enabled* storage devices (local, FTP/SFTP, etc.)
    for use in the file-explorer dropdown.
    """
    return (
        Device.query
        .join(Device.model)
        .join(DeviceModel.category)
        .filter(
            DeviceModel.category.has(name="storage"),
            Device.enabled == True
        )
        .order_by(Device.id)
        .all()
    )
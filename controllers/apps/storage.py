from models.device import Device
from models.device_model import DeviceModel

def get_local_storage_devices():
    # join category & model, filter by category.name='storage' and model.name='Local storage'
    return (
      Device.query
        .join(Device.model)
        .join(DeviceModel.category)
        .filter(DeviceModel.category.has(name='storage'),
                DeviceModel.name=='Local storage')
        .all()
    )

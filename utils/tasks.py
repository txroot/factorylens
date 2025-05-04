from datetime import datetime, timedelta
import subprocess
from models.camera import Camera
from models.device import Device
from extensions import db

# unit → seconds multiplier
_UNIT_MULTIPLIERS = {
    'ms':    0.001,
    'sec':   1,
    'min':   60,
    'hour':  3600,
    'day':   86400,
}

def poll_device_status(dev_id):
    """
    Polls the status of a single device and its cameras based on the device's polling interval.
    """
    # Import create_app here to avoid circular import at the top level
    from app import create_app  # Import your app context

    # Use app context when querying the database
    app = create_app()
    
    with app.app_context():  # Wrap database interaction in app context
        now = datetime.utcnow()
        print(f"Polling started for device {dev_id} at {now}")  # Debug print: when the polling starts
        
        dev = Device.query.get(dev_id)  # Get device by ID
        if not dev or not dev.enabled:
            print(f"Skipping device {dev.id} ({dev.name}) because it's disabled or not found.")
            return

        # compute how many seconds between polls
        unit = dev.poll_interval_unit or 'sec'
        interval = dev.poll_interval or 60
        delta = timedelta(seconds=interval * _UNIT_MULTIPLIERS.get(unit, 1))

        # If it's time to poll this device
        if not dev.last_seen or (dev.last_seen + delta) <= now:
            print(f"Polling device {dev.id} ({dev.name})...")  # Debug print: device being polled

            # Poll all cameras related to this device
            cams = Camera.query.filter_by(device_id=dev.id).all()
            device_status = 'online'  # Assume device is online initially

            # Process each camera for this device
            for cam in cams:
                print(f"Polling camera {cam.id} ({cam.name})...")  # Debug print: camera being polled

                # Check if camera has streams
                stream = cam.default_stream or (cam.streams[0] if cam.streams else None)
                if not stream:
                    print(f"Camera {cam.id} ({cam.name}) has no streams, marking as error.")
                    cam.status = 'error'
                    continue

                # Build RTSP URL and check the stream
                url = stream.full_url or stream.get_full_url(include_auth=True)
                try:
                    print(f"Checking stream URL for camera {cam.id} ({cam.name}): {url}")  # Debug print: URL being checked
                    subprocess.check_output([
                        "ffprobe", "-v", "error",
                        "-rtsp_transport", "tcp",
                        "-timeout", "1500000",   # 1.5 s
                        "-analyzeduration", "0",
                        "-probesize", "32",
                        "-i", url
                    ], timeout=2)
                    print(f"Camera {cam.id} ({cam.name}) is online.")  # Debug print: successful check
                    cam.status = 'online'
                except Exception as e:
                    print(f"Error while checking camera {cam.id} ({cam.name}): {str(e)}")  # Debug print: error during ffprobe
                    cam.status = 'offline'

                # Update camera's heartbeat
                cam.last_heartbeat = now
                print(f"Updated heartbeat for camera {cam.id} ({cam.name}) at {now}")  # Debug print: heartbeat update

                # If any camera is offline, mark the device as offline
                if cam.status == 'offline':
                    device_status = 'offline'

            # Update device status
            if dev.status != device_status:
                dev.status = device_status
                print(f"Updated device {dev.id} ({dev.name}) status to {dev.status}")
            
            # Update the last_seen timestamp of the device
            dev.last_seen = now
            print(f"Updated device {dev.id} last_seen at {now}")  # Debug print: last seen update

            # Commit the changes for this device and cameras
            db.session.commit()
            print(f"Device {dev.id} polling completed.")

        else:
            print(f"Device {dev.id} ({dev.name}) does not need to be polled yet.")

def poll_camera_status():
    """
    Initiates polling for all devices that need to be polled.
    This function schedules the polling based on each device's poll interval.
    """
    # Import create_app here to avoid circular import at the top level
    from app import create_app  # Import your app context

    # Use app context when querying the database
    app = create_app()

    with app.app_context():  # Wrap database interaction in app context
        # Find all devices that have passed their poll interval and need to be polled
        devices = Device.query.all()
        print(f"Found {len(devices)} devices to process.")  # Debug print: how many devices we have

        for dev in devices:
            print(f"Scheduling poll for device {dev.id} ({dev.name})")  # Debug print: device being scheduled
            poll_device_status(dev.id)  # Poll each device individually

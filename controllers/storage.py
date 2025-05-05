"""
controllers/storage_controller.py
Logic for file-based storage devices (pure controller functions).
"""
import os
from flask import send_from_directory, flash, redirect, url_for, abort, request, render_template
from extensions import db
from models.device import Device
from models.device_model import DeviceModel
from models.device_category import DeviceCategory


def get_storage_devices():
    """Fetch all Storage Unit devices from the database."""
    return (
        Device.query
        .join(Device.model)
        .join(DeviceModel.category)
        .filter(DeviceModel.category.has(name='storage'))
        .order_by(Device.id)
        .all()
    )


def list_devices():
    """Controller: list all configured storage devices."""
    devices = get_storage_devices()
    return render_template('storage/devices.html', devices=devices)


def browse_files(dev_id):
    """Controller: browse filesystem and handle upload/download for a storage device."""
    dev = Device.query.get_or_404(dev_id)
    params = dev.parameters or {}
    base = params.get('base_path')
    if not base or not os.path.isdir(base):
        flash('Base path not found or not configured.', 'danger')
        return redirect(url_for('storage.list_devices'))

    # Handle upload
    if request.method == 'POST':
        file = request.files.get('file')
        if file:
            dest = os.path.join(base, file.filename)
            file.save(dest)
            flash(f'Uploaded {file.filename}', 'success')
        return redirect(url_for('storage.browse_files', dev_id=dev.id, path=request.form.get('path', '')))

    # Path traversal protection
    rel_path = request.args.get('path', '')
    abs_path = os.path.normpath(os.path.join(base, rel_path))
    if not abs_path.startswith(os.path.normpath(base)):
        abort(403)

    # Directory or file?
    if os.path.isdir(abs_path):
        entries = []
        for name in sorted(os.listdir(abs_path)):
            full = os.path.join(abs_path, name)
            entries.append({'name': name, 'is_dir': os.path.isdir(full)})
        return render_template('storage/browse.html', dev=dev, entries=entries, rel_path=rel_path)
    else:
        # download file
        return send_from_directory(os.path.dirname(abs_path), os.path.basename(abs_path), as_attachment=True)


def delete_file(dev_id):
    """Controller: delete a file or empty directory on the storage device."""
    dev = Device.query.get_or_404(dev_id)
    params = dev.parameters or {}
    base = params.get('base_path')
    target = request.form.get('path', '')
    abs_path = os.path.normpath(os.path.join(base, target))
    if not abs_path.startswith(os.path.normpath(base)):
        abort(403)

    if os.path.isdir(abs_path):
        try:
            os.rmdir(abs_path)
            flash(f"Removed directory {target}", 'success')
        except OSError as e:
            flash(str(e), 'danger')
    else:
        os.remove(abs_path)
        flash(f"Deleted file {target}", 'success')

    return redirect(url_for('storage.browse_files', dev_id=dev.id, path=os.path.dirname(target)))

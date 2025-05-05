# routes/apps/storage.py

from flask import Blueprint, render_template
from controllers.apps.storage import get_storage_devices

apps_storage_bp = Blueprint('apps_storage', __name__, url_prefix='/apps')

@apps_storage_bp.route('/file-explorer')
def file_explorer():
    # only local‐storage devices, for now
    devices = get_storage_devices()
    return render_template('apps/file-explorer.hbs', devices=devices)

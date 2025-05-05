# routes/storage.py

from flask import Blueprint
from controllers.storage import list_devices, browse_files, delete_file

storage_bp = Blueprint('storage', __name__, url_prefix='/storage')

# List all storage devices
storage_bp.add_url_rule(
    '/', 'list_devices', list_devices, methods=['GET']
)

# Browse directory (view/upload)
storage_bp.add_url_rule(
    '/<int:dev_id>/files', 'browse_files', browse_files, methods=['GET', 'POST']
)

# Delete a file or empty directory
storage_bp.add_url_rule(
    '/<int:dev_id>/delete', 'delete_file', delete_file, methods=['POST']
)

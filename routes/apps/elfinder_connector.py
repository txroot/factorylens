# routes/apps/elfinder_connector.py

import os
import base64
import mimetypes
from flask import Blueprint, request, jsonify, current_app
from models.device import Device

elfinder_bp = Blueprint('elfinder_connector', __name__, url_prefix='/storage/connector')

def _resolve_base_path(raw: str) -> str:
    """Same logic as controllers/storage: absolute or under STORAGE_ROOT."""
    raw = raw.strip()
    if os.path.isabs(raw):
        return raw
    root = current_app.config.get('STORAGE_ROOT', '/app/storage')
    return os.path.join(root, raw)

@elfinder_bp.route('', methods=['GET', 'POST'])
def connector():
    # 1) Grab common params
    cmd    = request.values.get('cmd')
    dev_id = request.values.get('dev')
    target = request.values.get('target', '')  # Base64 hash of sub-folder
    print(f"[elFinder] cmd={cmd!r}, dev={dev_id!r}, target={target!r}")

    # 2) Lookup device & base folder
    dev = Device.query.get_or_404(dev_id)
    raw_base = (dev.parameters or {}).get('base_path','').strip()
    base = _resolve_base_path(raw_base)
    print(f"[elFinder] resolved base_path={base!r}")

    if not os.path.isdir(base):
        return jsonify(error=f'Invalid base path: {base}'), 400

    # 3) Handle only the 'open' command for now
    if cmd == 'open':
        # Decode Base64 target => relative path
        try:
            rel = base64.b64decode(target).decode('utf-8') if target else ''
        except Exception:
            rel = ''
        abs_dir = os.path.normpath(os.path.join(base, rel))

        # Guard traversal
        if not abs_dir.startswith(os.path.normpath(base)):
            return jsonify(error='Access denied'), 403

        # Build cwd metadata
        cwd = {
            'hash': target or '',
            'name': os.path.basename(abs_dir) or '/',
            'mime': 'directory',
            'ts': int(os.path.getmtime(abs_dir)),
            'size': 0,
            'dirs': 1
        }

        # Build file list
        files = []
        for name in sorted(os.listdir(abs_dir)):
            if name.startswith('.'):
                continue
            full = os.path.join(abs_dir, name)
            rel_child = os.path.join(rel, name)
            # elFinder expects Base64 hashes
            hash_b64 = base64.b64encode(rel_child.encode('utf-8')).decode('utf-8')
            files.append({
                'name' : name,
                'hash' : hash_b64,
                'mime' : 'directory' if os.path.isdir(full)
                          else mimetypes.guess_type(full)[0] or 'application/octet-stream',
                'ts'   : int(os.path.getmtime(full)),
                'size' : os.path.getsize(full) if os.path.isfile(full) else 0,
                'dirs' : 1 if os.path.isdir(full) else 0
            })

        response = {
            'cwd'   : cwd,
            'files' : [cwd] + files
        }
        print(f"[elFinder] open response: {len(files)} entries")
        return jsonify(response)

    # Fallback
    return jsonify(error=f"Unsupported command: {cmd}"), 400

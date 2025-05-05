# routes/apps/elfinder_connector.py

import os
import base64
import mimetypes
import traceback
from flask import Blueprint, request, jsonify, current_app
from models.device import Device

elfinder_bp = Blueprint(
    'elfinder_connector',
    __name__,
    url_prefix='/storage/connector'
)


def _resolve_base_path(raw: str) -> str:
    """
    Convert a raw 'base_path' (absolute or relative) into an absolute folder
    under STORAGE_ROOT (defaults to /app/storage).
    """
    raw = raw.strip()
    if os.path.isabs(raw):
        return raw
    root = current_app.config.get('STORAGE_ROOT', '/app/storage')
    return os.path.join(root, raw)


def _b64(s: str) -> str:
    """
    Base64‐encode a string, stripping any trailing '=' padding.
    """
    return base64.b64encode(s.encode('utf-8')).decode('utf-8').rstrip('=')


@elfinder_bp.route('', methods=['GET', 'POST'])
def connector():
    try:
        cmd    = request.values.get('cmd')
        dev_id = request.values.get('dev')
        target = request.values.get('target', '')
        current_app.logger.debug(f"[elFinder] cmd={cmd} dev={dev_id} target={target}")

        # Lookup device and resolve its base folder
        dev = Device.query.get_or_404(dev_id)
        raw = (dev.parameters or {}).get('base_path', '')
        base = _resolve_base_path(raw)
        if not os.path.isdir(base):
            return jsonify(error=f'Invalid base path: {base}'), 400

        # Only 'open' command implemented
        if cmd == 'open':
            volumeid = f"dev{dev_id}"  # unique per device

            # Decode the Base64‐encoded target into a relative path
            rel = ''
            if target:
                # strip off the "<volumeid>_" prefix
                _tmp = target.split('_', 1)[1] if '_' in target else target
                rel = base64.b64decode(_tmp + '===').decode('utf-8')
                # ── FIX: remove leading slash so join(base, rel) works
                if rel.startswith('/'):
                    rel = rel.lstrip('/')

            abs_dir = os.path.normpath(os.path.join(base, rel))
            # Prevent path traversal
            if not abs_dir.startswith(os.path.normpath(base)):
                return jsonify(error='Access denied'), 403

            # Helper to build consistent hashes
            def make_hash(path: str) -> str:
                return f"{volumeid}_{_b64(path or '/')}"

            cwd_hash = make_hash(rel)
            # Build the root (cwd) entry
            cwd = {
                'hash'     : cwd_hash,
                'name'     : os.path.basename(abs_dir) or '/',
                'mime'     : 'directory',
                'ts'       : int(os.path.getmtime(abs_dir)),
                'size'     : 0,
                'dirs'     : 1,
                'volumeid' : volumeid,
                'root'     : 1 if rel == '' else 0,
            }

            # List child entries
            files = [cwd]
            for name in sorted(os.listdir(abs_dir)):
                if name.startswith('.'):
                    continue
                full      = os.path.join(abs_dir, name)
                rel_child = os.path.join(rel, name)
                hash_child = make_hash(rel_child)
                files.append({
                    'hash'     : hash_child,
                    'phash'    : cwd_hash,
                    'name'     : name,
                    'mime'     : 'directory' if os.path.isdir(full)
                                  else mimetypes.guess_type(full)[0] or 'application/octet-stream',
                    'ts'       : int(os.path.getmtime(full)),
                    'size'     : os.path.getsize(full) if os.path.isfile(full) else 0,
                    'dirs'     : 1 if os.path.isdir(full) else 0,
                    'volumeid' : volumeid,
                })

            # Assemble the response
            response = {
                'api'        : 2.1,
                'cwd'        : cwd,
                'files'      : files,
                'options'    : {
                    'path'   : rel,
                    'url'    : '',
                    'tmbUrl' : '',
                },
                'netDrivers' : [],
                'tree'       : [item for item in files if item['dirs'] > 0],
            }

            current_app.logger.debug(
                f"[elFinder] open response: {len(files)-1} entries, "
                f"{len(response['tree'])} tree nodes"
            )
            return jsonify(response)

        # Unsupported commands
        return jsonify(error=f"Unsupported command: {cmd}"), 400

    except Exception as e:
        current_app.logger.error(
            "elFinder connector exception:\n" + traceback.format_exc()
        )
        return jsonify(error=str(e)), 500

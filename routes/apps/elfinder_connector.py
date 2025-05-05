# routes/apps/elfinder_connector.py

import os
import base64
import mimetypes
import traceback
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from models.device import Device

elfinder_bp = Blueprint('elfinder_connector', __name__, url_prefix='/storage/connector')


def _resolve_base_path(raw: str) -> str:
    raw = raw.strip()
    if os.path.isabs(raw):
        return raw
    root = current_app.config.get('STORAGE_ROOT', '/app/storage')
    return os.path.join(root, raw)


def _b64(s: str) -> str:
    return base64.b64encode(s.encode('utf-8')).decode('utf-8').rstrip('=')


@elfinder_bp.route('', methods=['GET', 'POST'])
def connector():
    try:
        cmd    = request.values.get('cmd')
        dev_id = request.values.get('dev')
        current_app.logger.debug(f"[elFinder] cmd={cmd} dev={dev_id}")

        # Lookup storage device
        dev = Device.query.get_or_404(dev_id)
        raw = (dev.parameters or {}).get('base_path', '')
        base = _resolve_base_path(raw)
        if not os.path.isdir(base):
            return jsonify(error=f'Invalid base path: {base}'), 400

        volumeid = f"dev{dev_id}"

        # ─── Helpers ─────────────────────────────────────────────────────────

        def make_hash(rel_path: str) -> str:
            """
            Normalize root to '/', encode and prefix with volumeid.
            """
            # represent root as '/'
            normalized = '/' if rel_path == '' else rel_path
            enc = _b64(normalized)
            return f"{volumeid}_{enc}"

        def resolve_path(hash_str: str):
            """
            Decode elFinder hash back to (abs_path, rel_path).
            """
            if not hash_str:
                rel = ''
            else:
                # strip prefix
                part = hash_str.split('_', 1)[1] if '_' in hash_str else hash_str
                decoded = base64.b64decode(part + '===').decode('utf-8')
                rel = '' if decoded in ('', '/') else decoded.lstrip('/')
            abs_path = os.path.normpath(os.path.join(base, rel))
            if not abs_path.startswith(os.path.normpath(base)):
                raise PermissionError("Access denied")
            return abs_path, rel

        # ─── OPEN ──────────────────────────────────────────────────────────────
        if cmd == 'open':
            target = request.values.get('target', '')
            abs_dir, rel = resolve_path(target)

            cwd_hash = make_hash(rel)
            cwd = {
                'hash'     : cwd_hash,
                'name'     : os.path.basename(abs_dir) or '/',
                'mime'     : 'directory',
                'ts'       : int(os.path.getmtime(abs_dir)),
                'size'     : 0,
                'dirs'     : 1,
                'volumeid' : volumeid,
                'root'     : 1 if rel == '' else 0,
                'read'     : 1,
                'write'    : 1,
                'locked'   : 0,
            }
            # if not root, add parent hash
            if rel:
                parent_rel = os.path.dirname(rel)
                cwd['phash'] = make_hash(parent_rel)

            files = [cwd]
            for name in sorted(os.listdir(abs_dir)):
                if name.startswith('.'):
                    continue
                full      = os.path.join(abs_dir, name)
                rel_child = os.path.join(rel, name)
                h = make_hash(rel_child)
                files.append({
                    'hash'     : h,
                    'phash'    : cwd_hash,
                    'name'     : name,
                    'mime'     : 'directory' if os.path.isdir(full)
                                  else mimetypes.guess_type(full)[0] or 'application/octet-stream',
                    'ts'       : int(os.path.getmtime(full)),
                    'size'     : os.path.getsize(full) if os.path.isfile(full) else 0,
                    'dirs'     : 1 if os.path.isdir(full) else 0,
                    'volumeid' : volumeid,
                    'read'     : 1,
                    'write'    : 1,
                    'locked'   : 0,
                })

            return jsonify({
                'api'        : 2.1,
                'cwd'        : cwd,
                'files'      : files,
                'options'    : {
                    'path'          : rel,
                    'url'           : '',
                    'tmbUrl'        : '',
                    'disabled'      : [],      # nothing globally disabled
                    'uploadMaxSize' : '64M'
                },
                'netDrivers' : [],
                'tree'       : [f for f in files if f.get('dirs',0) > 0],
            })

        # ─── MKDIR ─────────────────────────────────────────────────────────────
        if cmd == 'mkdir':
            cwd_hash = request.values.get('target','')
            abs_dir, rel = resolve_path(cwd_hash)
            names = request.values.getlist('name[]') or request.values.getlist('name')
            added = []
            for name in names:
                nm = secure_filename(name)
                path = os.path.join(abs_dir, nm)
                os.makedirs(path, exist_ok=True)
                rel_child = os.path.join(rel, nm)
                h = make_hash(rel_child)
                added.append({
                    'hash'     : h,
                    'phash'    : cwd_hash,
                    'name'     : nm,
                    'mime'     : 'directory',
                    'ts'       : int(os.path.getmtime(path)),
                    'size'     : 0,
                    'dirs'     : 1,
                    'volumeid' : volumeid,
                    'read'     : 1,
                    'write'    : 1,
                    'locked'   : 0,
                })
            return jsonify(added=added)

        # ─── UPLOAD ───────────────────────────────────────────────────────────
        if cmd == 'upload':
            cwd_hash = request.values.get('target','')
            abs_dir, rel = resolve_path(cwd_hash)
            uploaded = request.files.getlist('upload[]') or request.files.getlist('files[]')
            added = []
            for f in uploaded:
                filename = secure_filename(f.filename)
                dest = os.path.join(abs_dir, filename)
                f.save(dest)
                rel_child = os.path.join(rel, filename)
                h = make_hash(rel_child)
                added.append({
                    'hash'     : h,
                    'phash'    : cwd_hash,
                    'name'     : filename,
                    'mime'     : mimetypes.guess_type(dest)[0] or 'application/octet-stream',
                    'ts'       : int(os.path.getmtime(dest)),
                    'size'     : os.path.getsize(dest),
                    'dirs'     : 0,
                    'volumeid' : volumeid,
                    'read'     : 1,
                    'write'    : 1,
                    'locked'   : 0,
                })
            return jsonify(added=added)

        # ─── REMOVE ───────────────────────────────────────────────────────────
        if cmd == 'rm':
            targets = request.values.getlist('targets[]') or request.values.getlist('targets')
            removed = []
            for h in targets:
                try:
                    abs_path, _ = resolve_path(h)
                    if os.path.isdir(abs_path):
                        os.rmdir(abs_path)
                    else:
                        os.remove(abs_path)
                    removed.append(h)
                except:
                    pass
            return jsonify(removed=removed, sync=[])

        # unsupported command
        return jsonify(error=f"Unsupported command: {cmd}"), 400

    except PermissionError as pe:
        return jsonify(error=str(pe)), 403
    except Exception as e:
        current_app.logger.error("elFinder connector exception:\n" + traceback.format_exc())
        return jsonify(error=str(e)), 500

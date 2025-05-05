# routes/apps/elfinder_connector.py  (2025‑05‑05 fix‑02)
import os, base64, mimetypes, traceback
from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
from models.device import Device

elfinder_bp = Blueprint('elfinder_connector', __name__, url_prefix='/storage/connector')

# ───────────────────────── helpers ─────────────────────────
def _resolve_base_path(raw: str) -> str:
    root = current_app.config.get('STORAGE_ROOT', '/app/storage')
    return raw if os.path.isabs(raw) else os.path.join(root, raw.strip())

def _b64(s: str) -> str:
    """url‑safe base64 without trailing '=' """
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip('=')

def _b64pad(s: str) -> str:
    """add required padding back so base64 decode never fails"""
    return s + '=' * (-len(s) % 4)

# ───────────────────────── connector ────────────────────────
@elfinder_bp.route('', methods=['GET', 'POST'])
def connector():
    try:
        cmd    = request.values.get('cmd')
        dev_id = request.values.get('dev')
        current_app.logger.debug(f"[elFinder] cmd={cmd} dev={dev_id}")

        # base folder
        dev  = Device.query.get_or_404(dev_id)
        base = _resolve_base_path((dev.parameters or {}).get('base_path',''))
        if not os.path.isdir(base):
            return jsonify(error=f'Invalid base path: {base}'), 400

        volumeid = f"dev{dev_id}"

        # ── small helpers inside route ─────────────────────
        def make_hash(rel_path: str) -> str:
            rel_norm = '/' if rel_path == '' else rel_path
            return f"{volumeid}_{_b64(rel_norm)}"

        def resolve_path(hash_str: str):
            if not hash_str:
                rel = ''
            else:
                part = hash_str.split('_',1)[1] if '_' in hash_str else hash_str
                decoded = base64.urlsafe_b64decode(_b64pad(part)).decode()
                rel = '' if decoded in ('', '/') else decoded.lstrip('/')
            abs_path = os.path.normpath(os.path.join(base, rel))
            if not abs_path.startswith(os.path.normpath(base)):
                raise PermissionError("Access denied")
            return abs_path, rel

        # ───────────────────────── OPEN (dir listing) ───────────────────
        if cmd == 'open':
            abs_dir, rel = resolve_path(request.values.get('target', ''))
            cwd_hash = make_hash(rel)

            # 1️⃣  Build cwd entry
            cwd = {
                'hash'   : cwd_hash,
                'name'   : os.path.basename(abs_dir) or '/',
                'mime'   : 'directory',
                'ts'     : int(os.path.getmtime(abs_dir)),
                'size'   : 0,
                'dirs'   : 1,
                'volumeid': volumeid,
                'root'   : 1 if rel == '' else 0,
                'read'   : 1, 'write': 1, 'locked': 0,
            }
            if rel:                       # not at root → add parent pointer
                cwd['phash'] = make_hash(os.path.dirname(rel))

            files = [cwd]

            # 2️⃣  Add CHILDREN of the cwd
            for name in sorted(os.listdir(abs_dir)):
                if name.startswith('.'):
                    continue
                full      = os.path.join(abs_dir, name)
                rel_child = os.path.join(rel, name)
                files.append({
                    'hash'  : make_hash(rel_child),
                    'phash' : cwd_hash,
                    'name'  : name,
                    'mime'  : 'directory' if os.path.isdir(full)
                               else mimetypes.guess_type(full)[0] or 'application/octet-stream',
                    'ts'    : int(os.path.getmtime(full)),
                    'size'  : os.path.getsize(full) if os.path.isfile(full) else 0,
                    'dirs'  : 1 if os.path.isdir(full) else 0,
                    'volumeid': volumeid,
                    'read'  : 1, 'write': 1, 'locked': 0,
                })

            # 3️⃣  Add every ANCESTOR folder back to root
            parent_rel = rel
            while parent_rel:
                parent_rel = os.path.dirname(parent_rel)
                parent_abs = os.path.join(base, parent_rel) if parent_rel else base
                parent_hash = make_hash(parent_rel)
                entry = {
                    'hash'   : parent_hash,
                    'name'   : os.path.basename(parent_abs) or '/',
                    'mime'   : 'directory',
                    'ts'     : int(os.path.getmtime(parent_abs)),
                    'size'   : 0,
                    'dirs'   : 1,
                    'volumeid': volumeid,
                    'read'   : 1, 'write': 1, 'locked': 0,
                    'root'   : 1 if parent_rel == '' else 0,
                }
                if parent_rel:                         # still not root
                    entry['phash'] = make_hash(os.path.dirname(parent_rel))
                # prevent duplicates
                if entry['hash'] not in {f['hash'] for f in files}:
                    files.append(entry)

            # 4️⃣  Done
            return jsonify({
                'api'     : 2.1,
                'cwd'     : cwd,
                'files'   : files,
                'options' : {
                    'path'          : rel,
                    'url'           : '',
                    'tmbUrl'        : '',
                    'disabled'      : [],
                    'uploadMaxSize' : '64M'
                },
                'netDrivers': [],
                'tree'     : [f for f in files if f.get('dirs')],
            })
        # ───────────────────────── LS (names only) ─────────
        if cmd == 'ls':
            abs_dir, rel = resolve_path(request.values.get('target',''))
            only_dirs    = bool(request.values.get('mimes'))
            listing = [n for n in os.listdir(abs_dir)
                       if not n.startswith('.')
                       and (not only_dirs or os.path.isdir(os.path.join(abs_dir,n)))]
            return jsonify(list=listing)        # <- elFinder expects {list: [...]}

        # ───────────────────────── MKDIR ───────────────────
        if cmd == 'mkdir':
            cwd_hash = request.values.get('target','')
            abs_dir, rel_dir = resolve_path(cwd_hash)
            names = request.values.getlist('name[]') or request.values.getlist('name')
            added = []
            for nm in names:
                safe = secure_filename(nm)
                path = os.path.join(abs_dir, safe)
                os.makedirs(path, exist_ok=True)
                rel_child = os.path.join(rel_dir, safe)
                added.append({
                    'hash'  : make_hash(rel_child),
                    'phash' : cwd_hash,
                    'name'  : safe,
                    'mime'  : 'directory',
                    'ts'    : int(os.path.getmtime(path)),
                    'size'  : 0,
                    'dirs'  : 1,
                    'volumeid': volumeid,
                    'read'  : 1, 'write': 1, 'locked': 0,
                })
            return jsonify(added=added)

        # ───────────────────────── UPLOAD ──────────────────
        if cmd == 'upload':
            cwd_hash = request.values.get('target','')
            abs_dir, rel_dir = resolve_path(cwd_hash)
            uploads = request.files.getlist('upload[]') or request.files.getlist('files[]')
            added = []
            for f in uploads:
                fname = secure_filename(f.filename)
                dest  = os.path.join(abs_dir, fname)
                f.save(dest)
                rel_child = os.path.join(rel_dir, fname)
                added.append({
                    'hash'  : make_hash(rel_child),
                    'phash' : cwd_hash,
                    'name'  : fname,
                    'mime'  : mimetypes.guess_type(dest)[0] or 'application/octet-stream',
                    'ts'    : int(os.path.getmtime(dest)),
                    'size'  : os.path.getsize(dest),
                    'dirs'  : 0,
                    'volumeid': volumeid,
                    'read'  : 1, 'write': 1, 'locked': 0,
                })
            # elFinder likes cwd back so it can refresh the panel
            cwd = {'hash': cwd_hash}
            return jsonify(added=added, cwd=cwd, changed=[cwd_hash])

        # ───────────────────────── RM ──────────────────────
        if cmd == 'rm':
            targets = request.values.getlist('targets[]') or request.values.getlist('targets')
            removed=[]
            for h in targets:
                try:
                    abs_path,_=resolve_path(h)
                    if os.path.isdir(abs_path): os.rmdir(abs_path)
                    else: os.remove(abs_path)
                    removed.append(h)
                except Exception: pass
            return jsonify(removed=removed, sync=[])

        # ───────────────────────── FILE (preview) ───────────
        if cmd == 'file':
            abs_path,_ = resolve_path(request.values.get('target',''))
            return send_file(abs_path,
                             mimetype=mimetypes.guess_type(abs_path)[0] or 'application/octet-stream')

        # ───────────────────────── DOWNLOAD ────────────────
        if cmd == 'download':
            abs_path,_ = resolve_path(request.values.get('target',''))
            return send_file(abs_path,
                             mimetype='application/octet-stream',
                             as_attachment=True,
                             download_name=os.path.basename(abs_path))

        return jsonify(error=f"Unsupported command: {cmd}"),400

    except PermissionError as pe:
        return jsonify(error=str(pe)),403
    except Exception as exc:
        current_app.logger.error("elFinder connector exception:\n"+traceback.format_exc())
        return jsonify(error=str(exc)),500

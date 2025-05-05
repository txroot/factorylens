# routes/apps/elfinder_connector.py   ← full file with parents support
import os, base64, mimetypes, traceback
from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
from models.device import Device

elfinder_bp = Blueprint('elfinder_connector', __name__, url_prefix='/storage/connector')

# ───────────────────────── helpers ─────────────────────────
def _resolve_base_path(raw: str) -> str:
    root = current_app.config.get('STORAGE_ROOT', '/app/storage')
    return raw if os.path.isabs(raw) else os.path.join(root, raw.strip())

def _b64(s: str) -> str:      # url‑safe base64 (no padding)
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip('=')

def _b64pad(s: str) -> str:   # add padding back so decode never fails
    return s + '=' * (-len(s) % 4)

# ───────────────────────── connector ────────────────────────
@elfinder_bp.route('', methods=['GET', 'POST'])
def connector():
    try:
        cmd    = request.values.get('cmd')
        dev_id = request.values.get('dev')
        current_app.logger.debug(f"[elFinder] → cmd={cmd!r}, dev={dev_id!r}, "
                                 f"target={request.values.get('target')!r}")

        # base folder
        dev  = Device.query.get_or_404(dev_id)
        base = _resolve_base_path((dev.parameters or {}).get('base_path', ''))
        if not os.path.isdir(base):
            return jsonify(error=f'Invalid base path: {base}'), 400

        volumeid = f"dev{dev_id}"            # same ID for every call on this device

        # ── utilities ───────────────────────────────────────
        def make_hash(rel_path: str) -> str:
            rel_norm = rel_path if rel_path else '/'
            return f"{volumeid}_{_b64(rel_norm)}"

        def resolve_path(hash_str: str):
            if not hash_str:
                rel = ''
            else:
                part = hash_str.split('_', 1)[1] if '_' in hash_str else hash_str
                decoded = base64.urlsafe_b64decode(_b64pad(part)).decode()
                rel = '' if decoded in ('', '/') else decoded.lstrip('/')
            abs_path = os.path.normpath(os.path.join(base, rel))
            if not abs_path.startswith(os.path.normpath(base)):
                raise PermissionError("Access denied")
            return abs_path, rel

        # quick factory for directory entries (minimal fields)
        def dir_entry(full_abs: str, rel: str):
            entry = {
                'hash'    : make_hash(rel),
                'name'    : os.path.basename(full_abs) or '/',
                'mime'    : 'directory',
                'ts'      : int(os.path.getmtime(full_abs)),
                'size'    : 0,
                'dirs'    : 1,                   # announce it *may* have children
                'volumeid': volumeid,
                'read'    : 1, 'write': 1, 'locked': 0,
                'root'    : 1 if rel == '' else 0,
            }
            if rel:                              # not root → point to parent
                entry['phash'] = make_hash(os.path.dirname(rel))
            return entry

        # ───────────────────────── PARENTS ✧ NEW ✧ ─────────────────────────
        if cmd == 'parents':
            _, rel = resolve_path(request.values.get('target', ''))
            parents = []

            # walk from target‑dir up to root (excluding target itself)
            while rel:
                rel = os.path.dirname(rel)
                abs_path = os.path.join(base, rel) if rel else base
                parents.append(dir_entry(abs_path, rel))
            # add root entry if list is empty (target *was* the root)
            if not parents:
                parents.append(dir_entry(base, ''))

            return jsonify(tree=parents)

        # ───────────────────────── OPEN (dir listing) ───────────────────
        if cmd == 'open':
            abs_dir, rel = resolve_path(request.values.get('target', ''))
            cwd_hash = make_hash(rel)

            # 1️⃣ cwd
            cwd = dir_entry(abs_dir, rel)
            cwd['hash'] = cwd_hash   # (already the same, explicit for clarity)
            files = [cwd]

            # 2️⃣ children
            for name in sorted(os.listdir(abs_dir)):
                if name.startswith('.'):
                    continue
                full      = os.path.join(abs_dir, name)
                rel_child = os.path.join(rel, name)

                # does it itself contain *sub‑directories*?
                has_subdir = any(
                    os.path.isdir(os.path.join(full, p))
                    for p in os.listdir(full)
                ) if os.path.isdir(full) else 0

                entry = {
                    'hash'    : make_hash(rel_child),
                    'phash'   : cwd_hash,
                    'name'    : name,
                    'mime'    : 'directory' if os.path.isdir(full)
                                 else mimetypes.guess_type(full)[0] or 'application/octet-stream',
                    'ts'      : int(os.path.getmtime(full)),
                    'size'    : os.path.getsize(full) if os.path.isfile(full) else 0,
                    'dirs'    : 1 if has_subdir else 0,
                    'volumeid': volumeid,
                    'read'    : 1, 'write': 1, 'locked': 0,
                }
                files.append(entry)

            # 3️⃣ ancestors (for tree pane)
            parent_rel = rel
            while parent_rel:
                parent_rel = os.path.dirname(parent_rel)
                parent_abs = os.path.join(base, parent_rel) if parent_rel else base
                files.append(dir_entry(parent_abs, parent_rel))

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

        # ───────────────────────── LS ─────────────────────────────────
        if cmd == 'ls':
            abs_dir, rel = resolve_path(request.values.get('target',''))
            only_dirs    = bool(request.values.get('mimes'))
            listing = [
                n for n in os.listdir(abs_dir)
                if not n.startswith('.') and (not only_dirs or os.path.isdir(os.path.join(abs_dir,n)))
            ]
            current_app.logger.debug(f"[elFinder] ls → {listing}")
            return jsonify(list=listing)

        # ───────────────────────── MKDIR ───────────────────────────────
        if cmd == 'mkdir':
            abs_dir, rel_dir = resolve_path(request.values.get('target',''))
            names = request.values.getlist('name[]') or request.values.getlist('name')
            added = []
            for nm in names:
                safe = secure_filename(nm)
                path = os.path.join(abs_dir, safe)
                os.makedirs(path, exist_ok=True)
                rel_child = os.path.join(rel_dir, safe)
                entry = {
                    'hash': make_hash(rel_child),
                    'phash': request.values.get('target',''),
                    'name': safe,
                    'mime': 'directory',
                    'ts': int(os.path.getmtime(path)),
                    'size': 0,
                    'dirs': 1,
                    'volumeid': volumeid,
                    'read': 1, 'write': 1, 'locked': 0,
                }
                added.append(entry)
            current_app.logger.debug(f"[elFinder] mkdir → {added}")
            return jsonify(added=added)

        # ───────────────────────── UPLOAD ─────────────────────────────
        if cmd == 'upload':
            cwd_hash = request.values.get('target','')
            abs_dir, rel_dir = resolve_path(cwd_hash)
            uploads = request.files.getlist('upload[]') or request.files.getlist('files[]')
            added = []
            for f in uploads:
                name = secure_filename(f.filename)
                dest = os.path.join(abs_dir, name)
                f.save(dest)
                rel_child = os.path.join(rel_dir, name)
                entry = {
                    'hash': make_hash(rel_child),
                    'phash': cwd_hash,
                    'name': name,
                    'mime': mimetypes.guess_type(dest)[0] or 'application/octet-stream',
                    'ts': int(os.path.getmtime(dest)),
                    'size': os.path.getsize(dest),
                    'dirs': 0,
                    'volumeid': volumeid,
                    'read': 1, 'write': 1, 'locked': 0,
                }
                added.append(entry)
            current_app.logger.debug(f"[elFinder] upload → {added}")
            # include cwd so elFinder will refresh that folder
            return jsonify(added=added, cwd={'hash': cwd_hash}, changed=[cwd_hash])

        # ───────────────────────── RM ─────────────────────────────────
        if cmd == 'rm':
            targets = request.values.getlist('targets[]') or request.values.getlist('targets')
            removed = []
            for h in targets:
                try:
                    abs_path,_ = resolve_path(h)
                    if os.path.isdir(abs_path):
                        os.rmdir(abs_path)
                    else:
                        os.remove(abs_path)
                    removed.append(h)
                except Exception as e:
                    current_app.logger.error(f"[elFinder] rm error on {h}: {e}")
            current_app.logger.debug(f"[elFinder] rm → removed {removed}")
            return jsonify(removed=removed, sync=[])

        # ───────────────────────── FILE (preview) ───────────────────────
        if cmd == 'file':
            abs_path,_ = resolve_path(request.values.get('target',''))
            current_app.logger.debug(f"[elFinder] file → send {abs_path}")
            return send_file(
                abs_path,
                mimetype=mimetypes.guess_type(abs_path)[0] or 'application/octet-stream'
            )

        # ───────────────────────── DOWNLOAD ──────────────────────────────
        if cmd == 'download':
            abs_path,_ = resolve_path(request.values.get('target',''))
            current_app.logger.debug(f"[elFinder] download → send {abs_path}")
            return send_file(
                abs_path,
                mimetype='application/octet-stream',
                as_attachment=True,
                download_name=os.path.basename(abs_path)
            )

        # ───────────────────────── UNSUPPORTED ──────────────────────────
        msg = f"Unsupported command: {cmd}"
        current_app.logger.error(f"[elFinder] {msg}")
        return jsonify(error=msg), 400

    except PermissionError as pe:
        current_app.logger.error(f"[elFinder] PermissionError: {pe}")
        return jsonify(error=str(pe)), 403

    except Exception:
        tb = traceback.format_exc()
        current_app.logger.error(f"[elFinder] Exception:\n{tb}")
        return jsonify(error="Internal server error"), 500

# routes/apps/elfinder_connector.py
import os
import base64
import mimetypes
import shutil
import traceback
from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename
from models.device import Device

elfinder_bp = Blueprint('elfinder_connector', __name__, url_prefix='/storage/connector')

# ───────────────────────── helpers ─────────────────────────
def _resolve_base_path(raw: str) -> str:
    root = current_app.config.get('STORAGE_ROOT', '/app/storage')
    return raw if os.path.isabs(raw) else os.path.join(root, raw.strip())

def _b64(s: str) -> str:      # url-safe base64 (no padding)
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip('=')

def _b64pad(s: str) -> str:   # add padding back so decode never fails
    return s + '=' * (-len(s) % 4)

# ───────────────────────── connector ────────────────────────
@elfinder_bp.route('', methods=['GET', 'POST'])
def connector():
    try:
        cmd    = request.values.get('cmd')
        dev_id = request.values.get('dev')
        target = request.values.get('target') or ''
        current_app.logger.debug(f"[elFinder] cmd={cmd!r}, dev={dev_id!r}, target={target!r}")

        # 1) lookup device
        dev  = Device.query.get_or_404(dev_id)
        base = _resolve_base_path((dev.parameters or {}).get('base_path',''))
        if not os.path.isdir(base):
            return jsonify(error=f'Invalid base path: {base}'), 400

        volumeid = f"dev{dev_id}"

        # ── utilities ───────────────────────────────────────
        def make_hash(rel_path: str) -> str:
            norm = rel_path if rel_path else '/'
            return f"{volumeid}_{_b64(norm)}"

        def resolve_path(hash_str: str):
            if not hash_str:
                rel = ''
            else:
                part = hash_str.split('_',1)[1] if '_' in hash_str else hash_str
                decoded = base64.urlsafe_b64decode(_b64pad(part)).decode()
                rel = '' if decoded in ('','/') else decoded.lstrip('/')
            abs_path = os.path.normpath(os.path.join(base, rel))
            if not abs_path.startswith(os.path.normpath(base)):
                raise PermissionError("Access denied")
            return abs_path, rel

        def dir_entry(abs_path: str, rel: str):
            e = {
                'hash'    : make_hash(rel),
                'name'    : os.path.basename(abs_path) or '/',
                'mime'    : 'directory',
                'ts'      : int(os.path.getmtime(abs_path)),
                'size'    : 0,
                'dirs'    : 1,
                'volumeid': volumeid,
                'read'    : 1, 'write': 1, 'locked': 0,
                'root'    : 1 if rel=='' else 0,
            }
            if rel:
                e['phash'] = make_hash(os.path.dirname(rel))
            return e

        # ───────────────────────── PARENTS ─────────────────────────
        if cmd == 'parents':
            abs_dir, rel = resolve_path(target)
            parents = []
            while rel:
                rel = os.path.dirname(rel)
                abs_p = os.path.join(base, rel) if rel else base
                parents.append(dir_entry(abs_p, rel))
            if not parents:
                parents.append(dir_entry(base, ''))
            return jsonify(tree=parents)

        # ───────────────────────── OPEN ────────────────────────────
        if cmd == 'open':
            abs_dir, rel = resolve_path(target)
            cwd_hash = make_hash(rel)
            cwd = dir_entry(abs_dir, rel)
            cwd['hash'] = cwd_hash
            files = [cwd]
            # children
            for name in sorted(os.listdir(abs_dir)):
                if name.startswith('.'): continue
                full = os.path.join(abs_dir, name)
                rel_child = os.path.join(rel, name)
                has_sub = any(os.path.isdir(os.path.join(full,f)) for f in os.listdir(full)) if os.path.isdir(full) else 0
                files.append({
                    'hash'    : make_hash(rel_child),
                    'phash'   : cwd_hash,
                    'name'    : name,
                    'mime'    : 'directory' if os.path.isdir(full)
                                 else mimetypes.guess_type(full)[0] or 'application/octet-stream',
                    'ts'      : int(os.path.getmtime(full)),
                    'size'    : os.path.getsize(full) if os.path.isfile(full) else 0,
                    'dirs'    : 1 if has_sub else 0,
                    'volumeid': volumeid,
                    'read'    : 1, 'write': 1, 'locked': 0,
                })
            # ancestors for tree
            pr = rel
            while pr:
                pr = os.path.dirname(pr)
                abs_p = os.path.join(base,pr) if pr else base
                files.append(dir_entry(abs_p, pr))
            return jsonify({
                'api'     : 2.1,
                'cwd'     : cwd,
                'files'   : files,
                'options' : {'path': rel,'url':'','tmbUrl':'','disabled':[],'uploadMaxSize':'64M'},
                'netDrivers':[],
                'tree'    : [f for f in files if f.get('dirs')]
            })

        # ───────────────────────── LS ──────────────────────────────
        if cmd == 'ls':
            abs_dir, _ = resolve_path(target)
            only_dirs = bool(request.values.get('mimes'))
            listing = [n for n in os.listdir(abs_dir)
                       if not n.startswith('.') and (not only_dirs or os.path.isdir(os.path.join(abs_dir,n)))]
            return jsonify(list=listing)

        # ───────────────────────── MKDIR ───────────────────────────
        if cmd == 'mkdir':
            abs_dir, rel = resolve_path(target)
            names = request.values.getlist('name[]') or request.values.getlist('name')
            added = []
            for nm in names:
                safe = secure_filename(nm)
                newp = os.path.join(abs_dir, safe)
                os.makedirs(newp, exist_ok=True)
                added.append(dir_entry(newp, os.path.join(rel, safe)))
            return jsonify(added=added)

        # ───────────────────────── UPLOAD ──────────────────────────
        if cmd == 'upload':
            abs_dir, rel = resolve_path(target)
            files = request.files.getlist('upload[]') or request.files.getlist('files[]')
            added = []
            for f in files:
                fn = secure_filename(f.filename)
                dest = os.path.join(abs_dir,fn)
                f.save(dest)
                added.append({
                    'hash'    : make_hash(os.path.join(rel,fn)),
                    'phash'   : make_hash(rel),
                    'name'    : fn,
                    'mime'    : mimetypes.guess_type(dest)[0] or 'application/octet-stream',
                    'ts'      : int(os.path.getmtime(dest)),
                    'size'    : os.path.getsize(dest),
                    'dirs'    : 0,
                    'volumeid': volumeid,
                    'read'    : 1,'write':1,'locked':0
                })
            return jsonify(added=added, cwd={'hash': make_hash(rel)}, changed=[make_hash(rel)])

        # ───────────────────────── RM ──────────────────────────────
        if cmd == 'rm':
            targets = request.values.getlist('targets[]') or request.values.getlist('targets')
            removed = []
            for h in targets:
                try:
                    path, _ = resolve_path(h)
                    if os.path.isdir(path): os.rmdir(path)
                    else: os.remove(path)
                    removed.append(h)
                except: pass
            return jsonify(removed=removed, sync=[])

        # ───────────────────────── PASTE ✧ CUT & COPY ─────────────
        if cmd == 'paste':
            # targets[] = hashes, dst = hash of destination dir, cut = "1" or "0"
            targets = request.values.getlist('targets[]')
            dst_hash = request.values.get('dst','')
            cut_flag = request.values.get('cut') == '1'
            abs_dst, rel_dst = resolve_path(dst_hash)
            added = []
            removed = []
            for h in targets:
                abs_src, rel_src = resolve_path(h)
                name = os.path.basename(abs_src)
                abs_new = os.path.join(abs_dst, name)
                if cut_flag:
                    os.rename(abs_src, abs_new)
                    removed.append(h)
                else:
                    # copy
                    if os.path.isdir(abs_src):
                        shutil.copytree(abs_src, abs_new)
                    else:
                        shutil.copy2(abs_src, abs_new)
                added.append(dir_entry(abs_new, os.path.join(rel_dst, name)))
            resp = {'added': added}
            if cut_flag:
                resp['removed'] = removed
            return jsonify(resp)

        # ───────────────────────── FILE (preview) ───────────────────
        if cmd == 'file':
            abs_p, _ = resolve_path(target)
            return send_file(abs_p,
                             mimetype=mimetypes.guess_type(abs_p)[0] or 'application/octet-stream')

        # ───────────────────────── DOWNLOAD ──────────────────────────
        if cmd == 'download':
            abs_p, _ = resolve_path(target)
            return send_file(abs_p,
                             mimetype='application/octet-stream',
                             as_attachment=True,
                             download_name=os.path.basename(abs_p))

        # ───────────────────────── UNSUPPORTED ───────────────────────
        return jsonify(error=f"Unsupported command: {cmd}"), 400

    except PermissionError as pe:
        return jsonify(error=str(pe)), 403
    except Exception:
        tb = traceback.format_exc()
        current_app.logger.error(f"[elFinder] exception:\n{tb}")
        return jsonify(error="Internal server error"), 500

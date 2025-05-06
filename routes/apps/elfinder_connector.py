# routes/apps/elfinder_connector.py

import os
import stat
import base64
import mimetypes
import shutil
import traceback

from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    send_file,
)
from werkzeug.utils import secure_filename
import paramiko

from models.device import Device

elfinder_bp = Blueprint('elfinder_connector', __name__, url_prefix='/storage/connector')


def _b64(s: str) -> str:
    """URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(s.encode('utf-8')).decode('utf-8').rstrip('=')


def _b64pad(s: str) -> str:
    """Re-add padding for base64 decode."""
    return s + '=' * (-len(s) % 4)


def _resolve_local_base(raw: str) -> str:
    """Resolve a base path under STORAGE_ROOT unless absolute."""
    if os.path.isabs(raw):
        return raw
    root = current_app.config.get('STORAGE_ROOT', '/app/storage')
    return os.path.join(root, raw.strip())


def _open_sftp(params):
    """Open an SFTP session and chdir into the remote root."""
    host     = params['host']
    port     = int(params.get('port', 22))
    username = params.get('username')
    password = params.get('password')
    rp       = params.get('root_path', '/').rstrip('/')
    remote_root = rp or '/'

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        port=port,
        username=username,
        password=password,
        allow_agent=False,
        look_for_keys=False,
        timeout=10,
    )
    sftp = client.open_sftp()
    try:
        sftp.chdir(remote_root)
    except (IOError, FileNotFoundError):
        client.close()
        raise ValueError(f"SFTP: remote path not found: {remote_root}")

    current_app.logger.info(
        f"[elFinder][SFTP] connected to {username}@{host}:{port}, root={remote_root}"
    )
    return client, sftp, remote_root


@elfinder_bp.route('', methods=['GET', 'POST'])
def connector():
    try:
        cmd    = request.values.get('cmd')
        dev_id = request.values.get('dev')
        target = request.values.get('target', '')
        current_app.logger.debug(f"[elFinder] cmd={cmd!r}, dev={dev_id!r}, target={target!r}")

        # Lookup device
        dev    = Device.query.get_or_404(dev_id)
        params = dev.parameters or {}
        proto  = params.get('protocol', 'local').lower()

        # Choose storage backend
        is_sftp = False
        ssh = sftp = None
        if proto == 'sftp':
            ssh, sftp, base = _open_sftp(params)
            is_sftp = True
            remote_root = base
        else:
            base = _resolve_local_base(params.get('base_path', ''))

        if not (is_sftp or os.path.isdir(base)):
            return jsonify(error=f"Invalid base path: {base}"), 400

        volumeid = f"dev{dev_id}"

        def make_hash(rel_path: str) -> str:
            """Encode a relative path into elFinder’s hash."""
            norm = rel_path or '/'
            return f"{volumeid}_{_b64(norm)}"

        def resolve_path(hash_str: str):
            """Turn elFinder hash back into (abs_path, rel_path)."""
            if not hash_str:
                rel = ''
            else:
                part = hash_str.split('_', 1)[1] if '_' in hash_str else hash_str
                decoded = base64.urlsafe_b64decode(_b64pad(part)).decode('utf-8')
                rel = '' if decoded in ('', '/') else decoded.lstrip('/')
            if is_sftp:
                abs_path = f"{remote_root}/{rel}" if rel else remote_root
            else:
                abs_path = os.path.normpath(os.path.join(base, rel))
                if not abs_path.startswith(os.path.normpath(base)):
                    raise PermissionError("Access denied")
            return abs_path, rel

        def list_dir(abs_dir: str):
            """List directory entries for open/tree commands."""
            items = []
            if is_sftp:
                for attr in sftp.listdir_attr(abs_dir):
                    name = attr.filename
                    if name.startswith('.'):
                        continue
                    full = f"{abs_dir}/{name}"
                    items.append((name, full, stat.S_ISDIR(attr.st_mode), attr.st_size, attr.st_mtime))
            else:
                for name in sorted(os.listdir(abs_dir)):
                    if name.startswith('.'):
                        continue
                    full = os.path.join(abs_dir, name)
                    items.append((
                        name,
                        full,
                        os.path.isdir(full),
                        os.path.getsize(full) if os.path.isfile(full) else 0,
                        int(os.path.getmtime(full))
                    ))
            return items

        # ─── PARENTS (breadcrumb) ────────────────────────────────────
        if cmd == 'parents':
            abs_dir, rel = resolve_path(target)
            crumbs = []
            while rel:
                rel = os.path.dirname(rel)
                abs_p = f"{remote_root}/{rel}" if is_sftp else os.path.join(base, rel)
                ts    = int(sftp.stat(abs_p).st_mtime) if is_sftp else int(os.path.getmtime(abs_p))
                crumbs.append({
                    'hash'    : make_hash(rel),
                    'name'    : os.path.basename(rel) or '/',
                    'mime'    : 'directory',
                    'ts'      : ts,
                    'size'    : 0,
                    'dirs'    : 1,
                    'volumeid': volumeid,
                    'read'    : 1, 'write': 1, 'locked': 0
                })
            # root if no crumbs
            if not crumbs:
                ts = int(sftp.stat(remote_root).st_mtime) if is_sftp else int(os.path.getmtime(base))
                crumbs.append({
                    'hash'    : make_hash(''),
                    'name'    : '/',
                    'mime'    : 'directory',
                    'ts'      : ts,
                    'size'    : 0,
                    'dirs'    : 1,
                    'volumeid': volumeid,
                    'read'    : 1, 'write': 1, 'locked': 0
                })
            if is_sftp:
                sftp.close()
                ssh.close()
            return jsonify(tree=crumbs)

        # ─── TREE (subdir nodes) ────────────────────────────────────
        if cmd == 'tree':
            abs_dir, rel = resolve_path(target)
            nodes = []
            for name, full, is_dir, _, mtime in list_dir(abs_dir):
                if not is_dir:
                    continue
                child_rel = os.path.join(rel, name)
                # whether this child has subdirs
                has_sub = any(attr_is_dir for _, _, attr_is_dir, _, _ in list_dir(full))
                nodes.append({
                    'hash'    : make_hash(child_rel),
                    'phash'   : make_hash(rel),
                    'name'    : name,
                    'mime'    : 'directory',
                    'ts'      : mtime,
                    'dirs'    : 1 if has_sub else 0,
                    'volumeid': volumeid,
                    'read'    : 1, 'write': 1, 'locked': 0
                })
            if is_sftp:
                sftp.close()
                ssh.close()
            return jsonify(tree=nodes)

        # ─── OPEN (list cwd and children) ───────────────────────────
        if cmd == 'open':
            abs_dir, rel = resolve_path(target)
            cwd_hash     = make_hash(rel)
            # cwd entry
            ts = int(sftp.stat(abs_dir).st_mtime) if is_sftp else int(os.path.getmtime(abs_dir))
            cwd = {
                'hash'    : cwd_hash,
                'name'    : os.path.basename(rel) or '/',
                'mime'    : 'directory',
                'ts'      : ts,
                'size'    : 0,
                'dirs'    : 1,
                'volumeid': volumeid,
                'root'    : 1 if rel == '' else 0,
                'read'    : 1, 'write': 1, 'locked': 0
            }
            if rel:
                cwd['phash'] = make_hash(os.path.dirname(rel))

            files = [cwd]
            for name, full, is_dir, size, mtime in list_dir(abs_dir):
                files.append({
                    'hash'    : make_hash(os.path.join(rel, name)),
                    'phash'   : cwd_hash,
                    'name'    : name,
                    'mime'    : 'directory' if is_dir else (mimetypes.guess_type(full)[0] or 'application/octet-stream'),
                    'ts'      : mtime,
                    'size'    : size,
                    'dirs'    : 1 if is_dir else 0,
                    'volumeid': volumeid,
                    'read'    : 1, 'write': 1, 'locked': 0
                })

            resp = {
                'api'     : 2.1,
                'cwd'     : cwd,
                'files'   : files,
                'options' : {
                    'path'          : rel,
                    'url'           : '',
                    'tmbUrl'        : '',
                    'disabled'      : [],
                    'uploadMaxSize' : '64M',
                    'sftpConnected': is_sftp
                },
                'netDrivers': [],
                'tree'      : [f for f in files if f.get('dirs')]
            }
            if is_sftp:
                sftp.close()
                ssh.close()
            return jsonify(resp)

        # ─── LS (just names) ────────────────────────────────────────
        if cmd == 'ls':
            abs_dir, _ = resolve_path(target)
            only_dirs = bool(request.values.get('mimes'))
            names = []
            for n in os.listdir(abs_dir):
                if n.startswith('.'):
                    continue
                path = os.path.join(abs_dir, n)
                if only_dirs and not os.path.isdir(path):
                    continue
                names.append(n)
            return jsonify(list=names)

        # ─── MKDIR ───────────────────────────────────────────────────
        if cmd == 'mkdir':
            abs_dir, rel = resolve_path(target)
            names = request.values.getlist('name[]') or request.values.getlist('name')
            added = []
            for nm in names:
                safe = secure_filename(nm)
                newp = os.path.join(abs_dir, safe)
                os.makedirs(newp, exist_ok=True)
                ts = int(os.path.getmtime(newp))
                added.append({
                    'hash'    : make_hash(os.path.join(rel, safe)),
                    'phash'   : make_hash(rel),
                    'name'    : safe,
                    'mime'    : 'directory',
                    'ts'      : ts,
                    'size'    : 0,
                    'dirs'    : 1,
                    'volumeid': volumeid,
                    'read'    : 1, 'write': 1, 'locked': 0
                })
            return jsonify(added=added)

        # ─── UPLOAD ──────────────────────────────────────────────────
        if cmd == 'upload':
            abs_dir, rel = resolve_path(target)
            upload_files = request.files.getlist('upload[]') or request.files.getlist('files[]')
            added = []
            for f in upload_files:
                fn   = secure_filename(f.filename)
                dest = os.path.join(abs_dir, fn)
                f.save(dest)
                ts = int(os.path.getmtime(dest))
                added.append({
                    'hash'    : make_hash(os.path.join(rel, fn)),
                    'phash'   : make_hash(rel),
                    'name'    : fn,
                    'mime'    : mimetypes.guess_type(dest)[0] or 'application/octet-stream',
                    'ts'      : ts,
                    'size'    : os.path.getsize(dest),
                    'dirs'    : 0,
                    'volumeid': volumeid,
                    'read'    : 1, 'write': 1, 'locked': 0
                })
            return jsonify(added=added)

        # ─── RM ─────────────────────────────────────────────────────
        if cmd == 'rm':
            targets = request.values.getlist('targets[]') or request.values.getlist('targets')
            removed = []
            for h in targets:
                try:
                    path, _ = resolve_path(h)
                    if os.path.isdir(path):
                        os.rmdir(path)
                    else:
                        os.remove(path)
                    removed.append(h)
                except Exception:
                    continue
            return jsonify(removed=removed, sync=[])

        # ─── PASTE (cut/copy) ───────────────────────────────────────
        if cmd == 'paste':
            targets = request.values.getlist('targets[]')
            dst_hash = request.values.get('dst', '')
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
                    if os.path.isdir(abs_src):
                        shutil.copytree(abs_src, abs_new)
                    else:
                        shutil.copy2(abs_src, abs_new)
                ts = int(os.path.getmtime(abs_new))
                added.append({
                    'hash'    : make_hash(os.path.join(rel_dst, name)),
                    'phash'   : make_hash(rel_dst),
                    'name'    : name,
                    'mime'    : 'directory' if os.path.isdir(abs_new)
                                    else (mimetypes.guess_type(abs_new)[0] or 'application/octet-stream'),
                    'ts'      : ts,
                    'size'    : os.path.getsize(abs_new) if os.path.isfile(abs_new) else 0,
                    'dirs'    : 1 if os.path.isdir(abs_new) else 0,
                    'volumeid': volumeid,
                    'read'    : 1, 'write': 1, 'locked': 0
                })
            resp = {'added': added}
            if cut_flag:
                resp['removed'] = removed
            return jsonify(resp)

        # ─── FILE (preview/send inline) ─────────────────────────────
        if cmd == 'file':
            abs_p, _ = resolve_path(target)
            mimetype = mimetypes.guess_type(abs_p)[0] or 'application/octet-stream'
            if is_sftp:
                # fetch remote file into memory
                import io
                buf = io.BytesIO()
                sftp.getfo(abs_p, buf)
                buf.seek(0)
                # close SSH/SFTP before responding
                sftp.close()
                ssh.close()
                return send_file(buf, mimetype=mimetype)
            else:
                return send_file(abs_p, mimetype=mimetype)

        # ─── DOWNLOAD (attachment) ─────────────────────────────────
        if cmd == 'download':
            abs_p, _ = resolve_path(target)
            if is_sftp:
                import io
                buf = io.BytesIO()
                sftp.getfo(abs_p, buf)
                buf.seek(0)
                sftp.close()
                ssh.close()
                return send_file(
                    buf,
                    mimetype='application/octet-stream',
                    as_attachment=True,
                    download_name=os.path.basename(abs_p)
                )
            else:
                return send_file(
                    abs_p,
                    mimetype='application/octet-stream',
                    as_attachment=True,
                    download_name=os.path.basename(abs_p)
                )

        # ─── Unsupported command ────────────────────────────────────
        return jsonify(error=f"Unsupported command: {cmd}"), 400

    except PermissionError as pe:
        return jsonify(error=str(pe)), 403

    except Exception:
        tb = traceback.format_exc()
        current_app.logger.error(f"[elFinder] exception:\n{tb}")
        return jsonify(error="Internal server error"), 500

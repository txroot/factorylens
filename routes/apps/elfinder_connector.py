# routes/apps/elfinder_connector.py

import os
import stat
import base64
import mimetypes
import traceback

from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    send_file
)
from werkzeug.utils import secure_filename
from models.device import Device

# Paramiko for SFTP
import paramiko

elfinder_bp = Blueprint(
    'elfinder_connector',
    __name__,
    url_prefix='/storage/connector'
)


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode('utf-8')).decode('utf-8').rstrip('=')


def _b64pad(s: str) -> str:
    return s + '=' * (-len(s) % 4)


def _resolve_local_base(raw: str) -> str:
    if os.path.isabs(raw):
        return raw
    root = current_app.config.get('STORAGE_ROOT', '/app/storage')
    return os.path.join(root, raw.strip())


def _open_sftp(params):
    host      = params['host']
    port      = int(params.get('port', 22))
    username  = params.get('username')
    password  = params.get('password')
    rp        = params.get('root_path', '/')
    remote_root = rp if rp == '/' else rp.rstrip('/')

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        port=port,
        username=username,
        password=password,
        allow_agent=False,
        look_for_keys=False,
        timeout=10
    )
    sftp = client.open_sftp()
    try:
        sftp.chdir(remote_root)
    except (IOError, FileNotFoundError):
        raise ValueError(f"SFTP: remote path not found: {remote_root}")

    current_app.logger.info(f"[elFinder][SFTP] connected to {username}@{host}:{port}, root={remote_root}")
    return client, sftp, remote_root


@elfinder_bp.route('', methods=['GET', 'POST'])
def connector():
    try:
        cmd    = request.values.get('cmd')
        dev_id = request.values.get('dev')
        target = request.values.get('target', '')
        current_app.logger.debug(f"[elFinder] cmd={cmd!r}, dev={dev_id!r}, target={target!r}")

        dev    = Device.query.get_or_404(dev_id)
        params = dev.parameters or {}
        proto  = params.get('protocol', 'local').lower()

        is_sftp = False
        ssh = sftp = None

        # Choose backend
        if proto == 'sftp':
            try:
                ssh, sftp, remote_root = _open_sftp(params)
                base = remote_root
                is_sftp = True
            except Exception as e:
                msg = f"SFTP connection failed: {e}"
                current_app.logger.error(f"[elFinder][SFTP] {msg}")
                return jsonify(error=msg), 503
        else:
            base = _resolve_local_base(params.get('base_path',''))

        if not (is_sftp or os.path.isdir(base)):
            return jsonify(error=f"Invalid base path: {base}"), 400

        volumeid = f"dev{dev_id}"

        def make_hash(rel_path: str) -> str:
            norm = rel_path or '/'
            return f"{volumeid}_{_b64(norm)}"

        def resolve_path(hash_str: str):
            if not hash_str:
                rel = ''
            else:
                part = hash_str.split('_', 1)[1] if '_' in hash_str else hash_str
                decoded = base64.urlsafe_b64decode(_b64pad(part)).decode('utf-8')
                rel = '' if decoded in ('','/') else decoded.lstrip('/')
            if is_sftp:
                remote = f"{remote_root}/{rel}" if rel else remote_root
                return remote, rel
            else:
                local = os.path.normpath(os.path.join(base, rel))
                if not local.startswith(os.path.normpath(base)):
                    raise PermissionError("Access denied")
                return local, rel

        def list_dir(abs_dir):
            items = []
            if is_sftp:
                for attr in sftp.listdir_attr(abs_dir):
                    name = attr.filename
                    if name.startswith('.'): continue
                    full = f"{abs_dir}/{name}"
                    items.append((
                        name,
                        full,
                        stat.S_ISDIR(attr.st_mode),
                        attr.st_size,
                        attr.st_mtime
                    ))
            else:
                for name in sorted(os.listdir(abs_dir)):
                    if name.startswith('.'): continue
                    full = os.path.join(abs_dir, name)
                    items.append((
                        name,
                        full,
                        os.path.isdir(full),
                        os.path.getsize(full) if os.path.isfile(full) else 0,
                        int(os.path.getmtime(full))
                    ))
            return items

        # ─── PARENTS (breadcrumb) ─────────────────────────────────────────
        if cmd == 'parents':
            abs_dir, rel = resolve_path(target)
            parents = []
            cur = rel
            while cur:
                cur = os.path.dirname(cur)
                pr_abs = f"{remote_root}/{cur}" if is_sftp else os.path.join(base, cur)
                parents.append({
                    'hash'    : make_hash(cur),
                    'name'    : os.path.basename(cur) or '/',
                    'mime'    : 'directory',
                    'ts'      : int(sftp.stat(pr_abs).st_mtime) if is_sftp else int(os.path.getmtime(pr_abs)),
                    'size'    : 0,
                    'dirs'    : 1,
                    'volumeid': volumeid,
                    'read'    : 1, 'write': 1, 'locked': 0
                })
            if not parents:
                # root itself
                parents.append({
                    'hash'    : make_hash(''),
                    'name'    : '/',
                    'mime'    : 'directory',
                    'ts'      : int(sftp.stat(remote_root).st_mtime) if is_sftp else int(os.path.getmtime(base)),
                    'size'    : 0,
                    'dirs'    : 1,
                    'volumeid': volumeid,
                    'read'    : 1, 'write': 1, 'locked': 0
                })
            if is_sftp:
                sftp.close(); ssh.close()
            return jsonify(tree=parents)

        # ─── TREE (subdirs for tree pane) ───────────────────────────────────
        if cmd == 'tree':
            abs_dir, rel = resolve_path(target)
            nodes = []

            for name, full, is_dir, _, mtime in list_dir(abs_dir):
                if not is_dir:
                    continue    # tree shows only dirs
                child_rel = os.path.join(rel, name)

                # does the child itself contain sub‑dirs? (to show little ▶ triangle)
                has_sub = any(
                    entry_is_dir
                    for _, __, entry_is_dir, ___, ____ in list_dir(full)
                )

                nodes.append({
                    'hash'    : make_hash(child_rel),
                    'phash'   : make_hash(rel),        # ← parent hash is required
                    'name'    : name,
                    'mime'    : 'directory',
                    'ts'      : mtime,                 # ← NEW
                    'dirs'    : 1 if has_sub else 0,   # 1 = may have children
                    'volumeid': volumeid,              # ← NEW
                    'read'    : 1, 'write': 1, 'locked': 0
                })

            if is_sftp:
                sftp.close(); ssh.close()

            return jsonify(tree=nodes)

        # ─── OPEN (dir listing) ────────────────────────────────────────────
        if cmd == 'open':
            abs_dir, rel = resolve_path(target)
            cwd_hash     = make_hash(rel)

            # timestamp
            if is_sftp:
                ts = int(sftp.stat(abs_dir).st_mtime)
            else:
                children = list_dir(abs_dir)
                ts = int(children[0][4]) if (not rel and children) else int(os.path.getmtime(abs_dir))

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
                    'mime'    : 'directory' if is_dir else mimetypes.guess_type(full)[0] or 'application/octet-stream',
                    'ts'      : mtime,
                    'size'    : size,
                    'dirs'    : 1 if is_dir else 0,
                    'volumeid': volumeid,
                    'read'    : 1, 'write': 1, 'locked': 0
                })

            # add ancestor entries
            parent = rel
            while parent:
                parent = os.path.dirname(parent)
                pa_abs = f"{remote_root}/{parent}" if is_sftp else os.path.join(base, parent)
                files.append({
                    'hash'    : make_hash(parent),
                    'name'    : os.path.basename(parent) or '/',
                    'mime'    : 'directory',
                    'ts'      : int(sftp.stat(pa_abs).st_mtime) if is_sftp else int(os.path.getmtime(pa_abs)),
                    'size'    : 0,
                    'dirs'    : 1,
                    'volumeid': volumeid,
                    'root'    : 1 if parent == '' else 0,
                    'read'    : 1, 'write': 1, 'locked': 0
                })

            resp = {
                'api'        : 2.1,
                'cwd'        : cwd,
                'files'      : files,
                'options'    : {
                    'path'          : rel,
                    'url'           : '',
                    'tmbUrl'        : '',
                    'disabled'      : [],
                    'uploadMaxSize' : '64M',
                    'sftpConnected': is_sftp
                },
                'netDrivers' : [],
                'tree'       : [f for f in files if f.get('dirs')]
            }

            if is_sftp:
                sftp.close(); ssh.close()

            return jsonify(resp)

        # ─── MKDIR, UPLOAD, RM, FILE, DOWNLOAD (same as before) ───────────
        # … (keep your existing implementations for mkdir, upload, rm, file, download) …

        return jsonify(error=f"Unsupported command: {cmd}"), 400

    except PermissionError as pe:
        return jsonify(error=str(pe)), 403

    except Exception:
        tb = traceback.format_exc()
        current_app.logger.error(f"[elFinder] Exception:\n{tb}")
        return jsonify(error="Internal server error"), 500

"""
elFinder JSON connector (v2.1 API) with pluggable protocol drivers.

Supported protocols   : local filesystem, SFTP
Add more              : create a driver in storage_drivers.py and map it below
Blueprint URL prefix  : /storage/connector
"""

from __future__ import annotations

import base64
import io
import mimetypes
import os
import traceback
from typing import Dict

from flask import (
    Blueprint,
    jsonify,
    request,
    send_file,
    current_app,
)
from models.device import Device

from storage_drivers import LocalDriver, SFTPDriver, BaseDriver, DirEntry

elfinder_bp = Blueprint("elfinder_connector", __name__, url_prefix="/storage/connector")


# ────────────────────────── helpers ──────────────────────────────
def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def _b64pad(s: str) -> str:
    return s + "=" * (-len(s) % 4)


def _driver_for(dev) -> BaseDriver:
    """Instantiate the correct protocol driver for *dev*."""
    params = dev.parameters or {}
    proto = params.get("protocol", "local").lower()
    try:
        return {"local": LocalDriver, "sftp": SFTPDriver}[proto](params)
    except KeyError:  # unsupported protocol
        raise ValueError(f"Unsupported protocol: {proto}")


def _hash(volumeid: str, rel: str) -> str:
    return f"{volumeid}_{_b64(rel or '/')}"


# ────────────────────────── main route ───────────────────────────
@elfinder_bp.route("", methods=["GET", "POST"])
def connector():
    cmd: str = request.values.get("cmd", "")
    dev_id: str = request.values.get("dev", "")
    target: str = request.values.get("target", "")

    current_app.logger.debug("elFinder cmd=%s dev=%s target=%s", cmd, dev_id, target)

    try:
        # ───── init device / driver ───────────────────────────────
        dev = Device.query.get_or_404(dev_id)
        drv = _driver_for(dev)
        volumeid = f"dev{dev_id}"

        # ───── tiny utils inside the request scope ────────────────
        def resolve_hash(h: str) -> str:
            """
            Convert elFinder hash -> relative path ('' == root).
            The driver root itself is never exposed, caller always sees ''.
            """
            if not h:
                return ""
            part = h.split("_", 1)[1] if "_" in h else h
            decoded = base64.urlsafe_b64decode(_b64pad(part)).decode()
            return "" if decoded in ("/", "") else decoded.lstrip("/")

        def listdir_for(rel_dir: str) -> Dict:
            """Return cwd entry + children lists like elFinder's OPEN."""
            cwd_abs = rel_dir
            # cwd meta
            st = drv.stat(rel_dir)
            cwd_entry = {
                "hash": _hash(volumeid, rel_dir),
                "name": os.path.basename(rel_dir) or "/",
                "mime": "directory",
                "ts": int(st.st_mtime),
                "size": 0,
                "dirs": 1,
                "volumeid": volumeid,
                "root": 1 if not rel_dir else 0,
                "read": 1,
                "write": 1,
                "locked": 0,
            }
            if rel_dir:
                cwd_entry["phash"] = _hash(volumeid, os.path.dirname(rel_dir))

            files = [cwd_entry]
            # children
            for name, full, is_dir, size, mtime in drv.listdir(rel_dir):
                files.append(
                    {
                        "hash": _hash(volumeid, os.path.join(rel_dir, name)),
                        "phash": cwd_entry["hash"],
                        "name": name,
                        "mime": "directory" if is_dir else (mimetypes.guess_type(full)[0] or "application/octet-stream"),
                        "ts": mtime,
                        "size": size,
                        "dirs": 1 if is_dir else 0,
                        "volumeid": volumeid,
                        "read": 1,
                        "write": 1,
                        "locked": 0,
                    }
                )
            return {
                "api": 2.1,
                "cwd": cwd_entry,
                "files": files,
                "options": {
                    "path": rel_dir,
                    "url": "",
                    "tmbUrl": "",
                    "disabled": [],
                    "uploadMaxSize": "64M",
                },
                "netDrivers": [],
                "tree": [f for f in files if f.get("dirs")],
            }

        # ───── command switch ─────────────────────────────────────
        if cmd == "open":
            rel = resolve_hash(target)
            resp = listdir_for(rel)
            return jsonify(resp)

        if cmd == "tree":
            rel = resolve_hash(target)
            nodes = []
            for name, full, is_dir, _, mtime in drv.listdir(rel):
                if not is_dir:
                    continue
                child_rel = os.path.join(rel, name)
                # has subdirs?
                has_sub = any(ent[2] for ent in drv.listdir(child_rel))
                nodes.append(
                    {
                        "hash": _hash(volumeid, child_rel),
                        "phash": _hash(volumeid, rel),
                        "name": name,
                        "mime": "directory",
                        "ts": mtime,
                        "dirs": 1 if has_sub else 0,
                        "volumeid": volumeid,
                        "read": 1,
                        "write": 1,
                        "locked": 0,
                    }
                )
            return jsonify(tree=nodes)

        if cmd == "parents":
            rel = resolve_hash(target)
            crumbs = []
            p = rel
            while p:
                p = os.path.dirname(p)
                st = drv.stat(p or "")
                crumbs.append(
                    {
                        "hash": _hash(volumeid, p),
                        "name": os.path.basename(p) or "/",
                        "mime": "directory",
                        "ts": int(st.st_mtime),
                        "size": 0,
                        "dirs": 1,
                        "volumeid": volumeid,
                        "read": 1,
                        "write": 1,
                        "locked": 0,
                    }
                )
            if not crumbs:  # root
                st = drv.stat("")
                crumbs.append(
                    {
                        "hash": _hash(volumeid, ""),
                        "name": "/",
                        "mime": "directory",
                        "ts": int(st.st_mtime),
                        "size": 0,
                        "dirs": 1,
                        "volumeid": volumeid,
                        "read": 1,
                        "write": 1,
                        "locked": 0,
                    }
                )
            return jsonify(tree=crumbs)

        if cmd == "ls":
            rel = resolve_hash(target)
            only_dirs = bool(request.values.get("mimes"))
            names = [
                name
                for name, _, is_dir, *_ in drv.listdir(rel)
                if not (only_dirs and not is_dir)
            ]
            return jsonify(list=names)

        if cmd == "mkdir":
            rel = resolve_hash(target)
            names = request.values.getlist("name[]") or request.values.getlist("name")
            added = []
            for nm in names:
                safe = os.path.basename(nm)
                drv.mkdir(os.path.join(rel, safe))
                st = drv.stat(os.path.join(rel, safe))
                added.append(
                    {
                        "hash": _hash(volumeid, os.path.join(rel, safe)),
                        "phash": _hash(volumeid, rel),
                        "name": safe,
                        "mime": "directory",
                        "ts": int(st.st_mtime),
                        "size": 0,
                        "dirs": 1,
                        "volumeid": volumeid,
                        "read": 1,
                        "write": 1,
                        "locked": 0,
                    }
                )
            return jsonify(added=added)

        if cmd == "upload":
            rel = resolve_hash(target)
            files = request.files.getlist("upload[]") or request.files.getlist("files[]")
            added = []
            for f in files:
                fn = os.path.basename(f.filename)
                drv.upload(f, os.path.join(rel, fn))
                st = drv.stat(os.path.join(rel, fn))
                added.append(
                    {
                        "hash": _hash(volumeid, os.path.join(rel, fn)),
                        "phash": _hash(volumeid, rel),
                        "name": fn,
                        "mime": mimetypes.guess_type(fn)[0] or "application/octet-stream",
                        "ts": int(st.st_mtime),
                        "size": st.st_size,
                        "dirs": 0,
                        "volumeid": volumeid,
                        "read": 1,
                        "write": 1,
                        "locked": 0,
                    }
                )
            return jsonify(added=added)

        if cmd == "rm":
            targets = request.values.getlist("targets[]") or request.values.getlist("targets")
            removed = []
            for h in targets:
                rel = resolve_hash(h)
                drv.remove(rel)
                removed.append(h)
            return jsonify(removed=removed, sync=[])

        if cmd == "paste":
            targets = request.values.getlist("targets[]")
            dst_hash = request.values.get("dst", "")
            cut_flag = request.values.get("cut") == "1"
            rel_dst = resolve_hash(dst_hash)
            added = []
            removed = []
            for h in targets:
                rel_src = resolve_hash(h)
                name = os.path.basename(rel_src)
                rel_new = os.path.join(rel_dst, name)
                drv.rename(rel_src, rel_new, copy=not cut_flag)
                if cut_flag:
                    removed.append(h)
                st = drv.stat(rel_new)
                added.append(
                    {
                        "hash": _hash(volumeid, rel_new),
                        "phash": _hash(volumeid, rel_dst),
                        "name": name,
                        "mime": "directory" if pystat.S_ISDIR(st.st_mode)
                        else (mimetypes.guess_type(name)[0] or "application/octet-stream"),
                        "ts": int(st.st_mtime),
                        "size": st.st_size if not pystat.S_ISDIR(st.st_mode) else 0,
                        "dirs": 1 if pystat.S_ISDIR(st.st_mode) else 0,
                        "volumeid": volumeid,
                        "read": 1,
                        "write": 1,
                        "locked": 0,
                    }
                )
            resp = {"added": added}
            if cut_flag:
                resp["removed"] = removed
            return jsonify(resp)

        if cmd in ("file", "download"):
            rel = resolve_hash(target)
            mime = mimetypes.guess_type(rel)[0] or "application/octet-stream"
            buf = io.BytesIO()
            drv.readfile(rel, buf)
            buf.seek(0)
            as_attach = cmd == "download"
            return send_file(
                buf,
                mimetype=mime if not as_attach else "application/octet-stream",
                as_attachment=as_attach,
                download_name=os.path.basename(rel),
            )

        # ───── unsupported / default ───────────────────────────────
        return jsonify(error=f"Unsupported command: {cmd}"), 400

    except Exception as exc:
        tb = traceback.format_exc()
        current_app.logger.error("elFinder error: %s\n%s", exc, tb)
        return jsonify(error=str(exc)), 500

    finally:
        try:
            drv.close()
        except Exception:  # noqa: BLE001
            pass

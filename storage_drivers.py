"""
Protocol drivers for the elFinder connector, with debug prints.

Every driver implements a common set of file-ops used by elFinder:
    listdir, stat, mkdir, upload, remove, rename, readfile
All paths passed to a driver are absolute *inside the driver’s own root*
so the caller never worries about escaping the storage sandbox.
"""

from __future__ import annotations

import os
import io
import shutil
import stat as pystat
import mimetypes
from pathlib import Path
from typing import Iterator, Tuple

import paramiko
from flask import current_app


# ─────────────────────────── Base API ────────────────────────────
DirEntry = Tuple[str, str, bool, int, int]
#            name, full_path, is_dir, size, mtime


class BaseDriver:
    """Abstract storage driver."""

    root: str  # absolute path of the driver’s root

    def close(self) -> None:
        """Release any underlying resources (SSH connections…)."""
        pass

    def listdir(self, path: str) -> Iterator[DirEntry]:
        raise NotImplementedError

    def stat(self, path: str):
        raise NotImplementedError  # returns object with st_size / st_mtime / S_ISDIR

    def mkdir(self, path: str) -> None:
        raise NotImplementedError

    def upload(self, fileobj, dest_path: str) -> None:
        raise NotImplementedError

    def remove(self, path: str) -> None:
        raise NotImplementedError

    def rename(self, src: str, dst: str, copy: bool = False) -> None:
        raise NotImplementedError

    def readfile(self, path: str, out_buf: io.BytesIO) -> None:
        raise NotImplementedError


# ─────────────────────────── Local FS ────────────────────────────
class LocalDriver(BaseDriver):
    def __init__(self, params: dict):
        raw = (params.get("base_path") or "").strip()
        current_app.logger.debug("LocalDriver init params: %s", params)

        if not raw:
            raise ValueError("LocalDriver: missing base_path")

        if os.path.isabs(raw):
            resolved = raw
        else:
            root_cfg = current_app.config.get("STORAGE_ROOT", "/app/storage")
            resolved = os.path.join(root_cfg, raw)

        self.root = Path(resolved).expanduser().resolve()
        # ensure it exists
        self.root.mkdir(parents=True, exist_ok=True)
        current_app.logger.debug("LocalDriver root resolved to: %s", self.root)

    def _abs(self, rel: str) -> Path:
        p = (self.root / rel.lstrip("/")).resolve()
        if self.root not in p.parents and p != self.root:
            current_app.logger.warning("LocalDriver access denied to: %s", p)
            raise PermissionError("Access denied")
        return p

    def listdir(self, path: str):
        current_app.logger.debug("LocalDriver.listdir: %s", path)
        abs_dir = self._abs(path)
        for child in abs_dir.iterdir():
            if child.name.startswith("."):
                continue
            st = child.stat()
            yield (child.name, str(child), child.is_dir(),
                   st.st_size, int(st.st_mtime))

    def stat(self, path: str):
        current_app.logger.debug("LocalDriver.stat: %s", path)
        return self._abs(path).stat()

    def mkdir(self, path: str):
        current_app.logger.debug("LocalDriver.mkdir: %s", path)
        self._abs(path).mkdir(parents=True, exist_ok=True)

    def upload(self, fileobj, dest_path: str):
        current_app.logger.debug("LocalDriver.upload: %s", dest_path)
        dest = self._abs(dest_path)
        fileobj.save(dest)

    def remove(self, path: str):
        current_app.logger.debug("LocalDriver.remove: %s", path)
        p = self._abs(path)
        if p.is_dir():
            p.rmdir()
        else:
            p.unlink()

    def rename(self, src: str, dst: str, copy: bool = False):
        current_app.logger.debug("LocalDriver.rename: %s -> %s (copy=%s)", src, dst, copy)
        a_src = self._abs(src)
        a_dst = self._abs(dst)
        if copy:
            if a_src.is_dir():
                shutil.copytree(a_src, a_dst)
            else:
                shutil.copy2(a_src, a_dst)
        else:
            a_src.rename(a_dst)

    def readfile(self, path: str, out_buf: io.BytesIO):
        current_app.logger.debug("LocalDriver.readfile: %s", path)
        with self._abs(path).open("rb") as f:
            shutil.copyfileobj(f, out_buf)


# ─────────────────────────── SFTP driver ─────────────────────────

class SFTPDriver(BaseDriver):
    def __init__(self, params: dict):
        current_app.logger.debug("SFTPDriver init params: %s", params)
        self.host     = params.get("host")
        self.port     = int(params.get("port", 22))
        self.username = params.get("username")
        self.password = params.get("password")
        raw_root      = (params.get("root_path") or "").strip().rstrip("/")

        # connect
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        current_app.logger.debug("SFTPDriver connecting to %s@%s:%d …",
                                 self.username, self.host, self.port)
        self.ssh.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            allow_agent=False,
            look_for_keys=False,
            timeout=10,
        )
        self.sftp = self.ssh.open_sftp()

        # figure out home dir (may fail or return None)
        try:
            home = self.sftp.getcwd()
        except Exception as e:
            current_app.logger.warning("SFTPDriver.getcwd failed: %s", e, exc_info=True)
            home = "/"
        if not home:
            home = "/"
        current_app.logger.debug("SFTP home directory: %s", home)

        # try configured root, else fallback to home
        if raw_root:
            try:
                self.sftp.chdir(raw_root)
                self.root = raw_root
                current_app.logger.debug("SFTPDriver.chdir success: %s", raw_root)
            except Exception as e:
                current_app.logger.warning("SFTPDriver.chdir(%s) failed: %s – falling back to home", raw_root, e)
                try:
                    self.sftp.chdir(home)
                    self.root = home
                except Exception as e2:
                    current_app.logger.error("Cannot chdir to home %s: %s", home, e2, exc_info=True)
                    raise FileNotFoundError(f"Cannot use or fallback from root '{raw_root}' or home '{home}'")
        else:
            self.root = home
            current_app.logger.debug("No root_path given; using home as root: %s", home)

        # inspect final root
        try:
            entries = self.sftp.listdir(self.root)
            current_app.logger.debug("SFTPDriver final root=%s, contents=%s", self.root, entries)
        except Exception as e:
            current_app.logger.error("Failed to list SFTP root %s: %s", self.root, e, exc_info=True)

    def _abs(self, rel: str) -> str:
        # Treat None as empty → always return a string
        rel = (rel or "").lstrip("/")
        return f"{self.root}/{rel}" if rel else self.root

    def listdir(self, path: str):
        current_app.logger.debug("SFTPDriver.listdir: %r (root=%s)", path, self.root)
        abs_dir = self._abs(path)
        for attr in self.sftp.listdir_attr(abs_dir):
            if attr.filename.startswith("."):
                continue
            full = f"{abs_dir}/{attr.filename}"
            yield (
                attr.filename,
                full,
                pystat.S_ISDIR(attr.st_mode),
                attr.st_size,
                int(attr.st_mtime),
            )

    def stat(self, path: str):
        current_app.logger.debug("SFTPDriver.stat: %r", path)
        return self.sftp.stat(self._abs(path))

    def mkdir(self, path: str):
        current_app.logger.debug("SFTPDriver.mkdir: %r", path)
        self.sftp.mkdir(self._abs(path))

    def upload(self, fileobj, dest_path: str):
        current_app.logger.debug("SFTPDriver.upload: %r", dest_path)
        buf = io.BytesIO(fileobj.read())
        buf.seek(0)
        self.sftp.putfo(buf, self._abs(dest_path))

    def remove(self, path: str):
        current_app.logger.debug("SFTPDriver.remove: %r", path)
        tgt = self._abs(path)
        st  = self.sftp.stat(tgt)
        if pystat.S_ISDIR(st.st_mode):
            self.sftp.rmdir(tgt)
        else:
            self.sftp.remove(tgt)

    def rename(self, src: str, dst: str, copy: bool = False):
        current_app.logger.debug("SFTPDriver.rename: %r -> %r (copy=%s)", src, dst, copy)
        if copy:
            buf = io.BytesIO()
            self.sftp.getfo(self._abs(src), buf)
            buf.seek(0)
            self.sftp.putfo(buf, self._abs(dst))
        else:
            self.sftp.rename(self._abs(src), self._abs(dst))

    def readfile(self, path: str, out_buf: io.BytesIO):
        current_app.logger.debug("SFTPDriver.readfile: %r", path)
        self.sftp.getfo(self._abs(path), out_buf)

    def close(self):
        current_app.logger.debug("SFTPDriver.close")
        try:
            self.sftp.close()
        finally:
            self.ssh.close()

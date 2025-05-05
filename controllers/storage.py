"""
controllers/storage.py
Storage device filesystem logic for Factory Lens.
Handles listing devices, browsing folders, uploading, downloading, and deleting files.
"""
import os
from flask import (
    send_from_directory,
    flash,
    redirect,
    url_for,
    abort,
    request,
    render_template,
    current_app,
)
from models.device import Device
from models.device_model import DeviceModel


# ────────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────────
def get_storage_devices():
    """Return all devices whose model category = storage."""
    return (
        Device.query
        .join(Device.model)
        .join(DeviceModel.category)
        .filter(DeviceModel.category.has(name="storage"))
        .order_by(Device.id)
        .all()
    )


# ────────────────────────────────────────────────────────────────────────────────
# Pages
# ────────────────────────────────────────────────────────────────────────────────
def list_devices():
    """Render a table of storage devices (for a standalone page, if you need it)."""
    devices = get_storage_devices()
    return render_template("storage/devices.html", devices=devices)


def _resolve_base_path(raw_path: str) -> str:
    """
    Convert *raw_path* (from device.parameters['base_path']) into an absolute path.

    • If it is already absolute → return as‑is.
    • Otherwise → join it under app.config['STORAGE_ROOT']  (defaults to /app/storage)
    """
    if os.path.isabs(raw_path):
        return raw_path
    root = current_app.config.get("STORAGE_ROOT", "/app/storage")
    return os.path.join(root, raw_path)


def browse_files(dev_id):
    """
    Directory browser & uploader.

    ── GET  ──
      • /storage/<id>/files?path=sub/dir
        → Render template with file/folder listing
      • Clicking a file triggers download (same route, but path points to file)
    ── POST ──
      • Uploads a file to current path
    """
    dev = Device.query.get_or_404(dev_id)
    base_raw = (dev.parameters or {}).get("base_path", "").strip()
    if not base_raw:
        flash("Storage path not configured.", "danger")
        return redirect(url_for("storage.list_devices"))

    base = _resolve_base_path(base_raw)
    if not os.path.isdir(base):
        flash(f"Folder not found: {base}", "danger")
        return redirect(url_for("storage.list_devices"))

    # ───── Upload ───────────────────────────────────────────────────────────────
    if request.method == "POST":
        file = request.files.get("file")
        if file:
            dest = os.path.join(base, file.filename)
            file.save(dest)
            flash(f"Uploaded {file.filename}", "success")
        return redirect(
            url_for("storage.browse_files", dev_id=dev.id, path=request.form.get("path", ""))
        )

    # ───── Browse / Download ────────────────────────────────────────────────────
    rel_path = request.args.get("path", "")
    abs_path = os.path.normpath(os.path.join(base, rel_path))
    # basic traversal‑guard
    if not abs_path.startswith(os.path.normpath(base)):
        abort(403)

    if os.path.isdir(abs_path):
        # list directory
        entries = [
            {"name": n, "is_dir": os.path.isdir(os.path.join(abs_path, n))}
            for n in sorted(os.listdir(abs_path))
        ]
        return render_template(
            "storage/browse.html",
            dev=dev,
            entries=entries,
            rel_path=rel_path,
        )

    # else → download file
    return send_from_directory(
        os.path.dirname(abs_path),
        os.path.basename(abs_path),
        as_attachment=True,
    )


def delete_file(dev_id):
    """Delete a file or an empty directory."""
    dev = Device.query.get_or_404(dev_id)
    base_raw = (dev.parameters or {}).get("base_path", "").strip()
    base = _resolve_base_path(base_raw)

    target = request.form.get("path", "")
    abs_path = os.path.normpath(os.path.join(base, target))
    if not abs_path.startswith(os.path.normpath(base)):
        abort(403)

    if os.path.isdir(abs_path):
        try:
            os.rmdir(abs_path)
            flash(f"Removed directory {target}", "success")
        except OSError as exc:
            flash(str(exc), "danger")
    else:
        os.remove(abs_path)
        flash(f"Deleted file {target}", "success")

    return redirect(
        url_for("storage.browse_files", dev_id=dev.id, path=os.path.dirname(target))
    )

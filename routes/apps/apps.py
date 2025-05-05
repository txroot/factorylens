# routes/apps/apps.py

import subprocess, os, time, shlex
import shutil
import io
import cv2
import json

from flask import Blueprint, render_template, jsonify, current_app, Response
from flask import url_for, request, abort
from models.camera import Camera
from models.camera_stream import CameraStream
from models.device import Device

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

apps_bp = Blueprint('apps', __name__, url_prefix='/apps')

ffmpeg_processes = {}

@apps_bp.route('/video-player')
def video_player():
    cameras = Camera.query.filter(
        Camera.device.has(enabled=True)
    ).all()
    return render_template('apps/video-player.hbs', cameras=cameras)

@apps_bp.route('/apps/video-player/check/<int:cam_id>')
def check_playlist(cam_id):
    cam = Camera.query.get_or_404(cam_id)
    sid = request.args.get('stream_id', type=int)
    if sid:
        stream = CameraStream.query.get_or_404(sid)
    else:
        stream = (
            cam.default_stream
            or next((s for s in cam.streams if s.stream_type=='sub'), None)
            or next((s for s in cam.streams if s.stream_type=='main'), None)
        )
    if not stream:
        abort(400, "No stream configured")
    path = os.path.join(
        current_app.static_folder,
        'streams', cam.serial_number, str(stream.id), 'index.m3u8'
    )
    return jsonify({
      "exists_on_disk": os.path.exists(path),
      "full_disk_path": path
    })

# --- helper ------------------------------------------------------------
def probe_rtsp_codec(rtsp_url, timeout=2):
    """
    Return (codec_name, profile) for the first video stream in an RTSP URL.
    Uses an SDP‑only probe (analyzeduration 0, probesize 32) so it finishes fast.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-rtsp_transport", "tcp",
        "-timeout", "1500000",          # μs → 1.5 s handshake timeout
        "-analyzeduration", "0",
        "-probesize", "32",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,profile",
        "-of", "json",
        rtsp_url
    ]
    out = subprocess.check_output(cmd, timeout=timeout)
    streams = json.loads(out)["streams"]
    if not streams:
        return None, None
    s = streams[0]
    return s.get("codec_name"), s.get("profile")

# -----------------------------------------------------------------------
@apps_bp.route("/video-player/start/<int:cam_id>", methods=["POST"])
def start_stream(cam_id):
    cam = Camera.query.get_or_404(cam_id)
    sid = request.args.get('stream_id', type=int)
    if sid:
        stream = CameraStream.query.get_or_404(sid)
    else:
        stream = (
            cam.default_stream
            or next((s for s in cam.streams if s.stream_type=='sub'), None)
            or next((s for s in cam.streams if s.stream_type=='main'), None)
        )
    if not stream:
        abort(400, "No streams configured")

    # build input_url (full_url override → authified prefix/suffix)
    if stream.full_url:
        input_url = stream.full_url
    else:
        input_url = stream.get_full_url(include_auth=True) or cam.stream_url
    if not input_url:
        abort(400, "No valid RTSP URL")

    # output into static/streams/<serial>/<stream.id>/
    out_dir = os.path.join(
        current_app.static_folder,
        "streams", cam.serial_number, str(stream.id)
    )
    os.makedirs(out_dir, exist_ok=True)
    playlist = os.path.join(out_dir, "index.m3u8")

    # probe + choose copy vs transcode (your existing logic)
    try:
        codec, profile = probe_rtsp_codec(input_url)
    except subprocess.TimeoutExpired:
        codec, profile = None, None
    SAFE_H264 = {"Constrained Baseline", "Baseline", "Main", "High"}
    if codec=="h264" and (profile in SAFE_H264 or profile is None):
        video_args = ["-c:v","copy"]
    else:
        video_args = [
          "-vf","scale=w='min(1280,iw)':h=-2,format=yuv420p",
          "-c:v","libx264","-preset","ultrafast",
          "-profile:v","high","-level","4.0",
          "-g","50","-keyint_min","50","-sc_threshold","0",
          "-b:v","2500k","-maxrate","3000k","-bufsize","6000k"
        ]

    cmd = (["ffmpeg","-nostdin","-loglevel","error",
            "-rtsp_transport","tcp","-i",input_url]
           + video_args +
           ["-an","-f","hls",
            "-hls_time","2","-hls_list_size","3",
            "-hls_flags","delete_segments+independent_segments",
            playlist])
    err_log = os.path.join(out_dir, "ffmpeg-error.log")
    with open(err_log, "ab") as errf:
        p = subprocess.Popen(cmd, stderr=errf)
    ffmpeg_processes[cam_id] = p

    # wait up to 5 s
    for _ in range(10):
        if os.path.exists(playlist):
            break
        time.sleep(0.5)

    hls_url = url_for(
        "static",
        filename=f"streams/{cam.serial_number}/{stream.id}/index.m3u8"
    )
    return jsonify({"hls_url": hls_url})

@apps_bp.route('/video-player/stop/<int:cam_id>', methods=['POST'])
def stop_stream(cam_id):
    # 1) Terminate the ffmpeg process if running
    p = ffmpeg_processes.pop(cam_id, None)
    if p:
        p.terminate()
        current_app.logger.info("Stopped ffmpeg for camera %d", cam_id)

    # 2) Delete the HLS output directory
    cam = Camera.query.get_or_404(cam_id)
    out_dir = os.path.join(current_app.static_folder, 'streams', cam.serial_number)
    if os.path.isdir(out_dir):
        try:
            shutil.rmtree(out_dir)
            current_app.logger.info("Removed stream directory %s", out_dir)
        except Exception as e:
            current_app.logger.error("Error removing %s: %s", out_dir, e)

    return ('', 204)

@apps_bp.route('/video-player/snapshot/<int:cam_id>')
def video_snapshot(cam_id):
    cam = Camera.query.get_or_404(cam_id)

    # 1) stream‐specific snapshot?
    stream_id = request.args.get("stream_id", type=int)
    if stream_id:
        stream = CameraStream.query.get_or_404(stream_id)
        input_url = stream.get_full_url(include_auth=True) or ""
    else:
        # direct URL override?
        if cam.snapshot_url:
            try:
                import requests
                resp = requests.get(cam.snapshot_url, timeout=3)
                resp.raise_for_status()
                return Response(resp.content,
                                mimetype=resp.headers.get("Content-Type","image/jpeg"))
            except Exception:
                current_app.logger.warning("Failed proxying snapshot_url for cam %s", cam.id)
        # fall back to sub→main
        stream = (
            cam.default_stream
            or next((s for s in cam.streams if s.stream_type=="sub"), None)
            or next((s for s in cam.streams if s.stream_type=="main"), None)
        )
        if stream:
            input_url = stream.get_full_url(include_auth=True) or ""
        else:
            abort(400, "No stream available for snapshot")

    if not input_url:
        abort(400, "No RTSP URL for snapshot")

    # 2) ffmpeg-grab
    cmd = [
      'ffmpeg','-rtsp_transport','tcp',
      '-probesize','32','-analyzeduration','0',
      '-i', input_url,
      '-frames:v','1','-q:v','2',
      '-f','image2','pipe:1'
    ]
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        img_data, _ = p.communicate(timeout=5)
    except Exception as e:
        current_app.logger.error("Snapshot failed for camera %d: %s", cam_id, e)
        return current_app.send_static_file('img/video-player/placeholder.jpg')

    return Response(img_data, mimetype='image/jpeg')

@apps_bp.route('/video-player/snapshot/<int:cam_id>/pdf')
def video_snapshot_pdf(cam_id):
    cam = Camera.query.get_or_404(cam_id)

    # reconstruct your RTSP URL exactly as you do in snapshot…
    if cam.username and cam.password:
        suffix = getattr(cam, 'stream_url_suffix', '') or ''
        input_url = f"rtsp://{cam.username}:{cam.password}@{cam.address}:{cam.port}{suffix}"
    else:
        input_url = cam.stream_url

    # grab one frame with ffmpeg
    cmd = [
        'ffmpeg',
        '-rtsp_transport', 'tcp',
        '-probesize', '32', '-analyzeduration', '0',
        '-i', input_url,
        '-frames:v', '1',
        '-q:v', '2',
        '-f', 'image2', 'pipe:1'
    ]
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        img_data, _ = p.communicate(timeout=5)
    except Exception as e:
        current_app.logger.error("Snapshot→PDF failed for camera %d: %s", cam_id, e)
        # fall back to placeholder JPEG
        return current_app.send_static_file('img/video-player/placeholder.jpg')

    # build a PDF with that JPEG
    img_buf = io.BytesIO(img_data)
    img = ImageReader(img_buf)
    w, h = img.getSize()  # px
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=(w, h))
    c.drawImage(img, 0, 0, width=w, height=h)
    c.showPage()
    c.save()
    pdf_buf.seek(0)

    # generate timestamped filename
    ts = time.strftime("%Y-%m-%d_%H-%M")
    safe_name = cam.name.replace(" ", "_")
    filename = f"snapshot_{safe_name}_{ts}.pdf"

    return Response(
      pdf_buf.read(),
      mimetype='application/pdf',
      headers={
        'Content-Disposition': f'attachment; filename="{filename}"'
      }
    )

@apps_bp.route('/video-player/snapshot/pdf', methods=['POST'])
def convert_snapshot_to_pdf():
    """
    Accepts an uploaded JPEG (form‐file field "image") and returns a one‐page PDF.
    """
    if 'image' not in request.files:
        abort(400, "Missing 'image' file")
    img_file = request.files['image']
    img_bytes = img_file.read()

    # wrap in ImageReader
    img_buf = io.BytesIO(img_bytes)
    reader = ImageReader(img_buf)
    w, h = reader.getSize()

    # create PDF
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=(w, h))
    c.drawImage(reader, 0, 0, width=w, height=h)
    c.showPage()
    c.save()
    pdf_buf.seek(0)

    # timestamped filename
    ts = time.strftime("%Y-%m-%d_%H-%M")
    safe_name = img_file.filename.rsplit('.',1)[0]
    filename = f"{safe_name}_{ts}.pdf"

    return Response(
        pdf_buf.read(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
from flask import Blueprint, render_template, jsonify, current_app, Response
from flask import url_for, request, abort
from models.camera import Camera
import subprocess, os, time, shlex
import shutil
import io
import cv2
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

apps_bp = Blueprint('apps', __name__, url_prefix='/apps')

ffmpeg_processes = {}

@apps_bp.route('/video-player')
def video_player():
    cameras = Camera.query.all()
    return render_template('apps/video-player.hbs', cameras=cameras)

@apps_bp.route('/apps/video-player/check/<int:cam_id>')
def check_playlist(cam_id):
    cam = Camera.query.get_or_404(cam_id)
    path = os.path.join(app.static_folder, 'streams', cam.serial_number, 'index.m3u8')
    return {
      "exists_on_disk": os.path.exists(path),
      "full_disk_path": path
    }

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

    # where HLS files will go
    out_dir = os.path.join("public", "streams", cam.serial_number)
    os.makedirs(out_dir, exist_ok=True)
    playlist = os.path.join(out_dir, "index.m3u8")

    # reconstruct full RTSP URL
    if cam.username and cam.password:
        suffix = getattr(cam, "stream_url_suffix", "") or ""
        input_url = (
            f"rtsp://{cam.username}:{cam.password}@{cam.address}:{cam.port}{suffix}"
        )
    else:
        input_url = cam.stream_url

    # ---------- decide copy vs transcode ----------
    try:
        codec, profile = probe_rtsp_codec(input_url)
        current_app.logger.info(
            "RTSP probe for cam %s: codec=%s profile=%s", cam.id, codec, profile
        )
    except subprocess.TimeoutExpired:
        codec, profile = None, None
        current_app.logger.warning("RTSP probe timed out for cam %s", cam.id)

    # “safe” H.264 profiles that browsers decode natively
    SAFE_H264 = {"Constrained Baseline", "Baseline", "Main", "High"}

    if codec == "h264" and (profile in SAFE_H264 or profile is None):
        video_args = ["-c:v", "copy"]  # zero‑CPU copy
    else:
        # software x264 transcode (1 stream ≈ 80 % of one Pi‑5 core)
        video_args = [
            "-vf",
            "scale=w='min(1280,iw)':h=-2,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-profile:v",
            "high",
            "-level",
            "4.0",
            "-g",
            "50",
            "-keyint_min",
            "50",
            "-sc_threshold",
            "0",
            "-b:v",
            "2500k",
            "-maxrate",
            "3000k",
            "-bufsize",
            "6000k",
        ]

    # ---------- build the ffmpeg command ----------
    cmd = (
        [
            "ffmpeg",
            "-nostdin",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            input_url,
        ]
        + video_args
        + [
            "-an",
            "-f",
            "hls",
            "-hls_time",
            "2",
            "-hls_list_size",
            "3",
            "-hls_flags",
            "delete_segments+independent_segments",
            playlist,
        ]
    )

    # log full command
    current_app.logger.info("FFmpeg cmd: %s", " ".join(map(shlex.quote, cmd)))

    # launch ffmpeg
    err_log = os.path.join(out_dir, "ffmpeg-error.log")
    with open(err_log, "ab") as errf:
        p = subprocess.Popen(cmd, stderr=errf)
    ffmpeg_processes[cam_id] = p

    # wait up to 5 s for the playlist
    for _ in range(10):
        if os.path.exists(playlist):
            break
        time.sleep(0.5)
    else:
        current_app.logger.warning(
            "Playlist still missing after 5 s; see %s", err_log
        )

    return jsonify(
        {
            "hls_url": url_for(
                "static", filename=f"streams/{cam.serial_number}/index.m3u8"
            )
        }
    )
  
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

    # Reconstruct RTSP URL with credentials
    if cam.username and cam.password:
        suffix = getattr(cam, 'stream_url_suffix', '') or ''
        input_url = f"rtsp://{cam.username}:{cam.password}@{cam.address}:{cam.port}{suffix}"
    else:
        input_url = cam.stream_url

    # Build ffmpeg command to grab one frame
    cmd = [
        'ffmpeg',
        '-rtsp_transport', 'tcp',
        # ask ffmpeg to do almost no probing
        '-probesize', '32',
        '-analyzeduration', '0',
        '-i', input_url,
        # grab exactly one frame
        '-frames:v', '1',
        # set JPEG quality (optional)
        '-q:v', '2',
        '-f', 'image2',
        'pipe:1'
    ]
    # Run and capture stdout
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        img_data, _ = p.communicate(timeout=5)
    except Exception as e:
        current_app.logger.error("Snapshot failed for camera %d: %s", cam_id, e)
        # fall back to a 1×1 transparent GIF or your placeholder
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
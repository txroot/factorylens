from flask import Blueprint, render_template, jsonify, current_app, Response
from flask import url_for
from models.camera import Camera
import subprocess, os, time, shlex
import shutil

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

@apps_bp.route('/video-player/start/<int:cam_id>', methods=['POST'])
def start_stream(cam_id):
    cam = Camera.query.get_or_404(cam_id)

    # where HLS files will go:
    out_dir = os.path.join('public', 'streams', cam.serial_number)
    os.makedirs(out_dir, exist_ok=True)
    playlist = os.path.join(out_dir, 'index.m3u8')

    # 1) reconstruct the FULL RTSP URL (with credentials) if present
    if cam.username and cam.password:
        # if you have a suffix column, use that; otherwise grab path from cam.stream_url
        suffix = getattr(cam, 'stream_url_suffix', '') or ''
        input_url = f"rtsp://{cam.username}:{cam.password}@{cam.address}:{cam.port}{suffix}"
    else:
        input_url = cam.stream_url

    # 2) build the ffmpeg command
    cmd = [
        'ffmpeg', '-nostdin',
        '-rtsp_transport', 'tcp',
        '-i', input_url,
        '-c:v', 'copy', '-c:a', 'copy',
        '-f', 'hls',
        '-hls_time', '2',
        '-hls_list_size', '3',
        '-hls_flags', 'delete_segments',
        playlist
    ]

    # 3) print/log the exact command
    system_command = " ".join(shlex.quote(part) for part in cmd)
    print("System Command:", system_command)
    current_app.logger.info("System Command: %s", system_command)

    # 4) optionally capture stderr to file so you can inspect connection/auth errors
    err_log = os.path.join(out_dir, 'ffmpeg-error.log')
    # launch and store the process
    with open(err_log, 'ab') as errf:
        p = subprocess.Popen(cmd, stderr=errf)
    ffmpeg_processes[cam_id] = p

    # 5) wait up to 5s for the playlist to appear
    for _ in range(10):
        if os.path.exists(playlist):
            break
        time.sleep(0.5)
    else:
        current_app.logger.warning("Playlist still missing after 5s; see %s", err_log)

    return jsonify({
    "hls_url": url_for(
        'static',
        filename=f"streams/{cam.serial_number}/index.m3u8"
    )
})
    
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


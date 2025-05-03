from flask import Blueprint, render_template, jsonify, current_app
from models.camera import Camera
import subprocess, os, time, shlex

apps_bp = Blueprint('apps', __name__, url_prefix='/apps')

@apps_bp.route('/video-player')
def video_player():
    cameras = Camera.query.all()
    return render_template('apps/video-player.hbs', cameras=cameras)

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
    with open(err_log, 'ab') as errf:
        subprocess.Popen(cmd, stderr=errf)

    # 5) wait up to 5s for the playlist to appear
    for _ in range(10):
        if os.path.exists(playlist):
            break
        time.sleep(0.5)
    else:
        current_app.logger.warning("Playlist still missing after 5s; see %s", err_log)

    return jsonify({'hls_url': f"/static/streams/{cam.serial_number}/index.m3u8"})
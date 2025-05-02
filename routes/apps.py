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

    out_dir = os.path.join('public', 'streams', cam.serial_number)
    os.makedirs(out_dir, exist_ok=True)
    playlist = os.path.join(out_dir, 'index.m3u8')

    # --- launch (or relaunch) ffmpeg ----------------------------------------
    cmd = [
        'ffmpeg', '-nostdin', '-rtsp_transport', 'tcp', '-i', cam.stream_url,
        '-c:v', 'copy', '-c:a', 'copy',
        '-f', 'hls', '-hls_time', '2', '-hls_list_size', '3',
        '-hls_flags', 'delete_segments', playlist
    ]
    current_app.logger.info("Starting ffmpeg: %s", shlex.join(cmd))
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # --- wait (up to 5 s) until the first playlist exists -------------------
    for _ in range(10):
        if os.path.exists(playlist):
            break
        time.sleep(0.5)
    else:
        current_app.logger.warning("Playlist not ready for cam %s after 5 s", cam.serial_number)

    return jsonify({"hls_url": f"/static/streams/{cam.serial_number}/index.m3u8"})

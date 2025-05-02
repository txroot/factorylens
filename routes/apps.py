from flask import Blueprint, render_template, jsonify
from models.camera import Camera
import subprocess, os

apps_bp = Blueprint('apps', __name__, url_prefix='/apps')

@apps_bp.route('/video-player')
def video_player():
    cameras = Camera.query.all()
    return render_template('apps/video-player.hbs', cameras=cameras)

@apps_bp.route('/video-player/start/<int:cam_id>', methods=['POST'])
def start_stream(cam_id):
    cam = Camera.query.get_or_404(cam_id)
    # directory for HLS output
    out_dir = os.path.join('public', 'streams', cam.serial_number)
    os.makedirs(out_dir, exist_ok=True)
    playlist = os.path.join(out_dir, 'index.m3u8')

    # ffmpeg command
    cmd = [
        'ffmpeg', '-rtsp_transport', 'tcp', '-i', cam.stream_url,
        '-c:v', 'copy', '-c:a', 'copy',
        '-f', 'hls', '-hls_time', '2', '-hls_list_size', '3',
        '-hls_flags', 'delete_segments', playlist
    ]
    # Launch in background
    subprocess.Popen(cmd)

    # return the HLS URL for the client
    return jsonify({ 'hls_url': f"/static/streams/{cam.serial_number}/index.m3u8" })
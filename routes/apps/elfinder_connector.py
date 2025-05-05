# routes/elfinder_connector.py
from flask import Blueprint, request, jsonify
import os
from models.device import Device

elfinder_bp = Blueprint('elfinder_connector', __name__, url_prefix='/storage/connector')

@elfinder_bp.route('', methods=['GET','POST'])
def connector():
    cmd = request.values.get('cmd')
    dev_id = request.values.get('dev')          # we’ll pass device-ID as a param
    dev = Device.query.get_or_404(dev_id)
    base = dev.parameters.get('base_path') or ''
    # NOTE: for brevity, this is just a skeleton!
    if cmd == 'open':
        # list current directory (node == '' is root)
        target = request.values.get('target','')
        path = os.path.normpath(os.path.join(base, target))
        # build elFinder JSON response…
        files = []
        for name in os.listdir(path):
            full = os.path.join(path, name)
            files.append({
                'name': name,
                'hash': os.path.relpath(full, base),
                'mime': 'directory' if os.path.isdir(full) else 'text/plain',
                'ts': os.path.getmtime(full),
                'size': os.path.getsize(full) if os.path.isfile(full) else 0,
                'dirs': 1 if os.path.isdir(full) else 0
            })
        return jsonify({
            'cwd': {
              'hash': target,
              'name': os.path.basename(path) or '/',
              'mime': 'directory',
              'ts': os.path.getmtime(path),
              'size': 0,
              'dirs': 1
            },
            'files': [ {'hash': '', 'name':'','mime':'directory','ts':0,'size':0,'dirs':1} ] + files
        })
    # TODO: handle upload (cmd=upload), mkdir, rm, etc.
    return jsonify({'error':'Not implemented'}), 400

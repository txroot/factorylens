# routes/settings.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.camera import Camera
from models.device import Device
# (you’ll add imports for communication & storage controllers soon)

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/cameras', methods=['GET', 'POST'])
def cameras():
    # GET: show list / form; POST: save updates
    cameras = Camera.query.all()
    return render_template('settings/cameras.hbs', cameras=cameras)

@settings_bp.route('/devices', methods=['GET', 'POST'])
def devices():
    devices = Device.query.all()
    return render_template('settings/devices.hbs', devices=devices)

@settings_bp.route('/communication', methods=['GET', 'POST'])
def communication():
    # stub for MQTT communication settings
    return render_template('settings/communication.hbs')

@settings_bp.route('/file_storage', methods=['GET', 'POST'])
def file_storage():
    # stub for storage backends (FTP, SMB…)
    return render_template('settings/file_storage.hbs')

# routes/notifications.py

from flask import Blueprint, render_template

# Define the Blueprint
notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/')
def notifications():
    # Return the notifications page or a list of notifications
    return render_template('notifications.hbs')
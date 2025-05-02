# route/users.py

from flask import Blueprint, render_template, request
from controllers.users import register_user, login_user

users_bp = Blueprint('users', __name__, url_prefix='/users')

@users_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        register_user(request.form)
    return render_template('register.hbs')

@users_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_user(request.form)
    return render_template('login.hbs')

# Dummy data for the settings page
user_data = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "johndoe@example.com",
    "avatar_url": "/static/img/users/default-avatar.png"
}

# Settings route added here
@users_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    # You can later replace the dummy data with actual database data
    return render_template('settings.hbs', user=user_data)
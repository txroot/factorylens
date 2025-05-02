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

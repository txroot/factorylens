# routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models.user import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Query the user by username
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            # Optionally, restrict by role:
            if user.role in ['admin', 'sales']:
                login_user(user)
                return redirect(url_for('main.index'))
            else:
                flash("Access denied: your user role does not have permission.")
        else:
            flash("Invalid username or password.")
    
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/lock')
def lockscreen():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    return render_template('lockscreen.html')

@auth_bp.route('/unlock', methods=['POST'])
def unlock():
    code = request.form.get('lock_code')
    
    # If no user is detected, send them to login.
    if not current_user.is_authenticated:
        flash("Session expired, please login again.")
        return redirect(url_for('auth.login'))
    
    # Check if the code matches the user's password or PIN.
    if current_user.check_password(code) or (current_user.pin and current_user.pin == code):
        # Successful unlock – redirect to the main page.
        return redirect(url_for('main.index'))
    else:
        flash("Invalid password or PIN.")
        return render_template('lockscreen.html')

@auth_bp.route("/api/current_user", methods=["GET"])
@login_required
def current_user_info():
    """Return the currently logged-in user's details"""
    return jsonify({
        "username": current_user.username,
        "role": current_user.role  # Ensure 'role' is a valid field in your User model
    })
# controllers/users.py

from flask import flash, redirect, url_for
from flask_login import login_user as flask_login_user, logout_user as flask_logout_user, login_required
from extensions import db, login_manager
from models.user import User

# User loader callback
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def register_user(form):
    """
    Register a new user with username and password from form.
    """
    username = form.get('username')
    password = form.get('password')
    if User.query.filter_by(username=username).first():
        flash("Username already exists", "error")
        return False
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash("Registration successful. Please log in.", "success")
    return True


def login_user(form):
    """
    Authenticate and log in a user from form data.
    """
    username = form.get('username')
    password = form.get('password')
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        flask_login_user(user)
        return True
    flash("Invalid username or password", "error")
    return False

@login_required
def logout_user():
    """
    Log out the current user.
    """
    flask_logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))
# routes/home.py

from flask import Blueprint, render_template
from flask_login import login_required
home_bp = Blueprint('home', __name__)

@home_bp.route("/")
#@login_required
def index():
    # This calls the view/template for the index page.
    return render_template('home.hbs')
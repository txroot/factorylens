# routes/language.py

from flask import Blueprint, session, request, redirect, url_for

language_bp = Blueprint('language', __name__)

@language_bp.route('/change-language/<lang_code>')
def change_language(lang_code):
    # store the new language in the session
    session['lang'] = lang_code
    # send the user back to wherever they came from
    return redirect(request.referrer or url_for('dashboard.dashboard'))

from flask import Blueprint, render_template, session
from utils import login_required

main_bp = Blueprint('main', __name__)

@main_bp.route('/main')
@login_required
def index():
    """Main page"""
    return render_template('main.html', 
                          username=session.get('username'),
                          role=session.get('role'))

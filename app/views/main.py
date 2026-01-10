from flask import Blueprint, render_template
from flask_security import auth_required, current_user

bp = Blueprint("main", __name__)

@bp.route("/")
def index():
    return render_template("index.html")

@bp.route("/app")
@auth_required()
def app_home():
    return render_template("home.html", user=current_user)

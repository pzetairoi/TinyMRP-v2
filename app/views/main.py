from flask import Blueprint, render_template, redirect, url_for
from flask_security import auth_required, current_user

bp = Blueprint("main", __name__)

@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.app_home"))
    return render_template("index.html")

@bp.route("/app")
@auth_required()
def app_home():
    return render_template("home.html", user=current_user)

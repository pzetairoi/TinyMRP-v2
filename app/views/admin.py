# app/views/admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask import abort
from mongoengine.errors import DoesNotExist, ValidationError
from flask_security import roles_required
from flask_security.utils import hash_password
from ..models.auth import User, Role

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.route("/users")
@roles_required("admin")
def users_list():
    users = User.objects().order_by("-id").limit(200)
    return render_template("admin/users_list.html", users=users)

@bp.route("/users/new", methods=["GET", "POST"])
@roles_required("admin")
def users_create():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not email or not password:
            flash("Email and password are required.", "error")
            return redirect(url_for("admin.users_create"))
        if User.objects(email=email).first():
            flash("User already exists.", "error")
            return redirect(url_for("admin.users_create"))
        import secrets
        u = User(email=email, password=hash_password(password), fs_uniquifier=secrets.token_hex(16))
        # initial roles from form
        role_ids = request.form.getlist("roles")
        if role_ids:
            u.roles = list(Role.objects(id__in=role_ids))
        u.save()
        flash("User created.", "success")
        return redirect(url_for("admin.users_list"))
    roles = Role.objects().order_by("name")
    return render_template("admin/users_form.html", roles=roles)

@bp.route("/users/<user_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def users_edit(user_id):
    # robust fetch: 404 if id is invalid or user doesn't exist
    try:
        u = User.objects.get(id=user_id)
    except (DoesNotExist, ValidationError):
        abort(404)

    if request.method == "POST":
        role_ids = request.form.getlist("roles")
        # optional: filter out invalid ids so we don't error on bad input
        try:
            u.roles = list(Role.objects(id__in=role_ids))
        except ValidationError:
            # if any id is malformed, ignore them (or flash an error if you prefer)
            u.roles = list(Role.objects(id__in=[rid for rid in role_ids if len(rid) == 24]))
        u.save()
        flash("User updated.", "success")
        return redirect(url_for("admin.users_list"))

    roles = Role.objects().order_by("name")
    return render_template("admin/users_edit.html", user=u, roles=roles)


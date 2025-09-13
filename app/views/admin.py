# app/views/admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask import abort
from mongoengine.errors import DoesNotExist, ValidationError
from flask_security import roles_required
from flask_security.utils import hash_password
from app.services.audit import log_action
from ..models.auth import User, Role

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.get("/")
@roles_required("admin")
def admin_index():
    return render_template("admin/index.html")

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
        try:
            log_action("admin.user.create", resource_type="user", resource=email)
        except Exception:
            pass
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

        # Optional password reset
        new_pw = (request.form.get("new_password") or "").strip()
        new_pw2 = (request.form.get("confirm_password") or "").strip()
        if new_pw or new_pw2:
            if not new_pw:
                flash("New password cannot be empty.", "error");
                return redirect(url_for("admin.users_edit", user_id=user_id))
            if new_pw != new_pw2:
                flash("Password confirmation does not match.", "error");
                return redirect(url_for("admin.users_edit", user_id=user_id))
            u.password = hash_password(new_pw)
            try:
                log_action("admin.user.password", resource_type="user", resource=str(u.email))
            except Exception:
                pass

        u.save()
        try:
            log_action("admin.user.edit_roles", resource_type="user", resource=str(u.email))
        except Exception:
            pass
        flash("User updated.", "success")
        return redirect(url_for("admin.users_list"))

    roles = Role.objects().order_by("name")
    return render_template("admin/users_edit.html", user=u, roles=roles)


@bp.route("/purge-parts", methods=["GET", "POST"])
@roles_required("admin")
def purge_parts():
    """Dangerous action: delete all Parts, BOM links, and PartFiles.
    Requires admin and explicit POST with CSRF.
    """
    if request.method == "POST":
        # Import here to avoid circulars at import time
        from ..models.part import Part
        from ..models.bom import BOMLink
        from ..models.artifact import PartFile

        n_files = PartFile.objects.delete()
        n_bom   = BOMLink.objects.delete()
        n_parts = Part.objects.delete()

        try:
            log_action("admin.purge_parts", resource_type="system", resource=f"parts={n_parts},bom={n_bom},files={n_files}")
        except Exception:
            pass
        flash(f"Deleted parts={n_parts}, bom_links={n_bom}, part_files={n_files}", "success")
        return redirect(url_for("admin.users_list"))

    return render_template("admin/purge_parts.html")


# app/views/admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask import abort
from datetime import datetime
from mongoengine.errors import DoesNotExist, ValidationError
from flask_security import roles_required, current_user
from flask_security.utils import hash_password
from app.services.audit import log_action
from ..models.auth import User, Role
from ..models.job import Job
from ..models.supplier import Supplier
from ..models.customer import Customer
from ..models.api_token import ApiToken
from ..models.user_settings import UserSettings
from app.services.app_settings import branding_root, get_app_settings
from zoneinfo import ZoneInfo
import os
import re


def _parse_hw_folders(value: str) -> list[str]:
    raw = [p.strip() for p in re.split(r"[,;\r\n]+", value or "") if p.strip()]
    seen = set()
    out: list[str] = []
    for item in raw:
        token = item.strip().lower()
        if not token or token in seen:
            continue
        out.append(token)
        seen.add(token)
    return out

bp = Blueprint("admin", __name__, url_prefix="/admin")

@bp.get("/")
@roles_required("admin")
def admin_index():
    return render_template("admin/index.html")

@bp.get("/metrics")
@roles_required("admin")
def admin_metrics():
    try:
        from app.services.metrics import get_metrics_store
        file_root = current_app.config.get("FILE_ROOT_LOCAL") or current_app.root_path
        metrics = get_metrics_store().snapshot(file_root=file_root)
    except Exception:
        metrics = {}
    return render_template("admin/metrics.html", metrics=metrics)


@bp.route("/settings", methods=["GET", "POST"])
@roles_required("admin")
def admin_settings():
    settings = get_app_settings(create=True)
    if request.method == "POST":
        tz = (request.form.get("timezone") or "").strip()
        if tz:
            try:
                ZoneInfo(tz)
            except Exception:
                flash("Invalid timezone. Use a valid IANA name like Australia/Melbourne.", "error")
                return redirect(url_for("admin.admin_settings"))
        settings.timezone = tz

        hw_raw = request.form.get("hardware_folders") or ""
        settings.hardware_folders = _parse_hw_folders(hw_raw)

        remove_logo = bool(request.form.get("remove_logo") in ("on", "true", "1", True))
        upload = request.files.get("brand_logo")
        if upload and upload.filename:
            raw = upload.read() or b""
            max_bytes = int(current_app.config.get("BRANDING_LOGO_MAX_BYTES", 2 * 1024 * 1024))
            if len(raw) > max_bytes:
                flash(f"Logo file too large (max {max_bytes} bytes).", "error")
                return redirect(url_for("admin.admin_settings"))
            ext = os.path.splitext(upload.filename)[1].lower()
            if ext not in (".png", ".svg"):
                flash("Logo must be a PNG or SVG file.", "error")
                return redirect(url_for("admin.admin_settings"))
            if ext == ".png" and not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                flash("Invalid PNG file.", "error")
                return redirect(url_for("admin.admin_settings"))
            if ext == ".svg" and b"<svg" not in raw[:2048].lower():
                flash("Invalid SVG file.", "error")
                return redirect(url_for("admin.admin_settings"))
            brand_dir, base_root = branding_root()
            os.makedirs(brand_dir, exist_ok=True)
            target_name = f"logo{ext}"
            abs_path = os.path.join(brand_dir, target_name)
            with open(abs_path, "wb") as fh:
                fh.write(raw)
            try:
                rel_path = os.path.relpath(abs_path, base_root)
            except Exception:
                rel_path = abs_path
            settings.brand_logo_rel_path = rel_path
            remove_logo = False

        if remove_logo:
            settings.brand_logo_rel_path = ""

        settings.updated_at = datetime.utcnow()
        settings.save()
        try:
            current_app.config["HARDWARE_FOLDERS"] = settings.hardware_folders or []
        except Exception:
            pass
        try:
            log_action("admin.settings.update", resource_type="settings", resource="app_settings")
        except Exception:
            pass
        flash("Settings updated.", "success")
        return redirect(url_for("admin.admin_settings"))

    process_meta = current_app.config.get("PROCESS_META", {}) or {}
    process_rows = [(k, v) for k, v in process_meta.items() if not str(k).startswith("_")]
    process_rows.sort(key=lambda item: item[0])
    hw_display = "\n".join(settings.hardware_folders or [])
    return render_template(
        "admin/settings.html",
        settings=settings,
        process_rows=process_rows,
        hardware_folders_text=hw_display,
    )

@bp.route("/users")
@roles_required("admin")
def users_list():
    users = User.objects().order_by("-id").limit(200)
    return render_template("admin/users_list.html", users=users)


def _cleanup_user_references(u: User):
    try:
        Job.objects(participants=u).update(pull__participants=u)
    except Exception:
        pass
    try:
        Supplier.objects(users=u).update(pull__users=u)
    except Exception:
        pass
    try:
        Customer.objects(users=u).update(pull__users=u)
    except Exception:
        pass
    try:
        ApiToken.objects(user_id=u).delete()
    except Exception:
        pass
    try:
        UserSettings.objects(user_id=u).delete()
    except Exception:
        pass


@bp.post("/users/bulk-delete")
@roles_required("admin")
def users_bulk_delete():
    ids = request.form.getlist("user_ids")
    if not ids:
        flash("No users selected.", "error")
        return redirect(url_for("admin.users_list"))
    users = list(User.objects(id__in=ids))
    deleted = 0
    skipped_admin = 0
    skipped_self = 0
    for u in users:
        try:
            if u.has_role("admin"):
                skipped_admin += 1
                continue
        except Exception:
            pass
        try:
            if str(u.id) == str(current_user.id):
                skipped_self += 1
                continue
        except Exception:
            pass
        _cleanup_user_references(u)
        try:
            u.delete()
            deleted += 1
            try:
                log_action("admin.user.delete", resource_type="user", resource=str(u.email))
            except Exception:
                pass
        except Exception:
            pass
    if deleted:
        flash(f"Deleted {deleted} user(s).", "success")
    if skipped_admin:
        flash(f"Skipped {skipped_admin} admin user(s).", "warning")
    if skipped_self:
        flash("Skipped your own account.", "warning")
    return redirect(url_for("admin.users_list"))

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


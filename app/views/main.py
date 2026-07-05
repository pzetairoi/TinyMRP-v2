import os
from datetime import datetime

from flask import Blueprint, render_template, send_file, abort, request, redirect, url_for, flash, current_app
from flask_security import auth_required, current_user
from flask_security.utils import hash_password

from app.services.audit import log_action
from app.services.acl import user_has_permission
from app.services.password_policy import password_policy_summary, validate_password_change
from app.services.user_profile import (
    permissions_for_user,
    profile_color_choices,
    profile_for_user,
    profile_shape_choices,
    role_names_for_user,
    sanitize_profile,
)
from app.services.user_settings import get_or_create_settings
from app.services.timezone_utils import utc_now

bp = Blueprint("main", __name__)


def _can_access(user, perm: str) -> bool:
    roles = {getattr(role, "name", "") for role in (getattr(user, "roles", []) or [])}
    return "admin" in roles or user_has_permission(user, perm)


def _quick_links(user) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    if _can_access(user, "items.view"):
        links.append({"title": "Inventory", "href": "/ui/parts", "description": "Browse parts, files, and part detail."})
    if _can_access(user, "jobs.view"):
        links.append({"title": "Jobs", "href": url_for("admin_jobs.jobs_list"), "description": "Review jobs, BOM requirements, and scope."})
    if _can_access(user, "orders.view"):
        links.append({"title": "Orders", "href": url_for("admin_orders.orders_list"), "description": "Open purchase and sales orders."})
    if _can_access(user, "suppliers.view"):
        links.append({"title": "Suppliers", "href": url_for("admin_suppliers.suppliers_list"), "description": "Manage supplier records and contacts."})
    if _can_access(user, "customers.view"):
        links.append({"title": "Customers", "href": url_for("admin_customers.customers_list"), "description": "Manage customer records and scope."})
    if _can_access(user, "tools.view"):
        links.append({"title": "Tools", "href": url_for("tools.tools_index"), "description": "Open utilities, exports, and admin helpers."})
    if _can_access(user, "import.bom"):
        links.append({"title": "Import", "href": "/ui/upload-pack", "description": "Import BOM packs and associated files."})
    links.append({"title": "Tokens", "href": "/ui/addin/tokens", "description": "Manage API tokens for the add-in and scripts."})
    links.append({"title": "Help", "href": "/help", "description": "Read operator help and troubleshooting notes."})
    return links

def _latest_file(root: str, patterns: list[str]) -> str | None:
    latest = None
    latest_mtime = -1.0
    if not root or not os.path.isdir(root):
        return None
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if not any(name.lower().endswith(pat) for pat in patterns):
                continue
            path = os.path.join(dirpath, name)
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                continue
            if mtime > latest_mtime:
                latest = path
                latest_mtime = mtime
    return latest


def _latest_file_any(roots: list[str], patterns: list[str]) -> str | None:
    latest = None
    latest_mtime = -1.0
    for root in roots:
        path = _latest_file(root, patterns)
        if not path:
            continue
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            continue
        if mtime > latest_mtime:
            latest = path
            latest_mtime = mtime
    return latest

@bp.route("/")
def index():
    return render_template("index.html")

@bp.route("/app")
@auth_required()
def app_home():
    settings = get_or_create_settings(current_user)
    profile = profile_for_user(current_user, settings)
    security_summary = password_policy_summary()
    security_summary.update(
        {
            "last_login_at": current_user.last_login_at,
            "last_login_ip": current_user.last_login_ip,
            "last_login_ua": current_user.last_login_ua,
            "password_changed_at": current_user.password_changed_at,
            "account_created_at": current_user.created_at,
            "account_updated_at": current_user.updated_at,
            "session_timeout_minutes": int(current_app.config.get("PERMANENT_SESSION_LIFETIME").total_seconds() // 60),
            "generic_auth_responses": bool(current_app.config.get("SECURITY_RETURN_GENERIC_RESPONSES")),
            "secure_cookie": bool(current_app.config.get("SESSION_COOKIE_SECURE")),
            "remember_cookie_secure": bool(current_app.config.get("REMEMBER_COOKIE_SECURE")),
        }
    )
    return render_template(
        "home.html",
        user=current_user,
        profile=profile,
        role_names=role_names_for_user(current_user),
        permissions=permissions_for_user(current_user),
        profile_colors=profile_color_choices(),
        profile_shapes=profile_shape_choices(),
        quick_links=_quick_links(current_user),
        security_summary=security_summary,
    )


@bp.post("/app/profile")
@auth_required()
def app_profile_update():
    settings = get_or_create_settings(current_user)
    profile = sanitize_profile(
        {
            "display_name": request.form.get("display_name"),
            "avatar_color": request.form.get("avatar_color"),
            "avatar_shape": request.form.get("avatar_shape"),
        }
    )
    settings.profile = profile
    settings.updated_at = utc_now()
    settings.save()
    try:
        current_user.updated_at = utc_now()
        current_user.save()
    except Exception:
        pass
    try:
        log_action("account.profile.update", resource_type="user", resource=str(current_user.email or ""))
    except Exception:
        pass
    flash("Account profile updated.", "success")
    return redirect(url_for("main.app_home"))


@bp.post("/app/password")
@auth_required()
def app_password_change():
    errors = validate_password_change(
        current_password=request.form.get("current_password") or "",
        current_password_hash=current_user.password,
        new_password=request.form.get("new_password") or "",
        confirm_password=request.form.get("confirm_password") or "",
        email=current_user.email or "",
    )
    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("main.app_home"))

    current_user.password = hash_password(request.form.get("new_password") or "")
    current_user.password_changed_at = utc_now()
    current_user.updated_at = utc_now()
    current_user.save()
    try:
        log_action("account.password.change", resource_type="user", resource=str(current_user.email or ""))
    except Exception:
        pass
    flash("Password changed.", "success")
    return redirect(url_for("main.app_home"))


@bp.get("/downloads/macro")
def download_macro():
    roots = []
    env_root = os.getenv("MACRO_FILES_ROOT") or ""
    if env_root.strip():
        roots.append(os.path.abspath(env_root))
    roots.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "misc")))
    path = _latest_file_any(roots, [".swp"])
    if not path or not os.path.isfile(path):
        abort(404)
    try:
        log_action("download.macro", resource_type="download", resource=os.path.basename(path), meta={"source": "landing"})
    except Exception:
        pass
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@bp.get("/downloads/addin")
def download_addin():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "solidworks-addin", "Windows Installer latest"))
    path = _latest_file(root, [".exe", ".msi"])
    if not path or not os.path.isfile(path):
        abort(404)
    try:
        log_action("download.addin", resource_type="download", resource=os.path.basename(path), meta={"source": "landing"})
    except Exception:
        pass
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

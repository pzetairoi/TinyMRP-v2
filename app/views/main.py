import os
from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, render_template, send_file, abort, request, redirect, url_for, flash, current_app
from flask_login import login_required
from flask_security import auth_required, current_user
from flask_security.utils import hash_password

from app.models.audit import AuditLog
from app.models.job import Job
from app.models.order import Order
from app.models.part import Part
from app.services.audit import log_action
from app.services.acl import (
    permissions_required,
    user_can_view_items,
    user_has_permission,
)
from app.services.authorization import authorised_get, has_permission, scope_queryset
from app.services.attrs import approval_field_values, harvest_part_attrs
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
from app.views.api_helpers import add_datetime_fields

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


def _has_any_permission(user, *perms: str) -> bool:
    return any(_can_access(user, perm) for perm in perms)


def _parts_base_query(user):
    if not has_permission(user, "parts.read"):
        return None
    return scope_queryset(Part.objects, user, "parts")


def _part_href(part_number: str, revision: str) -> str:
    rev_clean = (revision or "").strip()
    kwargs = {"pn": part_number}
    if rev_clean:
        kwargs["rev"] = rev_clean
    return url_for("ui.part_ui", **kwargs)


def _job_href(user, job_id: str) -> str | None:
    if _can_access(user, "jobs.view"):
        return url_for("admin_jobs.jobs_view", job_id=job_id)
    if _can_access(user, "jobs.manage"):
        return url_for("admin_jobs.jobs_edit", job_id=job_id)
    return None


def _order_href(user, order_id: str) -> str | None:
    if _can_access(user, "orders.view"):
        return url_for("admin_orders.orders_view", order_id=order_id)
    if _can_access(user, "orders.manage"):
        return url_for("admin_orders.orders_edit", order_id=order_id)
    return None


def _recently_visited_resources(user, action: str, limit: int, scan_cap: int = 200) -> list[str]:
    """Distinct resource identifiers this user actually opened, most-recent
    first, sourced from the audit log rather than "recently updated by
    anyone" -- the latter isn't personal and isn't what "recently visited"
    means to the person looking at their own home page.
    """
    uid = str(getattr(user, "id", "") or "")
    if not uid:
        return []
    seen: set[str] = set()
    out: list[str] = []
    try:
        entries = (
            AuditLog.objects(user_id=uid, action=action)
            .order_by("-ts")
            .only("resource")
            .limit(scan_cap)
        )
        for entry in entries:
            resource = (entry.resource or "").strip()
            if not resource or resource in seen:
                continue
            seen.add(resource)
            out.append(resource)
            if len(out) >= limit:
                break
    except Exception:
        pass
    return out


def _recent_parts(user, limit: int = 5) -> list[dict[str, object]]:
    base = _parts_base_query(user)
    if base is None:
        return []

    rows: list[dict[str, object]] = []
    for resource in _recently_visited_resources(user, "part.view", limit):
        pn, _, rev = resource.partition(":")
        pn = pn.strip()
        if not pn:
            continue
        part = (
            base.filter(part_number__iexact=pn, revision__iexact=rev.strip())
            .only("part_number", "revision", "description", "status", "attrs", "updated_at")
            .first()
        )
        if not part:
            continue
        attrs = harvest_part_attrs(part)
        approval = approval_field_values(attrs)
        revision = (attrs.get("revision") or part.revision or "").strip()
        row: dict[str, object] = {
            "part_number": part.part_number,
            "revision": revision,
            "description": part.description or attrs.get("description") or "No description recorded",
            "status": (part.status or "").strip() or "active",
            "approved": bool(approval.get("approved")),
            "approved_by": approval.get("approved_by") or "",
            "href": _part_href(part.part_number, revision),
        }
        add_datetime_fields(row, "updated_at", part.updated_at)
        rows.append(row)
    return rows


def _recent_jobs(user, limit: int = 5) -> list[dict[str, object]]:
    if not _has_any_permission(user, "jobs.read"):
        return []

    rows: list[dict[str, object]] = []
    for resource in _recently_visited_resources(user, "job.view", limit):
        try:
            job_oid = ObjectId(resource)
        except (InvalidId, TypeError):
            continue
        job = authorised_get(
            Job.objects(is_deleted=False).only(
                "job_number",
                "title",
                "description",
                "status",
                "customer",
                "updated_at",
                "created_at",
            ),
            user,
            job_oid,
            resource_type="jobs",
        )
        if not job:
            continue
        try:
            customer_name = job.customer.name if job.customer else ""
        except Exception:
            customer_name = ""
        row: dict[str, object] = {
            "job_number": job.job_number,
            "title": (job.title or job.description or "").strip() or "No title recorded",
            "status": (job.status or "").strip() or "draft",
            "customer_name": customer_name or "No customer assigned",
            "href": _job_href(user, str(job.id)),
        }
        add_datetime_fields(row, "updated_at", job.updated_at or job.created_at)
        rows.append(row)
    return rows


def _recent_orders(user, limit: int = 5) -> list[dict[str, object]]:
    if not _has_any_permission(user, "orders.read"):
        return []

    rows: list[dict[str, object]] = []
    for resource in _recently_visited_resources(user, "order.view", limit):
        try:
            order_oid = ObjectId(resource)
        except (InvalidId, TypeError):
            continue
        order = authorised_get(
            Order.objects.only(
                "order_number",
                "description",
                "kind",
                "status",
                "customer",
                "supplier",
                "updated_at",
                "order_date",
            ),
            user,
            order_oid,
            resource_type="orders",
        )
        if not order:
            continue
        try:
            supplier_name = order.supplier.name if order.supplier else ""
        except Exception:
            supplier_name = ""
        try:
            customer_name = order.customer.name if order.customer else ""
        except Exception:
            customer_name = ""
        company_name = supplier_name or customer_name or "No company assigned"
        row: dict[str, object] = {
            "order_number": order.order_number,
            "description": (order.description or "").strip() or "No description recorded",
            "kind": (order.kind or "").strip() or "purchase",
            "status": (order.status or "").strip() or "draft",
            "company_name": company_name,
            "href": _order_href(user, str(order.id)),
        }
        add_datetime_fields(row, "updated_at", order.updated_at or order.order_date)
        rows.append(row)
    return rows


HOME_ITEMS_LIMIT_CHOICES = (3, 5, 10)
_DEFAULT_HOME_PREFS = {"show_parts": True, "show_jobs": True, "show_orders": True, "items_limit": 5}


def _home_prefs_for_user(settings) -> dict[str, object]:
    raw = {}
    try:
        raw = (settings.ui_preferences or {}).get("home") or {}
    except Exception:
        raw = {}
    prefs = dict(_DEFAULT_HOME_PREFS)
    for key in ("show_parts", "show_jobs", "show_orders"):
        if key in raw:
            prefs[key] = bool(raw.get(key))
    try:
        limit = int(raw.get("items_limit", prefs["items_limit"]))
    except (TypeError, ValueError):
        limit = prefs["items_limit"]
    prefs["items_limit"] = limit if limit in HOME_ITEMS_LIMIT_CHOICES else _DEFAULT_HOME_PREFS["items_limit"]
    return prefs


def _home_dashboard_context(user, permissions: list[str], home_prefs: dict[str, object]) -> dict[str, object]:
    limit = int(home_prefs.get("items_limit") or _DEFAULT_HOME_PREFS["items_limit"])
    can_view_parts = user_can_view_items(user)
    can_view_jobs = _has_any_permission(user, "jobs.view", "jobs.manage")
    can_view_orders = _has_any_permission(user, "orders.view", "orders.manage")
    show_parts = can_view_parts and bool(home_prefs.get("show_parts", True))
    show_jobs = can_view_jobs and bool(home_prefs.get("show_jobs", True))
    show_orders = can_view_orders and bool(home_prefs.get("show_orders", True))

    recent_parts = _recent_parts(user, limit=limit) if show_parts else []
    recent_jobs = _recent_jobs(user, limit=limit) if show_jobs else []
    recent_orders = _recent_orders(user, limit=limit) if show_orders else []

    summary_bits: list[str] = []
    if recent_parts:
        summary_bits.append(f"{len(recent_parts)} recent parts")
    if recent_jobs:
        summary_bits.append(f"{len(recent_jobs)} recent jobs")
    if recent_orders:
        summary_bits.append(f"{len(recent_orders)} recent orders")
    subtitle = "See what you've recently visited and customize what shows up here."
    if summary_bits:
        subtitle = "Currently showing " + ", ".join(summary_bits[:-1] + ([f"and {summary_bits[-1]}"] if len(summary_bits) > 1 else [summary_bits[-1]])) + "."

    return {
        "subtitle": subtitle,
        "recent_parts": recent_parts,
        "recent_jobs": recent_jobs,
        "recent_orders": recent_orders,
        "show_parts": show_parts,
        "show_jobs": show_jobs,
        "show_orders": show_orders,
        "can_view_parts": can_view_parts,
        "can_view_jobs": can_view_jobs,
        "can_view_orders": can_view_orders,
        "permissions_count": len(permissions),
        "home_prefs": home_prefs,
        "home_items_limit_choices": HOME_ITEMS_LIMIT_CHOICES,
    }

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
    role_names = role_names_for_user(current_user)
    permissions = permissions_for_user(current_user)
    security_summary = password_policy_summary()
    security_summary.update(
        {
            "last_login_at": current_user.last_login_at,
            "last_login_ip": current_user.last_login_ip,
            "password_changed_at": current_user.password_changed_at,
            "account_created_at": current_user.created_at,
            "account_updated_at": current_user.updated_at,
            "session_timeout_minutes": int(current_app.config.get("PERMANENT_SESSION_LIFETIME").total_seconds() // 60),
        }
    )
    home_prefs = _home_prefs_for_user(settings)
    dashboard = _home_dashboard_context(current_user, permissions, home_prefs)
    return render_template(
        "home.html",
        user=current_user,
        profile=profile,
        role_names=role_names,
        permissions=permissions,
        profile_colors=profile_color_choices(),
        profile_shapes=profile_shape_choices(),
        quick_links=_quick_links(current_user),
        security_summary=security_summary,
        dashboard=dashboard,
    )


@bp.post("/app/home-prefs")
@auth_required()
def app_home_prefs_update():
    settings = get_or_create_settings(current_user)
    prefs = dict(_DEFAULT_HOME_PREFS)
    prefs["show_parts"] = "show_parts" in request.form
    prefs["show_jobs"] = "show_jobs" in request.form
    prefs["show_orders"] = "show_orders" in request.form
    try:
        limit = int(request.form.get("items_limit", _DEFAULT_HOME_PREFS["items_limit"]))
    except (TypeError, ValueError):
        limit = _DEFAULT_HOME_PREFS["items_limit"]
    prefs["items_limit"] = limit if limit in HOME_ITEMS_LIMIT_CHOICES else _DEFAULT_HOME_PREFS["items_limit"]

    ui_prefs = dict(settings.ui_preferences or {})
    ui_prefs["home"] = prefs
    settings.ui_preferences = ui_prefs
    settings.updated_at = utc_now()
    settings.save()
    flash("Dashboard preferences saved.", "success")
    return redirect(url_for("main.app_home") + "#recent-activity")


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
@login_required
@permissions_required("tools.view")
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
        log_action("download.macro", resource_type="download", resource=os.path.basename(path), meta={"source": "tools"})
    except Exception:
        pass
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@bp.get("/downloads/addin")
@login_required
@permissions_required("tools.view")
def download_addin():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "solidworks-addin", "Windows Installer latest"))
    path = _latest_file(root, [".exe", ".msi"])
    if not path or not os.path.isfile(path):
        abort(404)
    try:
        log_action("download.addin", resource_type="download", resource=os.path.basename(path), meta={"source": "tools"})
    except Exception:
        pass
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

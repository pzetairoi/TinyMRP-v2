import os
from datetime import datetime

from flask import Blueprint, render_template, send_file, abort, request, redirect, url_for, flash, current_app
from flask_security import auth_required, current_user
from flask_security.utils import hash_password
from mongoengine.queryset.visitor import Q

from app.models.job import Job
from app.models.order import Order
from app.models.part import Part
from app.services.audit import log_action
from app.services.acl import (
    allowed_parts_for,
    apply_job_scope,
    apply_order_scope,
    user_can_view_items,
    user_has_permission,
)
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


def _allowed_parts_q(user) -> Q | None:
    allowed = allowed_parts_for(user)
    if allowed is None:
        return None
    q = Q(id__in=[])
    has_matches = False
    for pn, rev in allowed:
        pn_clean = (pn or "").strip()
        if not pn_clean:
            continue
        has_matches = True
        rev_clean = (rev or "").strip()
        if rev_clean:
            q = q | Q(part_number__iexact=pn_clean, revision__iexact=rev_clean)
        else:
            q = q | Q(part_number__iexact=pn_clean)
    return q if has_matches else Q(id__in=[])


def _parts_base_query(user):
    if not user_can_view_items(user):
        return None
    qs = Part.objects
    allowed_q = _allowed_parts_q(user)
    if allowed_q is not None:
        qs = qs.filter(allowed_q)
    return qs


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


def _recent_parts(user, limit: int = 5) -> list[dict[str, object]]:
    base = _parts_base_query(user)
    if base is None:
        return []

    rows: list[dict[str, object]] = []
    for part in (
        base.order_by("-updated_at")
        .only("part_number", "revision", "description", "status", "attrs", "updated_at")
        .limit(limit)
    ):
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
    if not _has_any_permission(user, "jobs.view", "jobs.manage"):
        return []

    rows: list[dict[str, object]] = []
    jobs = (
        apply_job_scope(Job.objects(is_deleted=False), user)
        .order_by("-updated_at")
        .only("job_number", "title", "description", "status", "customer", "updated_at", "created_at")
        .limit(limit)
    )
    for job in jobs:
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
    if not _has_any_permission(user, "orders.view", "orders.manage"):
        return []

    rows: list[dict[str, object]] = []
    orders = (
        apply_order_scope(Order.objects(), user)
        .order_by("-updated_at")
        .only("order_number", "description", "kind", "status", "customer", "supplier", "updated_at", "order_date")
        .limit(limit)
    )
    for order in orders:
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


def _attention_items(user) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    parts_q = _parts_base_query(user)
    if parts_q is not None:
        missing_description = parts_q.filter(
            __raw__={
                "$and": [
                    {"$or": [{"description": {"$exists": False}}, {"description": ""}, {"description": None}]},
                    {"$or": [{"attrs.description": {"$exists": False}}, {"attrs.description": ""}, {"attrs.description": None}]},
                ]
            }
        ).count()
        missing_process = parts_q.filter(
            __raw__={"$or": [{"processes": {"$exists": False}}, {"processes": {"$size": 0}}]}
        ).count()
        missing_material = parts_q.filter(
            __raw__={
                "$or": [
                    {"canonical.material": {"$exists": False}},
                    {"canonical.material": ""},
                    {"canonical.material": None},
                ]
            }
        ).count()
        if missing_description:
            items.append(
                {
                    "title": "Parts missing descriptions",
                    "count": missing_description,
                    "detail": "Visible parts still need a usable description.",
                    "href": url_for("ui.parts_ui"),
                }
            )
        if missing_process:
            items.append(
                {
                    "title": "Parts missing process metadata",
                    "count": missing_process,
                    "detail": "Visible parts do not yet have process assignments.",
                    "href": url_for("ui.parts_ui"),
                }
            )
        if missing_material:
            items.append(
                {
                    "title": "Parts missing material",
                    "count": missing_material,
                    "detail": "Material is still blank on visible parts.",
                    "href": url_for("ui.parts_ui"),
                }
            )

    if _has_any_permission(user, "jobs.view", "jobs.manage"):
        jobs_q = apply_job_scope(Job.objects(is_deleted=False), user)
        overdue_jobs = jobs_q.filter(status__in=["released", "in_progress"], scheduled_end__lt=utc_now()).count()
        active_jobs = jobs_q.filter(status__in=["released", "in_progress", "on_hold"]).count()
        if overdue_jobs:
            items.append(
                {
                    "title": "Jobs past scheduled end",
                    "count": overdue_jobs,
                    "detail": "Released or in-progress jobs are already past their planned end date.",
                    "href": url_for("admin_jobs.jobs_list") if _can_access(user, "jobs.view") else None,
                }
            )
        elif active_jobs:
            items.append(
                {
                    "title": "Active jobs in progress",
                    "count": active_jobs,
                    "detail": "Open jobs are visible and may need scheduling or purchasing follow-up.",
                    "href": url_for("admin_jobs.jobs_list") if _can_access(user, "jobs.view") else None,
                }
            )

    if _has_any_permission(user, "orders.view", "orders.manage"):
        orders_q = apply_order_scope(Order.objects(), user)
        open_orders = orders_q.filter(status__nin=["delivered", "cancelled"]).count()
        if open_orders:
            items.append(
                {
                    "title": "Open orders",
                    "count": open_orders,
                    "detail": "Draft and in-flight orders remain visible to this account.",
                    "href": url_for("admin_orders.orders_list") if _can_access(user, "orders.view") else None,
                }
            )
    return items


def _quick_actions_for_home(user) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if user_can_view_items(user):
        actions.append(
            {
                "title": "Find Parts",
                "href": url_for("ui.parts_ui"),
                "description": "Browse part detail, BOM, and deliverables.",
            }
        )
    if _can_access(user, "import.bom"):
        actions.append(
            {
                "title": "Upload Pack",
                "href": url_for("ui.upload_pack_ui"),
                "description": "Import a BOM ZIP and associated files.",
            }
        )
    if _can_access(user, "jobs.manage"):
        actions.append(
            {
                "title": "New Job",
                "href": url_for("admin_jobs.jobs_new"),
                "description": "Create a new manufacturing or work-order job.",
            }
        )
    elif _can_access(user, "jobs.view"):
        actions.append(
            {
                "title": "Jobs",
                "href": url_for("admin_jobs.jobs_list"),
                "description": "Review active and recent jobs.",
            }
        )
    if _can_access(user, "orders.manage"):
        actions.append(
            {
                "title": "New Order",
                "href": url_for("admin_orders.orders_new"),
                "description": "Open a new purchase or sales order.",
            }
        )
    elif _can_access(user, "orders.view"):
        actions.append(
            {
                "title": "Orders",
                "href": url_for("admin_orders.orders_list"),
                "description": "Review visible purchase and sales orders.",
            }
        )
    if _has_any_permission(user, "customers.view", "customers.manage"):
        actions.append(
            {
                "title": "Customers",
                "href": url_for("admin_customers.customers_list"),
                "description": "Open customer records and linked work.",
            }
        )
    if _has_any_permission(user, "suppliers.view", "suppliers.manage"):
        actions.append(
            {
                "title": "Suppliers",
                "href": url_for("admin_suppliers.suppliers_list"),
                "description": "Open supplier records and linked orders.",
            }
        )
    if _can_access(user, "tools.view"):
        actions.append(
            {
                "title": "Tools",
                "href": url_for("tools.tools_index"),
                "description": "Open installers and utility workflows.",
            }
        )
    return actions


def _home_dashboard_context(user, permissions: list[str]) -> dict[str, object]:
    recent_parts = _recent_parts(user)
    recent_jobs = _recent_jobs(user)
    recent_orders = _recent_orders(user)
    attention_items = _attention_items(user)
    attention_total = sum(int(item.get("count", 0) or 0) for item in attention_items)

    summary_bits: list[str] = []
    if recent_parts:
        summary_bits.append(f"{len(recent_parts)} recent parts")
    if recent_jobs:
        summary_bits.append(f"{len(recent_jobs)} recent jobs")
    if recent_orders:
        summary_bits.append(f"{len(recent_orders)} recent orders")
    if attention_total:
        summary_bits.append(f"{attention_total} attention items")
    subtitle = "See recent activity, pending attention items, and safe next actions for your current access."
    if summary_bits:
        subtitle = "Currently showing " + ", ".join(summary_bits[:-1] + ([f"and {summary_bits[-1]}"] if len(summary_bits) > 1 else [summary_bits[-1]])) + "."

    return {
        "subtitle": subtitle,
        "recent_parts": recent_parts,
        "recent_jobs": recent_jobs,
        "recent_orders": recent_orders,
        "attention_items": attention_items,
        "quick_actions": _quick_actions_for_home(user),
        "show_parts": user_can_view_items(user),
        "show_jobs": _has_any_permission(user, "jobs.view", "jobs.manage"),
        "show_orders": _has_any_permission(user, "orders.view", "orders.manage"),
        "permissions_count": len(permissions),
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
    dashboard = _home_dashboard_context(current_user, permissions)
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

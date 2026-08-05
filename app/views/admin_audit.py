from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app
from mongoengine.queryset.visitor import Q

from app.models.audit import AuditLog
from app.models.auth import User
from app.services.audit import log_action
from app.services.authorization import require_permission
from app.services.timezone_utils import local_input_value, parse_user_datetime, resolve_timezone_name
from mongoengine import get_connection

bp = Blueprint("admin_audit", __name__, url_prefix="/admin/audit")

AUDIT_CATEGORIES = {
    "view": ("Viewed", ("part.view", "parts.list", "whereused.view", "file.list", "file.view", "part.files.view", "docpack.options")),
    "change": ("Changed", ("part.notes.update", "part.comments.add", "part.files.refresh", "part.delete")),
    "upload": ("Uploaded", ("upload.", "import.")),
    "export": ("Exported", ("arena.export.", "docpack.build", "download.")),
    "access": ("Access & admin", ("account.", "admin.", "session.", "share.")),
}

ACTION_LABELS = {
    "parts.list": "Browsed the parts table",
    "part.view": "Opened a part",
    "part.view.deny": "Was denied access to a part",
    "whereused.view": "Checked where a part is used",
    "part.files.view": "Viewed part files",
    "file.view": "Opened a file",
    "file.list": "Listed available files",
    "part.notes.update": "Updated part notes",
    "part.comments.add": "Added a part comment",
    "part.files.refresh": "Refreshed part files",
    "part.delete": "Deleted a part",
    "upload.pack": "Uploaded a BOM pack",
    "upload.extra_files": "Uploaded part files",
    "arena.export.bom": "Exported an Arena BOM",
    "arena.export.files": "Exported Arena file links",
    "docpack.build": "Built a document pack",
    "account.profile.update": "Updated their profile",
    "account.password.change": "Changed their password",
    "session.security_event_revoke": "Signed out existing browser sessions",
    "admin.settings.update": "Changed application settings",
}


def _audit_category(action: str) -> tuple[str, str]:
    action_text = str(action or "")
    for key, (label, prefixes) in AUDIT_CATEGORIES.items():
        if any(action_text == prefix or action_text.startswith(prefix) for prefix in prefixes):
            return key, label
    return "other", "Other"


def _activity_summary(user_id: str) -> dict | None:
    if not user_id:
        return None
    base = AuditLog.objects(user_id=user_id)
    latest = base.order_by("-ts").first()
    part_resources = set()
    for row in base(action="part.view").only("resource").limit(5000):
        if row.resource:
            part_resources.add(row.resource)
    upload_rows = list(base(action__in=["upload.pack", "upload.extra_files"]).only("action", "extra"))
    parts_uploaded = 0
    files_uploaded = 0
    for row in upload_rows:
        extra = row.extra or {}
        parts_uploaded += int(extra.get("parts_imported") or extra.get("imported_parts") or 0)
        files_uploaded += int(extra.get("files_uploaded") or extra.get("file_count") or 0)
    changes = sum(
        base(action__icontains=token).count()
        for token in ("update", "add", "delete", "create", "edit", "refresh")
    )
    exports = sum(base(action__startswith=prefix).count() for prefix in ("arena.export", "docpack.build", "download."))
    try:
        user = User.objects(id=user_id).only("email").first()
    except Exception:
        user = None
    return {
        "total_events": base.count(),
        "last_activity": latest.ts if latest else None,
        "parts_viewed": len(part_resources),
        "upload_actions": len(upload_rows),
        "parts_uploaded": parts_uploaded,
        "files_uploaded": files_uploaded,
        "changes": changes,
        "exports": exports,
        "email": (user.email if user else "") or (latest.email if latest else ""),
    }

def _parse_dt(value: str | None, end: bool = False) -> datetime | None:
    return parse_user_datetime(value, end_of_day=end)


@bp.get("/")
@require_permission("audit.read")
def audit_list():
    qtext = (request.args.get("q") or "").strip().lower()
    limit = int(request.args.get("limit") or 200)
    offset = int(request.args.get("offset") or 0)
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    email = (request.args.get("email") or request.args.get("user") or "").strip()
    user_id = (request.args.get("user_id") or "").strip()
    ip = (request.args.get("ip") or "").strip()
    action = (request.args.get("action") or "").strip()
    endpoint = (request.args.get("endpoint") or "").strip()
    method = (request.args.get("method") or "").strip()
    resource_type = (request.args.get("resource_type") or "").strip()
    category = (request.args.get("category") or "").strip().lower()
    start = _parse_dt(request.args.get("start"))
    end = _parse_dt(request.args.get("end"), end=True)

    q = Q()
    if qtext:
        # simple OR contains across email, action, resource, ip
        q = (
            Q(email__icontains=qtext)
            | Q(action__icontains=qtext)
            | Q(resource__icontains=qtext)
            | Q(ip__icontains=qtext)
            | Q(endpoint__icontains=qtext)
        )
    if email:
        q = q & Q(email__icontains=email)
    if user_id:
        q = q & Q(user_id=user_id)
    if ip:
        q = q & Q(ip__icontains=ip)
    if action:
        q = q & Q(action__icontains=action)
    if endpoint:
        q = q & Q(endpoint__icontains=endpoint)
    if method:
        q = q & Q(method__iexact=method)
    if resource_type:
        q = q & Q(resource_type__icontains=resource_type)
    if category in AUDIT_CATEGORIES:
        category_q = Q(action="__never__")
        for prefix in AUDIT_CATEGORIES[category][1]:
            category_q = category_q | Q(action__startswith=prefix)
        q = q & category_q
    if start:
        q = q & Q(ts__gte=start)
    if end:
        q = q & Q(ts__lte=end)

    logs = list(AuditLog.objects(q).order_by("-ts").skip(offset).limit(limit))
    audit_rows = []
    for entry in logs:
        category_key, category_label = _audit_category(entry.action)
        audit_rows.append(
            {
                "entry": entry,
                "category": category_key,
                "category_label": category_label,
                "label": ACTION_LABELS.get(entry.action, str(entry.action or "Activity").replace(".", " ").title()),
            }
        )
    total = AuditLog.objects.count()
    filtered_total = AuditLog.objects(q).count()
    # Diagnostics: try pinging the Mongo server for the configured alias
    alias = current_app.config.get("MONGODB_ALIAS", "tinymrp-v2")
    uri = current_app.config.get("MONGO_URI")
    ping_ok = None
    try:
        client = get_connection(alias=alias)
        client.admin.command('ping')
        ping_ok = True
    except Exception:
        ping_ok = False
    return render_template(
        "admin/audit_list.html",
        logs=logs,
        audit_rows=audit_rows,
        activity_summary=_activity_summary(user_id),
        audit_categories=[(key, value[0]) for key, value in AUDIT_CATEGORIES.items()],
        category=category,
        q=qtext,
        limit=limit,
        offset=offset,
        total=total,
        filtered_total=filtered_total,
        email=email,
        user_id=user_id,
        ip=ip,
        action=action,
        endpoint=endpoint,
        method=method,
        resource_type=resource_type,
        start=local_input_value(start),
        end=local_input_value(end),
        alias=alias,
        uri=uri,
        ping_ok=ping_ok,
        selected_timezone=resolve_timezone_name(),
    )


@bp.post("/test")
@require_permission("system.maintenance")
def audit_test():
    try:
        log_action("admin.audit.test", resource_type="system", resource="manual-test")
        flash("Inserted a test audit entry.", "success")
    except Exception as e:
        flash(f"Failed to write audit entry: {e}", "error")
    return redirect(url_for("admin_audit.audit_list"))

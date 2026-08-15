from datetime import datetime, timedelta
from urllib.parse import parse_qs, unquote, urlsplit
from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app
from mongoengine.queryset.visitor import Q

from app.models.audit import AuditLog
from app.models.auth import User
from app.services.audit import _safe_page_path, log_action
from app.services.authorization import require_permission
from app.services.timezone_utils import local_input_value, parse_user_datetime, resolve_timezone_name, utc_now
from mongoengine import get_connection

bp = Blueprint("admin_audit", __name__, url_prefix="/admin/audit")

AUDIT_CATEGORIES = {
    "view": ("Viewed", ("part.view", "parts.list", "whereused.view", "file.list", "file.view", "part.files.view", "docpack.options", "bom.view", "job.view", "order.view")),
    "change": ("Changed", ("part.notes.update", "part.comments.add", "part.files.refresh", "part.delete")),
    "upload": ("Uploaded", ("upload.", "import.")),
    "export": ("Exported", ("arena.export.", "docpack.build", "download.")),
    "access": ("Access & admin", ("account.", "admin.", "session.", "share.", "auth.", "authorization.", "api_token.")),
}

RANGE_OPTIONS = {
    "24h": ("Last 24 hours", timedelta(hours=24)),
    "7d": ("Last 7 days", timedelta(days=7)),
    "30d": ("Last 30 days", timedelta(days=30)),
    "90d": ("Last 90 days", timedelta(days=90)),
}

ACTION_LABELS = {
    "auth.login": "Signed in",
    "auth.logout": "Signed out",
    "parts.list": "Browsed the parts table",
    "part.view": "Opened a part",
    "part.view.deny": "Was denied access to a part",
    "whereused.view": "Checked where a part is used",
    "bom.view": "Opened a bill of materials",
    "job.view": "Opened a job",
    "order.view": "Opened an order",
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
    "authorization.denied": "Was denied access",
}

_PAGE_LABELS = {
    "/app": "Home",
    "/ui/dashboard": "Dashboard",
    "/ui/parts": "Parts",
    "/ui/bom": "Bill of materials",
    "/ui/upload-pack": "Upload pack",
    "/ui/addin/tokens": "Add-in tokens",
    "/ui/admin/addin": "Add-in administration",
    "/ui/admin/fields": "Part field configuration",
    "/admin": "Administration",
    "/admin/audit": "Audit log",
    "/admin/settings": "Application settings",
    "/admin/users": "Users",
    "/admin/roles": "Roles",
    "/tools": "Tools",
}

_ACTION_PAGE_LABELS = {
    "parts.list": "Parts",
    "part.view": "Part detail",
    "part.files.view": "Part detail · Files",
    "file.list": "Part detail · Files",
    "file.view": "File viewer",
    "whereused.view": "Where used",
    "bom.view": "Bill of materials",
    "docpack.options": "Part detail · Document pack",
    "docpack.build": "Document pack",
    "upload.pack": "Upload pack",
    "upload.extra_files": "Upload pack",
    "account.profile.update": "Profile",
    "account.password.change": "Profile · Security",
}

_SENSITIVE_META_FRAGMENTS = ("password", "secret", "token", "authorization", "cookie")


def _audit_category(action: str) -> tuple[str, str]:
    action_text = str(action or "")
    for key, (label, prefixes) in AUDIT_CATEGORIES.items():
        if any(action_text == prefix or action_text.startswith(prefix) for prefix in prefixes):
            return key, label
    return "other", "Other"


def _resource_label(entry: AuditLog) -> str:
    resource = str(entry.resource or "").strip()
    if not resource or entry.action == "parts.list":
        return ""
    if entry.resource_type in {"part", "bom", "whereused", "docpack"}:
        cleaned = resource
        for prefix in ("root:", "flat:", "children:"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
                break
        part_number, separator, revision = cleaned.rpartition(":")
        if separator and part_number:
            return f"{part_number} · Rev {revision}" if revision else part_number
    return resource


def _friendly_page_label(page_path: str, entry: AuditLog) -> str:
    parsed = urlsplit(page_path or "")
    path = parsed.path.rstrip("/") or "/"
    revision = (parse_qs(parsed.query).get("rev") or [""])[0]
    if path.startswith("/ui/part/"):
        part_number = unquote(path.removeprefix("/ui/part/"))
        return f"Part {part_number}{f' · Rev {revision}' if revision else ''}"
    if path.startswith("/ui/bom/"):
        part_number = unquote(path.removeprefix("/ui/bom/"))
        return f"BOM {part_number}{f' · Rev {revision}' if revision else ''}"
    if path.startswith("/admin/users/"):
        return "User administration"
    if path.startswith("/admin/roles/"):
        return "Role administration"
    for prefix, label in sorted(_PAGE_LABELS.items(), key=lambda item: len(item[0]), reverse=True):
        if path == prefix or path.startswith(f"{prefix}/"):
            return label
    action_label = _ACTION_PAGE_LABELS.get(str(entry.action or ""))
    if action_label:
        resource = _resource_label(entry)
        if entry.action == "part.view" and resource:
            return f"Part {resource}"
        return action_label
    if path.startswith("/api/"):
        return "Background request"
    words = path.strip("/").split("/")[-1].replace("-", " ").replace("_", " ")
    return words.title() if words else "Unknown page"


def _entry_page(entry: AuditLog) -> dict:
    extra = entry.extra or {}
    page_path = _safe_page_path(extra.get("page_path") or extra.get("referrer") or "")
    # Old records predate explicit page capture. Their endpoint is still a
    # useful fallback, and the friendly label is inferred from the action.
    display_path = page_path or str(entry.endpoint or "")
    return {
        "label": _friendly_page_label(display_path, entry),
        "path": display_path,
        "filter": page_path or str(entry.endpoint or ""),
        "is_ui_page": bool(page_path and not urlsplit(page_path).path.startswith("/api/")),
    }


def _redact_meta(value, key: str = ""):
    if any(fragment in key.lower() for fragment in _SENSITIVE_META_FRAGMENTS):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(k): _redact_meta(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_meta(item, key) for item in value]
    return value


def _display_meta(entry: AuditLog) -> dict:
    hidden = {"page_path", "referrer", "endpoint_name", "request_id"}
    return {
        str(key): _redact_meta(value, str(key))
        for key, value in (entry.extra or {}).items()
        if key not in hidden
    }


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
    try:
        limit = int(request.args.get("limit") or 100)
    except (TypeError, ValueError):
        limit = 100
    try:
        offset = int(request.args.get("offset") or 0)
    except (TypeError, ValueError):
        offset = 0
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    email = (request.args.get("email") or request.args.get("user") or "").strip()
    user_id = (request.args.get("user_id") or "").strip()
    ip = (request.args.get("ip") or "").strip()
    action = (request.args.get("action") or "").strip()
    endpoint = (request.args.get("endpoint") or "").strip()
    page = (request.args.get("page") or "").strip()
    method = (request.args.get("method") or "").strip()
    resource_type = (request.args.get("resource_type") or "").strip()
    category = (request.args.get("category") or "").strip().lower()
    range_key = (request.args.get("range") or "").strip().lower()
    if range_key not in RANGE_OPTIONS:
        range_key = ""
    explicit_start = _parse_dt(request.args.get("start"))
    start = explicit_start
    end = _parse_dt(request.args.get("end"), end=True)
    if range_key and not start:
        start = utc_now() - RANGE_OPTIONS[range_key][1]

    q = Q()
    if qtext:
        q = (
            Q(email__icontains=qtext)
            | Q(action__icontains=qtext)
            | Q(resource__icontains=qtext)
            | Q(ip__icontains=qtext)
            | Q(endpoint__icontains=qtext)
            | Q(resource_type__icontains=qtext)
            | Q(extra__page_path__icontains=qtext)
            | Q(extra__referrer__icontains=qtext)
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
    if page:
        q = q & (
            Q(endpoint__icontains=page)
            | Q(extra__page_path__icontains=page)
            | Q(extra__referrer__icontains=page)
        )
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
    current_args = request.args.to_dict(flat=True)

    def filter_url(**updates):
        args = dict(current_args)
        args.pop("offset", None)
        for key, value in updates.items():
            if value:
                args[key] = value
            else:
                args.pop(key, None)
        return url_for("admin_audit.audit_list", **args)

    for entry in logs:
        category_key, category_label = _audit_category(entry.action)
        page_context = _entry_page(entry)
        audit_rows.append(
            {
                "entry": entry,
                "category": category_key,
                "category_label": category_label,
                "label": ACTION_LABELS.get(entry.action, str(entry.action or "Activity").replace(".", " ").title()),
                "page": page_context,
                "resource_label": _resource_label(entry),
                "meta": _display_meta(entry),
                "user_filter_url": filter_url(email=entry.email) if entry.email else "",
                "page_filter_url": filter_url(page=page_context["filter"]) if page_context["filter"] else "",
                "action_filter_url": filter_url(action=entry.action) if entry.action else "",
            }
        )
    total = AuditLog.objects.count()
    filtered_total = AuditLog.objects(q).count()
    showing_start = offset + 1 if filtered_total and logs else 0
    showing_end = min(offset + len(logs), filtered_total)
    previous_url = ""
    next_url = ""
    if offset > 0:
        previous_args = dict(current_args)
        previous_args["offset"] = max(0, offset - limit)
        previous_args["limit"] = limit
        previous_url = url_for("admin_audit.audit_list", **previous_args)
    if offset + len(logs) < filtered_total:
        next_args = dict(current_args)
        next_args["offset"] = offset + limit
        next_args["limit"] = limit
        next_url = url_for("admin_audit.audit_list", **next_args)
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
        category_filters=[
            {"key": "", "label": "All", "url": filter_url(category="")},
            *[
                {"key": key, "label": value[0], "url": filter_url(category=key)}
                for key, value in AUDIT_CATEGORIES.items()
            ],
        ],
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
        page=page,
        method=method,
        resource_type=resource_type,
        range_key=range_key,
        range_options=[(key, label) for key, (label, _delta) in RANGE_OPTIONS.items()],
        start=local_input_value(explicit_start),
        end=local_input_value(end),
        alias=alias,
        uri=uri,
        ping_ok=ping_ok,
        selected_timezone=resolve_timezone_name(),
        showing_start=showing_start,
        showing_end=showing_end,
        previous_url=previous_url,
        next_url=next_url,
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

from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app
from flask_security import roles_required
from mongoengine.queryset.visitor import Q

from app.models.audit import AuditLog
from app.services.audit import log_action
from app.services.timezone_utils import local_input_value, parse_user_datetime, resolve_timezone_name
from mongoengine import get_connection

bp = Blueprint("admin_audit", __name__, url_prefix="/admin/audit")

def _parse_dt(value: str | None, end: bool = False) -> datetime | None:
    return parse_user_datetime(value, end_of_day=end)


@bp.get("/")
@roles_required("admin")
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
    if start:
        q = q & Q(ts__gte=start)
    if end:
        q = q & Q(ts__lte=end)

    logs = AuditLog.objects(q).order_by("-ts").skip(offset).limit(limit)
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
    except Exception as e:
        ping_ok = False
    return render_template(
        "admin/audit_list.html",
        logs=logs,
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
@roles_required("admin")
def audit_test():
    try:
        log_action("admin.audit.test", resource_type="system", resource="manual-test")
        flash("Inserted a test audit entry.", "success")
    except Exception as e:
        flash(f"Failed to write audit entry: {e}", "error")
    return redirect(url_for("admin_audit.audit_list"))

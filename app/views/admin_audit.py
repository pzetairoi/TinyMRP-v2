from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app
from flask_security import roles_required
from mongoengine.queryset.visitor import Q

from app.models.audit import AuditLog
from app.services.audit import log_action
from mongoengine import get_connection

bp = Blueprint("admin_audit", __name__, url_prefix="/admin/audit")


@bp.get("/")
@roles_required("admin")
def audit_list():
    qtext = (request.args.get("q") or "").strip().lower()
    limit = int(request.args.get("limit") or 200)
    limit = max(1, min(limit, 1000))

    q = Q()
    if qtext:
        # simple OR contains across email, action, resource, ip
        q = (
            Q(email__icontains=qtext)
            | Q(action__icontains=qtext)
            | Q(resource__icontains=qtext)
            | Q(ip__icontains=qtext)
        )

    logs = AuditLog.objects(q).order_by("-ts").limit(limit)
    total = AuditLog.objects.count()
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
    return render_template("admin/audit_list.html", logs=logs, q=qtext, limit=limit, total=total, alias=alias, uri=uri, ping_ok=ping_ok)


@bp.post("/test")
@roles_required("admin")
def audit_test():
    try:
        log_action("admin.audit.test", resource_type="system", resource="manual-test")
        flash("Inserted a test audit entry.", "success")
    except Exception as e:
        flash(f"Failed to write audit entry: {e}", "error")
    return redirect(url_for("admin_audit.audit_list"))

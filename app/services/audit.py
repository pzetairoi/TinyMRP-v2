from __future__ import annotations
from typing import Any, Dict, Optional

from flask import request, current_app, has_request_context
from flask_login import current_user

from app.models.audit import AuditLog


def _safe_str(v: Any, max_len: int = 500) -> str:
    try:
        s = str(v)
    except Exception:
        s = repr(v)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _client_ip() -> str:
    if not has_request_context():
        return ""
    try:
        xff = request.headers.get("X-Forwarded-For") or ""
        if xff:
            return xff.split(",")[0].strip()
        xri = request.headers.get("X-Real-IP") or ""
        if xri:
            return xri.strip()
        return request.remote_addr or ""
    except Exception:
        return ""


def log_action(action: str, resource_type: Optional[str] = None, resource: Optional[str] = None,
               meta: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Create an AuditLog document with contextual info.
    Safe to call even if DB unavailable (swallow exceptions).
    """
    try:
        user = None
        if has_request_context():
            try:
                user = current_user if getattr(current_user, "is_authenticated", False) else None
            except Exception:
                user = None
        roles = []
        if user is not None:
            try:
                roles = [getattr(r, "name", "") for r in (user.roles or []) if getattr(r, "name", None)]
            except Exception:
                roles = []
        # Try compute resource if not passed and PN/REV provided in query (only within request context)
        if resource is None and has_request_context():
            pn = (request.args.get("pn") or request.args.get("part_number") or request.args.get("root_pn") or "").strip()
            rev = request.args.get("rev")
            if pn:
                resource = f"{pn}:{(rev or '')}"
        # Build meta and context-safe headers
        _meta: Dict[str, Any] = dict(meta or {})
        if not has_request_context():
            _meta.setdefault("source", "cli")
        ip = ""
        ua = ""
        method = ""
        endpoint = ""
        if has_request_context():
            try:
                ip = _client_ip()
            except Exception:
                ip = ""
            try:
                ua = _safe_str(request.headers.get("User-Agent") or (request.user_agent.string if request.user_agent else ""))
            except Exception:
                ua = ""
            try:
                method = _safe_str(request.method or "")
            except Exception:
                method = ""
            try:
                endpoint = _safe_str(request.path or "")
            except Exception:
                endpoint = ""
            try:
                _meta.setdefault("endpoint_name", _safe_str(request.endpoint or ""))
                _meta.setdefault("referrer", _safe_str(request.referrer or ""))
                _meta.setdefault("request_id", _safe_str(request.headers.get("X-Request-Id") or ""))
            except Exception:
                pass
        entry = AuditLog(
            user_id=str(getattr(user, "id", "")) if user else "",
            email=(getattr(user, "email", "") or "") if user else "",
            roles=",".join(roles),
            action=action,
            resource_type=resource_type or "",
            resource=resource or "",
            ip=ip,
            ua=ua,
            method=method,
            endpoint=endpoint,
            extra=_meta,
        )
        entry.save()
        # Optional debug logging
        try:
            if current_app and current_app.config.get("AUDIT_LOG_DEBUG"):
                current_app.logger.info("audit saved action=%s id=%s resource=%s", action, getattr(entry, 'id', None), resource)
        except Exception:
            pass
        try:
            return str(getattr(entry, 'id', "")) or None
        except Exception:
            return None
    except Exception as e:
        try:
            current_app.logger.warning("audit log failed: %s", e)
        except Exception:
            pass
    return None

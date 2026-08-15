from __future__ import annotations
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit

from flask import request, current_app, g, has_request_context
from flask_login import current_user

from app.models.audit import AuditLog


_SAFE_PAGE_QUERY_KEYS = {"job", "rev", "tab"}


def _submitted_action_summary(endpoint_name: str) -> str:
    name = str(endpoint_name or "").rsplit(".", 1)[-1].lower()
    if any(token in name for token in ("delete", "purge", "remove")):
        return "Deleted or removed a record"
    if any(token in name for token in ("create", "new", "add")):
        return "Created a record"
    if any(token in name for token in ("edit", "update", "save", "prefs")):
        return "Saved changes"
    return "Submitted a page action"


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


def _safe_page_path(value: Any) -> str:
    """Return useful UI location context without retaining credentials or tokens."""
    try:
        parsed = urlsplit(_safe_str(value, 1000))
        path = parsed.path or ""
        if not path.startswith("/"):
            return ""
        # Public share URLs contain a bearer credential in the path. The page
        # type is useful to an auditor; the credential never is.
        if path.startswith("/share/part/") or path.startswith("/api/share/part/"):
            path = "/share/part/[redacted]"
        safe_query = [
            (key, val)
            for key, val in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() in _SAFE_PAGE_QUERY_KEYS
        ]
        return _safe_str(path + (f"?{urlencode(safe_query)}" if safe_query else ""), 500)
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
            if user is None:
                user = getattr(g, "api_user", None)
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
        else:
            # Under permission-test impersonation the acting identity is a test
            # user; record the administrator behind it so accountability for the
            # action is never lost.
            try:
                from app.services.impersonation import real_user

                behind = real_user()
                if behind is not None:
                    _meta.setdefault("impersonated_by", _safe_str(behind.email))
            except Exception:
                pass
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
                _meta.setdefault("referrer", _safe_page_path(request.referrer or ""))
                _meta.setdefault("request_id", _safe_str(request.headers.get("X-Request-Id") or ""))
                page_path = _safe_page_path(
                    request.headers.get("X-TinyMRP-Page")
                    or request.referrer
                    or request.url
                )
                if page_path:
                    _meta.setdefault("page_path", page_path)
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
        if has_request_context():
            try:
                g._tinymrp_audit_event_written = True
            except Exception:
                pass
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


def init_visible_page_audit(app) -> None:
    """Record rendered pages once, without treating their assets/API calls as visits."""
    if getattr(app, "_tinymrp_visible_page_audit", False):
        return
    app._tinymrp_visible_page_audit = True

    @app.after_request
    def _record_rendered_page(response):
        try:
            path = request.path or ""
            is_authenticated = bool(getattr(current_user, "is_authenticated", False))
            successful = 200 <= response.status_code < 400
            # Explicit action logs always win. This fallback covers traditional
            # server-rendered forms (jobs, orders, settings, etc.) whose POST
            # handler performed work but did not yet have a named audit event.
            # API endpoints are excluded: several use POST purely for table
            # searches, and deliberate API mutations already log explicitly.
            if (
                request.method in {"POST", "PUT", "PATCH", "DELETE"}
                and successful
                and is_authenticated
                and not path.startswith(("/api/", "/ui/", "/files/", "/extra/", "/share/"))
                and not getattr(g, "_tinymrp_audit_event_written", False)
            ):
                visible_page = _safe_page_path(
                    request.headers.get("X-TinyMRP-Page")
                    or request.referrer
                    or request.url
                )
                target = _safe_page_path(request.url)
                log_action(
                    "page.action",
                    resource_type="page",
                    resource=target,
                    meta={
                        "page_path": visible_page or target,
                        "summary": _submitted_action_summary(request.endpoint or ""),
                        "status": response.status_code,
                    },
                )
            is_visible_html = (
                request.method == "GET"
                and 200 <= response.status_code < 300
                and response.mimetype == "text/html"
            )
            # React navigation is recorded by the route tracker after it has
            # resolved the actual client-side URL. Recording the shell here as
            # well would create two visits for one page load.
            if not is_visible_html or path.startswith(("/ui/", "/share/")):
                return response
            if not is_authenticated:
                return response
            page_path = _safe_page_path(request.url)
            if page_path:
                log_action(
                    "page.view",
                    resource_type="page",
                    resource=page_path,
                    meta={"page_path": page_path},
                )
        except Exception:
            # Auditing must never turn a successfully rendered page into an
            # error response.
            pass
        return response

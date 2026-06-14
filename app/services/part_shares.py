from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Any

from flask import current_app, has_request_context, request, url_for

from app.models.audit import AuditLog
from app.models.part_share import PartShareLink
from app.services.part_norm import clean_rev


def _secret() -> bytes:
    raw = (
        current_app.config.get("SECRET_KEY")
        or current_app.config.get("SECURITY_PASSWORD_SALT")
        or "tinymrp-part-share"
    )
    return str(raw).encode("utf-8")


def normalize_share_revision(value: object | None) -> str:
    return clean_rev(value)


def hash_part_share_token(token: str) -> str:
    return hmac.new(_secret(), str(token or "").encode("utf-8"), hashlib.sha256).hexdigest()


def create_part_share(
    part_number: str,
    revision: str | None,
    *,
    created_by=None,
    expires_in_days: int = 30,
) -> tuple[PartShareLink, str]:
    raw_token = secrets.token_urlsafe(32)
    share = PartShareLink(
        part_number=str(part_number or "").strip(),
        revision=normalize_share_revision(revision),
        token_hash=hash_part_share_token(raw_token),
        token_prefix=raw_token[:8],
        created_by_user_id=str(getattr(created_by, "id", "") or ""),
        created_by_email=str(getattr(created_by, "email", "") or ""),
    )
    if expires_in_days > 0:
        share.expires_at = datetime.utcnow() + timedelta(days=int(expires_in_days))
    share.save()
    return share, raw_token


def resolve_part_share(share_id: str, raw_token: str) -> tuple[PartShareLink | None, str]:
    share = PartShareLink.objects(id=share_id).first()
    if not share:
        return None, "not_found"
    expected = hash_part_share_token(raw_token)
    if not hmac.compare_digest(share.token_hash or "", expected):
        return None, "not_found"
    if share.revoked_at:
        return share, "revoked"
    expires_at = getattr(share, "expires_at", None)
    if expires_at and expires_at <= datetime.utcnow():
        return share, "expired"
    return share, "ok"


def share_status(share: PartShareLink) -> str:
    if getattr(share, "revoked_at", None):
        return "revoked"
    expires_at = getattr(share, "expires_at", None)
    if expires_at and expires_at <= datetime.utcnow():
        return "expired"
    return "active"


def public_part_share_url(share: PartShareLink, raw_token: str) -> str:
    return url_for(
        "part_shares.public_part_share_ui",
        share_id=str(share.id),
        token=raw_token,
        _external=True,
    )


def share_dict(share: PartShareLink) -> dict[str, Any]:
    return {
        "id": str(share.id),
        "part_number": share.part_number or "",
        "revision": share.revision or "",
        "token_prefix": share.token_prefix or "",
        "status": share_status(share),
        "created_at": share.created_at.isoformat() if share.created_at else None,
        "created_by_email": share.created_by_email or "",
        "expires_at": share.expires_at.isoformat() if share.expires_at else None,
        "revoked_at": share.revoked_at.isoformat() if share.revoked_at else None,
        "revoked_by_email": share.revoked_by_email or "",
        "last_accessed_at": share.last_accessed_at.isoformat() if share.last_accessed_at else None,
        "access_count": int(share.access_count or 0),
    }


def _safe_str(value: object, max_len: int = 500) -> str:
    text = str(value or "")
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def _client_ip() -> str:
    if not has_request_context():
        return ""
    xff = request.headers.get("X-Forwarded-For") or ""
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("X-Real-IP") or ""
    if xri:
        return xri.strip()
    return request.remote_addr or ""


def record_part_share_access(share: PartShareLink, *, kind: str) -> None:
    now = datetime.utcnow()
    ip = _client_ip()
    ua = _safe_str(request.headers.get("User-Agent") or "") if has_request_context() else ""
    share.update(
        inc__access_count=1,
        set__last_accessed_at=now,
        set__last_access_ip=ip,
        set__last_access_ua=ua,
    )
    try:
        AuditLog(
            action="part.share.access",
            resource_type="part_share",
            resource=f"{share.part_number}:{share.revision or ''}",
            ip=ip,
            ua=ua,
            method=_safe_str(request.method or "") if has_request_context() else "",
            endpoint=f"/share/part/{share.id}/<redacted>",
            extra={
                "share_id": str(share.id),
                "token_prefix": share.token_prefix or "",
                "kind": kind,
            },
        ).save()
    except Exception:
        pass


def public_response_headers(resp):
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp

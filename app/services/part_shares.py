from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from flask import current_app, g, has_request_context, request, url_for

from app.models.audit import AuditLog
from app.models.artifact import PartFile
from app.models.bom import BOMLink
from app.models.extra_file import PartExtraFile
from app.models.part import Part
from app.models.part_share import PartShareLink
from app.services.file_security import (
    FileSecurityError,
    resolve_associated_path,
    resolve_managed_path,
)
from app.services.authorization import part_is_released
from app.services.part_norm import clean_rev
from app.services.timezone_utils import format_display_ts, local_input_value, utc_iso, utc_now


PUBLIC_MANAGED_FILE_GROUPS = frozenset(
    {"png", "pdf", "dxf", "step", "edr", "3mf", "ply", "stl", "datasheet"}
)
PUBLIC_ASSOCIATED_EXTENSIONS = frozenset(
    {
        "pdf",
        "png",
        "jpg",
        "jpeg",
        "dxf",
        "dwg",
        "step",
        "stp",
        "iges",
        "igs",
        "stl",
        "3mf",
        "ply",
        "edr",
        "txt",
        "csv",
        "xlsx",
        "docx",
    }
)
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
_INTERNAL_FILE_TERMS = ("internal", "private", "review", "markup", "audit")


@dataclass(frozen=True)
class PublicPartShareScope:
    share: PartShareLink
    root: tuple[str, str]
    allowed_parts: frozenset[tuple[str, str]]
    managed_file_groups: frozenset[str]

    def allows_part(self, part_number: Any, revision: Any) -> bool:
        key = (
            str(part_number or "").strip().casefold(),
            normalize_share_revision(revision).casefold(),
        )
        return key in self.allowed_parts

    def allows_managed_file(self, file_record: PartFile) -> bool:
        group = str(getattr(file_record, "ext_group", "") or "").strip().lower()
        return bool(
            group in self.managed_file_groups
            and self.allows_part(
                getattr(file_record, "part_number", ""),
                getattr(file_record, "revision", ""),
            )
        )

    def allows_associated_file(self, file_record: PartExtraFile) -> bool:
        name = str(getattr(file_record, "original_name", "") or "").strip()
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        source = str(getattr(file_record, "source", "") or "").strip().lower()
        label = str(getattr(file_record, "label", "") or "").strip().lower()
        return bool(
            self.allows_part(
                getattr(file_record, "part_number", ""),
                getattr(file_record, "revision", ""),
            )
            and extension in PUBLIC_ASSOCIATED_EXTENSIONS
            and source not in _INTERNAL_FILE_TERMS
            and not any(term in label for term in _INTERNAL_FILE_TERMS)
        )


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
    allow_children: bool = False,
    allow_docpacks: bool = False,
    allow_attributes: bool = False,
    allow_unreleased: bool = False,
) -> tuple[PartShareLink, str]:
    raw_token = secrets.token_urlsafe(32)
    share = PartShareLink(
        part_number=str(part_number or "").strip(),
        revision=normalize_share_revision(revision),
        token_hash=hash_part_share_token(raw_token),
        token_prefix=raw_token[:8],
        allow_children=bool(allow_children),
        allow_docpacks=bool(allow_docpacks),
        allow_attributes=bool(allow_attributes),
        allow_unreleased=bool(allow_unreleased),
        enabled=True,
        created_by_user_id=str(getattr(created_by, "id", "") or ""),
        created_by_email=str(getattr(created_by, "email", "") or ""),
    )
    if expires_in_days > 0:
        share.expires_at = utc_now() + timedelta(days=int(expires_in_days))
    share.save()
    return share, raw_token


def resolve_part_share(share_id: str, raw_token: str) -> tuple[PartShareLink | None, str]:
    if not _TOKEN_RE.fullmatch(str(raw_token or "")):
        return None, "not_found"
    try:
        share = PartShareLink.objects(id=share_id).first()
    except Exception:
        return None, "unavailable"
    if not share:
        return None, "not_found"
    try:
        expected = hash_part_share_token(raw_token)
    except Exception:
        return None, "unavailable"
    if not hmac.compare_digest(share.token_hash or "", expected):
        return None, "not_found"
    if not _share_has_stored_revision(share):
        return share, "legacy_scope"
    if not bool(getattr(share, "enabled", True)):
        return share, "disabled"
    if share.revoked_at:
        return share, "revoked"
    expires_at = getattr(share, "expires_at", None)
    if expires_at and expires_at <= utc_now():
        return share, "expired"
    return share, "ok"


def _share_has_stored_revision(share: PartShareLink) -> bool:
    """Distinguish an exact blank revision from a legacy missing field."""

    try:
        raw = PartShareLink._get_collection().find_one(
            {"_id": share.id},
            {"revision": 1},
        )
        return bool(raw is not None and "revision" in raw)
    except Exception:
        return False


def _build_public_scope(share: PartShareLink) -> PublicPartShareScope:
    root = (
        str(share.part_number or "").strip(),
        normalize_share_revision(share.revision),
    )
    root_part = Part.objects(
        part_number__iexact=root[0],
        revision__iexact=root[1],
    ).first()
    if (
        not root[0]
        or not root_part
        or (
            not bool(getattr(share, "allow_unreleased", False))
            and not part_is_released(root_part)
        )
    ):
        raise ValueError("share unavailable")

    allowed: set[tuple[str, str]] = {
        (root[0].casefold(), root[1].casefold())
    }
    if bool(getattr(share, "allow_children", False)):
        queue = [root]
        while queue:
            parent_pn, parent_rev = queue.pop(0)
            for link in BOMLink.objects(
                parent_pn=parent_pn,
                parent_rev=parent_rev,
            ):
                child_pn = str(getattr(link, "child_pn", "") or "").strip()
                child_rev = normalize_share_revision(
                    getattr(link, "child_rev", "")
                )
                if not child_pn:
                    continue
                normalized = (child_pn.casefold(), child_rev.casefold())
                if normalized in allowed:
                    continue
                child_part = Part.objects(
                    part_number__iexact=child_pn,
                    revision__iexact=child_rev,
                ).first()
                if (
                    not child_part
                    or (
                        not bool(
                            getattr(share, "allow_unreleased", False)
                        )
                        and not part_is_released(child_part)
                    )
                ):
                    raise ValueError("share unavailable")
                allowed.add(normalized)
                queue.append((child_pn, child_rev))
    return PublicPartShareScope(
        share=share,
        root=root,
        allowed_parts=frozenset(allowed),
        managed_file_groups=PUBLIC_MANAGED_FILE_GROUPS,
    )


def resolve_public_part_share_scope(
    share_id: str,
    raw_token: str,
) -> tuple[PublicPartShareScope | None, str]:
    """Resolve one token-bound public scope, cached only for this request."""

    cache_key = (
        f"{share_id}:"
        f"{hashlib.sha256(str(raw_token or '').encode()).hexdigest()}"
    )
    if has_request_context():
        cached = getattr(g, "_public_part_share_scopes", {}).get(cache_key)
        if cached is not None:
            return cached
    share, status = resolve_part_share(share_id, raw_token)
    if not share or status != "ok":
        result = (None, status)
    else:
        try:
            result = (_build_public_scope(share), "ok")
        except Exception:
            result = (None, "unavailable")
    if has_request_context():
        cache = getattr(g, "_public_part_share_scopes", None)
        if cache is None:
            cache = {}
            g._public_part_share_scopes = cache
        cache[cache_key] = result
    return result


def public_managed_file_path(
    scope: PublicPartShareScope,
    file_record: PartFile,
    *,
    kind: str = "file",
    must_exist: bool = True,
):
    if not scope.allows_managed_file(file_record):
        raise FileSecurityError("file unavailable")
    return resolve_managed_path(
        file_record,
        kind=kind,
        must_exist=must_exist,
    )


def public_associated_file_path(
    scope: PublicPartShareScope,
    file_record: PartExtraFile,
):
    if not scope.allows_associated_file(file_record):
        raise FileSecurityError("file unavailable")
    return resolve_associated_path(file_record, must_exist=True)


def share_status(share: PartShareLink) -> str:
    if not bool(getattr(share, "enabled", True)):
        return "disabled"
    if getattr(share, "revoked_at", None):
        return "revoked"
    expires_at = getattr(share, "expires_at", None)
    if expires_at and expires_at <= utc_now():
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
        "allow_children": bool(getattr(share, "allow_children", False)),
        "allow_docpacks": bool(getattr(share, "allow_docpacks", False)),
        "allow_attributes": bool(getattr(share, "allow_attributes", False)),
        "enabled": bool(getattr(share, "enabled", True)),
        "status": share_status(share),
        "created_at": utc_iso(share.created_at),
        "created_at_display": format_display_ts(share.created_at, fmt="%Y-%m-%d %H:%M:%S %Z") or None,
        "created_at_local": local_input_value(share.created_at) or None,
        "created_by_email": share.created_by_email or "",
        "expires_at": utc_iso(share.expires_at),
        "expires_at_display": format_display_ts(share.expires_at, fmt="%Y-%m-%d %H:%M:%S %Z") or None,
        "expires_at_local": local_input_value(share.expires_at) or None,
        "revoked_at": utc_iso(share.revoked_at),
        "revoked_at_display": format_display_ts(share.revoked_at, fmt="%Y-%m-%d %H:%M:%S %Z") or None,
        "revoked_at_local": local_input_value(share.revoked_at) or None,
        "revoked_by_email": share.revoked_by_email or "",
        "last_accessed_at": utc_iso(share.last_accessed_at),
        "last_accessed_at_display": format_display_ts(share.last_accessed_at, fmt="%Y-%m-%d %H:%M:%S %Z") or None,
        "last_accessed_at_local": local_input_value(share.last_accessed_at) or None,
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
    now = utc_now()
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


def migrate_legacy_part_shares(*, apply: bool = False) -> dict[str, Any]:
    """Backfill only legacy shares whose part number has one exact revision."""

    report: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "migrated": [],
        "unambiguous": [],
        "ambiguous": [],
    }
    collection = PartShareLink._get_collection()
    for raw in collection.find(
        {"revision": {"$exists": False}},
        {"part_number": 1},
    ):
        share_id = str(raw.get("_id"))
        pn = str(raw.get("part_number") or "").strip()
        revisions = sorted(
            {
                normalize_share_revision(part.revision)
                for part in Part.objects(part_number__iexact=pn).only("revision")
            }
        )
        if pn and len(revisions) == 1:
            report["unambiguous"].append(share_id)
            if apply:
                collection.update_one(
                    {"_id": raw["_id"], "revision": {"$exists": False}},
                    {"$set": {"revision": revisions[0]}},
                )
                report["migrated"].append(share_id)
        else:
            report["ambiguous"].append(share_id)
    return report

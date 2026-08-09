# app/services/diagnostics.py — environment and storage diagnostics for admins.
"""Configuration and filesystem checks for troubleshooting.

Everything here is read-only and redaction-first: values are only ever
reported after passing through :func:`_redact`, because the same page shows
connection strings and secret keys that must never be echoed back verbatim.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlsplit, urlunsplit

from flask import current_app

from app.models.artifact import PartFile
from app.services.app_settings import resolve_file_sources

# Substrings that mark a config key as sensitive regardless of where it came
# from, so a newly added secret is redacted by default rather than leaked.
_SECRET_HINTS = ("secret", "password", "token", "salt", "key", "credential", "auth")

# Configuration that actually influences file discovery, storage and uploads.
_TRACKED_KEYS = (
    "FILES_LOCAL_ROOT",
    "FILE_ROOT_LOCAL",
    "FILES_URL_PREFIX",
    "FILE_ROOT_HTTP",
    "FILES_UPSTREAM_BASE",
    "FILES_UPSTREAM_ALLOWED_HOSTS",
    "FILES_PROXY_MAX_BYTES",
    "FILE_HASH_MAX_BYTES",
    "EXTRA_FILES_ALLOWED",
    "UPLOAD_PACK_MAX_ZIP_MB",
    "UPLOAD_PACK_MAX_FILE_MB",
    "UPLOAD_PACK_MAX_FILES",
    "MONGO_URI",
    "ENV_FILE",
    "TINYMRP_ALLOWED_ORIGINS",
    "TINYMRP_CORS_CREDENTIALS",
    "ALLOW_PERMISSION_TEST_DATA",
    "SECRET_KEY",
    "SECURITY_PASSWORD_SALT",
)

# Deliverable folders discovery expects under each storage root.
_EXPECTED_GROUPS = ("png", "pdf", "dxf", "step", "edr", "3mf", "ply", "stl", "datasheet")


def _is_secret(key: str) -> bool:
    lowered = key.casefold()
    return any(hint in lowered for hint in _SECRET_HINTS)


def _redact(key: str, value: Any) -> str:
    """Render a config value safely.

    Secrets collapse to a set/unset marker with a length hint, and URIs keep
    their host and database while dropping any embedded credentials, so the
    page stays useful for diagnosis without disclosing anything usable.
    """
    text = "" if value is None else str(value)
    if not text:
        return ""
    if _is_secret(key):
        return f"set ({len(text)} chars)"
    if "://" in text:
        try:
            parts = urlsplit(text)
            if parts.password or parts.username:
                host = parts.hostname or ""
                if parts.port:
                    host = f"{host}:{parts.port}"
                netloc = f"***@{host}"
                return urlunsplit((parts.scheme, netloc, parts.path, "", ""))
        except ValueError:
            return "set (unparseable URI)"
    return text


def config_rows() -> List[Dict[str, str]]:
    """Tracked configuration with provenance, redacted for display."""
    rows = []
    for key in _TRACKED_KEYS:
        value = current_app.config.get(key, os.environ.get(key))
        rows.append(
            {
                "key": key,
                "value": _redact(key, value),
                "source": "environment" if key in os.environ else ("config" if value is not None else ""),
                "status": "ok" if value not in (None, "") else "unset",
                "secret": _is_secret(key),
            }
        )
    return rows


def _directory_report(root: Path) -> Dict[str, Any]:
    groups = []
    for name in _EXPECTED_GROUPS:
        directory = root / name
        try:
            exists = directory.is_dir()
            count = sum(1 for entry in directory.iterdir() if entry.is_file()) if exists else 0
        except OSError:
            exists, count = False, 0
        groups.append({"name": name, "exists": exists, "files": count})
    return {"groups": groups, "files": sum(item["files"] for item in groups)}


def storage_rows() -> List[Dict[str, Any]]:
    """Per-source reachability, capacity and deliverable folder inventory."""
    rows = []
    for source in resolve_file_sources():
        raw_root = str(source.get("local_root") or "").strip()
        root = Path(raw_root) if raw_root else None
        row: Dict[str, Any] = {
            "id": source.get("id") or "",
            "label": source.get("label") or "",
            "root": raw_root,
            "url_prefix": source.get("url_prefix") or "",
            "priority": source.get("priority"),
            "use_for_approved": bool(source.get("use_for_approved", True)),
            "use_for_unapproved": bool(source.get("use_for_unapproved", True)),
            "exists": False,
            "writable": False,
            "groups": [],
            "files": 0,
            "free_h": "",
            "total_h": "",
            "error": "",
        }
        if root is None:
            row["error"] = "No local root configured."
            rows.append(row)
            continue
        try:
            row["exists"] = root.is_dir()
        except OSError as exc:
            row["error"] = str(exc)
        if row["exists"]:
            row["writable"] = os.access(root, os.W_OK)
            report = _directory_report(root)
            row.update(report)
            try:
                usage = shutil.disk_usage(root)
                row["free_h"] = _format_bytes(usage.free)
                row["total_h"] = _format_bytes(usage.total)
            except OSError:
                pass
        elif not row["error"]:
            row["error"] = "Directory is not reachable from the server."
        rows.append(row)
    return rows


def _format_bytes(value: float) -> str:
    step = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if step < 1024 or unit == "TB":
            return f"{step:.1f} {unit}" if unit != "B" else f"{int(step)} B"
        step /= 1024
    return f"{step:.1f} TB"


def record_health(sample: int = 400) -> Dict[str, Any]:
    """Compare file records against what is actually on disk.

    A capped sample keeps the page responsive on large estates while still
    surfacing the common failure: records pointing at files that moved or were
    deleted outside the app.
    """
    total = PartFile.objects.count()
    missing: List[Dict[str, str]] = []
    checked = 0
    for row in PartFile.objects.only("part_number", "revision", "path", "ext_group").limit(sample):
        path = str(getattr(row, "path", "") or "")
        if not path:
            continue
        checked += 1
        if not os.path.isfile(path):
            missing.append(
                {
                    "part_number": row.part_number,
                    "revision": row.revision or "",
                    "ext_group": row.ext_group or "",
                    "path": path,
                }
            )
    return {
        "total": total,
        "checked": checked,
        "missing": missing[:25],
        "missing_count": len(missing),
        "truncated": total > checked,
    }


def environment_report() -> Dict[str, Any]:
    """Everything the diagnostics panel renders."""
    return {
        "config": config_rows(),
        "storage": storage_rows(),
        "records": record_health(),
    }

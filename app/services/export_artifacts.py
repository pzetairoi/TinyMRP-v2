"""Short-lived, owner-bound storage for generated export downloads."""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

from app.services.timezone_utils import utc_iso, utc_now


_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
_RETENTION = timedelta(hours=1)


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError):
        return None


def _root() -> Path:
    root = Path(tempfile.gettempdir()) / "tinymrp_protected_exports"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root.resolve()


def _paths(token: str) -> tuple[Path, Path]:
    if not _TOKEN_RE.fullmatch(str(token or "")):
        raise ValueError("export unavailable")
    root = _root()
    data = (root / f"{token}.bin").resolve()
    metadata = (root / f"{token}.json").resolve()
    if data.parent != root or metadata.parent != root:
        raise ValueError("export unavailable")
    return data, metadata


def cleanup_export_artifacts() -> None:
    cutoff = utc_now() - _RETENTION
    root = _root()
    for metadata_path in root.glob("*.json"):
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            created_at = payload.get("created_at")
            created = _parse_timestamp(created_at)
            if created and created >= cutoff:
                continue
            token = metadata_path.stem
            data_path, _ = _paths(token)
            data_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
        except Exception:
            try:
                data_path, _ = _paths(metadata_path.stem)
                data_path.unlink(missing_ok=True)
                metadata_path.unlink(missing_ok=True)
            except Exception:
                pass
            continue


def store_export_artifact(
    payload: bytes,
    *,
    owner_id: Any,
    display_name: str,
    pairs: list[tuple[str, str]],
    file_groups: list[str] | None,
    include_markups: bool = False,
    require_bom: bool = True,
) -> str:
    cleanup_export_artifacts()
    token = secrets.token_urlsafe(32)
    data_path, metadata_path = _paths(token)
    data_path.write_bytes(payload)
    metadata = {
        "owner_id": str(owner_id or ""),
        "display_name": os.path.basename(str(display_name or "export.zip")),
        "pairs": [[str(pn), str(rev)] for pn, rev in pairs],
        "file_groups": list(file_groups) if file_groups is not None else None,
        "include_markups": bool(include_markups),
        "require_bom": bool(require_bom),
        "created_at": utc_iso(utc_now()),
    }
    metadata_path.write_text(
        json.dumps(metadata, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    try:
        os.chmod(data_path, 0o600)
        os.chmod(metadata_path, 0o600)
    except OSError:
        pass
    return token


def load_export_artifact(
    token: str,
    *,
    owner_id: Any,
) -> tuple[Path, dict[str, Any]]:
    data_path, metadata_path = _paths(token)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        created = _parse_timestamp(metadata.get("created_at"))
    except Exception as exc:
        raise ValueError("export unavailable") from exc
    if (
        str(metadata.get("owner_id") or "") != str(owner_id or "")
        or created is None
        or created < utc_now() - _RETENTION
        or not data_path.is_file()
    ):
        if created is None or created < utc_now() - _RETENTION:
            data_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
        raise ValueError("export unavailable")
    return data_path, metadata

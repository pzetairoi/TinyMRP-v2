"""Retention for the upload packs the add-in leaves in <deliverables>/bom.

Every *Create upload pack* writes a timestamped ZIP there. Nothing reads it
again once the import has run - not the server, and not the sample-dataset
builder, which skips the folder as working material - so they accumulate for as
long as the instance has been in service. One estate had 1,258 of them, 281 MB,
going back eighteen months.

Old packs are MOVED to bom/archive, never deleted. They are the only record of
what a pack contained, so a sweep that reclaimed space by destroying them would
trade a tidy folder for a lost audit trail. Tidying the working folder is the
whole job; the disk cost is unchanged and deliberate.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import timedelta
from pathlib import Path

from flask import current_app, has_app_context

from app.services.timezone_utils import utc_now

logger = logging.getLogger(__name__)

ARCHIVE_DIRNAME = "archive"
_SWEEP_INTERVAL = timedelta(hours=24)


def _bom_root() -> Path | None:
    if not has_app_context():
        return None
    root = str(
        current_app.config.get("FILE_ROOT_LOCAL")
        or current_app.config.get("FILES_LOCAL_ROOT")
        or ""
    ).strip()
    if not root:
        return None
    bom = Path(root) / "bom"
    return bom if bom.is_dir() else None


def _archive_target(archive_dir: Path, source: Path) -> Path:
    """A free name in the archive, so a repeat filename never overwrites one."""
    candidate = archive_dir / source.name
    if not candidate.exists():
        return candidate
    stem, suffix = source.stem, source.suffix
    for index in range(1, 1000):
        candidate = archive_dir / f"{stem}.{index}{suffix}"
        if not candidate.exists():
            return candidate
    return archive_dir / f"{stem}.{utc_now().strftime('%Y%m%d%H%M%S%f')}{suffix}"


def archive_old_bom_packs(retention_days: int) -> dict[str, int]:
    """Move packs older than the window into bom/archive. Never deletes."""
    result = {"archived": 0, "failed": 0, "scanned": 0}
    if retention_days <= 0:
        return result
    bom = _bom_root()
    if bom is None:
        return result
    cutoff = (utc_now() - timedelta(days=retention_days)).timestamp()
    archive_dir = bom / ARCHIVE_DIRNAME
    for entry in bom.iterdir():
        # Only loose ZIPs directly in bom/. The archive is a directory, so it is
        # skipped by is_file() and can never be swept into itself.
        if not entry.is_file() or entry.suffix.casefold() != ".zip":
            continue
        result["scanned"] += 1
        try:
            if entry.stat().st_mtime >= cutoff:
                continue
        except OSError:
            result["failed"] += 1
            continue
        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
            target = _archive_target(archive_dir, entry)
            # Same filesystem in every deployment, but a bind mount could make
            # bom/ and its archive differ; move() handles both.
            shutil.move(str(entry), str(target))
            result["archived"] += 1
        except (OSError, shutil.Error):
            # One unreadable pack must not stop the sweep, and losing a pack is
            # worse than leaving it in place - so this is reported, not retried.
            result["failed"] += 1
            logger.warning("could not archive upload pack %s", entry, exc_info=True)
    if result["archived"] or result["failed"]:
        logger.info(
            "upload pack sweep: archived %s, failed %s, of %s scanned",
            result["archived"],
            result["failed"],
            result["scanned"],
        )
    return result


def sweep_bom_packs_if_due(*, force: bool = False) -> dict[str, int]:
    """Archive old packs at most once a day.

    Called after an import rather than from a scheduler. Packs only appear
    because someone imported one, so import traffic is exactly the signal that
    there is anything to tidy - and it needs no timer installed per server,
    which keeps container and Windows instances behaving the same.
    """
    from app.services.app_settings import get_app_settings

    skipped = {"archived": 0, "failed": 0, "scanned": 0, "ran": 0}
    try:
        settings = get_app_settings()
        if settings is None:
            return skipped
        retention = int(getattr(settings, "bom_pack_retention_days", 7) or 0)
        if retention <= 0:
            return skipped
        last = getattr(settings, "bom_pack_swept_at", None)
        if not force and last and (utc_now() - last) < _SWEEP_INTERVAL:
            return skipped
        # Stamped before the work, not after: a sweep that dies half way must
        # not be retried by every import for the rest of the day.
        settings.update(set__bom_pack_swept_at=utc_now())
        outcome = archive_old_bom_packs(retention)
        outcome["ran"] = 1
        return outcome
    except Exception:
        # Housekeeping must never fail the import that triggered it.
        logger.warning("upload pack sweep failed", exc_info=True)
        return skipped

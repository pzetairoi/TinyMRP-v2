"""Read-only view of this instance's backups, for the admin dashboard.

DELIBERATELY READ ONLY. The backups directory is bind-mounted read-only into
the container, and nothing here writes, deletes or triggers a backup. Deleting
a backup stays a deliberate act on the host, next to restore-instance.sh, which
is the only thing that can actually use one.

The dashboard exists to answer three questions an operator should not have to
SSH for: is a backup happening at all, how much space is it taking, and how
much room is left. A production instance was found running with no scheduled
backup whatsoever and nobody noticed, because nothing surfaced it.

Every function fails soft and returns "unavailable" rather than raising: an
unmounted or missing directory is a normal state on a hand-made instance, and
an admin page must not 500 because of it.
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Where the deploy script mounts the instance's backups. Overridable mainly so
# tests do not need a container.
BACKUPS_DIR = os.getenv("TINYMRP_BACKUPS_DIR", "/data/backups")

# An archive whose UNCOMPRESSED size is below this holds no documents.
# mongodump writes a valid, tiny archive when it cannot authenticate and still
# exits 0 - that is how four consecutive backups here were silently empty for
# weeks, past a guard that checked the file was non-empty.
#
# It must be the uncompressed size. The compressed size is worthless as a
# signal: a dump of highly repetitive data compresses to a few hundred bytes
# and would be indistinguishable from an empty one. backup-instance.sh makes
# the same check with `gzip -dc | wc -c`.
_MIN_USEFUL_ARCHIVE_BYTES = 1024


def _gzip_uncompressed_size(path: str) -> int:
    """Uncompressed size from the gzip trailer, without decompressing.

    The last four bytes of a gzip member are ISIZE, the uncompressed length
    modulo 2**32. Reading them is O(1); actually decompressing a multi-gigabyte
    archive on every dashboard render is not.

    The modulo means a member over 4 GiB reports its remainder. That only ever
    makes a huge archive look small, i.e. flags it for attention rather than
    hiding a problem, so it fails in the safe direction.
    """
    try:
        with open(path, "rb") as fh:
            fh.seek(-4, os.SEEK_END)
            return int.from_bytes(fh.read(4), "little")
    except OSError:
        return 0


def _dir_size_bytes(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


# The deliverables archive may live on another drive entirely, in which case the
# backup folder holds only a pointer. Reading it is how the dashboard can say
# what a backup actually contains and where it went.
def _manifest(path: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for name in ("manifest.env", "deliverables.location"):
        candidate = os.path.join(path, name)
        try:
            with open(candidate, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    key, sep, value = line.strip().partition("=")
                    if sep and key:
                        out[key.strip().lower()] = value.strip()
        except OSError:
            continue
    return out


def _kind_of(path: str, manifest: Dict[str, str]) -> str:
    """"full" carries the deliverables, "database" does not.

    Classified the same way the host script classifies it for retention, so the
    dashboard and the pruning rules can never disagree about what a backup is.
    """
    if os.path.isfile(os.path.join(path, "deliverables.tar.gz")):
        return "full"
    if manifest.get("deliverables_archive"):
        return "full"
    return "database"


def backups_available() -> bool:
    """Whether this instance can see its backups at all."""
    try:
        return os.path.isdir(BACKUPS_DIR)
    except OSError:
        return False


def list_backups(limit: int = 50) -> List[Dict[str, Any]]:
    """Newest first. Empty list when unavailable - never raises."""
    if not backups_available():
        return []

    rows: List[Dict[str, Any]] = []
    try:
        names = sorted(os.listdir(BACKUPS_DIR), reverse=True)
    except OSError:
        return []

    for name in names[: max(0, int(limit))]:
        path = os.path.join(BACKUPS_DIR, name)
        if not os.path.isdir(path):
            continue
        archive = os.path.join(path, "mongo.archive.gz")
        archive_bytes = _gzip_uncompressed_size(archive) if os.path.isfile(archive) else 0
        created: Optional[datetime] = None
        try:
            created = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
        except OSError:
            created = None
        manifest = _manifest(path)
        kind = _kind_of(path, manifest)
        elsewhere = manifest.get("deliverables_archive") or ""
        # The folder size does not include an archive kept on another drive, so
        # report that separately rather than understating what the backup costs.
        try:
            deliverables_bytes = int(manifest.get("deliverables_bytes") or 0)
        except (TypeError, ValueError):
            deliverables_bytes = 0
        rows.append(
            {
                "name": name,
                "size_bytes": _dir_size_bytes(path),
                "created_at": created,
                "kind": kind,
                "deliverables_bytes": deliverables_bytes,
                # Absolute host path when the archive is on another drive, empty
                # when it sits in the folder or the backup has none.
                "deliverables_elsewhere": elsewhere,
                # Reported, not enforced. A operator seeing "looks empty" has
                # the one piece of information that matters about a backup.
                "looks_empty": archive_bytes < _MIN_USEFUL_ARCHIVE_BYTES,
            }
        )
    return rows


def disk_usage() -> Optional[Dict[str, int]]:
    """Total/used/free for the filesystem holding the backups.

    Falls back to the deliverables mount, which lives on the same host
    filesystem, so the number is still the operator's real headroom even on an
    instance predating the backups mount.
    """
    for path in (BACKUPS_DIR, "/data/deliverables", "/"):
        try:
            if not os.path.isdir(path):
                continue
            usage = shutil.disk_usage(path)
            return {
                "total_bytes": int(usage.total),
                "used_bytes": int(usage.used),
                "free_bytes": int(usage.free),
            }
        except OSError:
            continue
    return None


_FREQUENCY_LABELS = {
    "weekly": "every week",
    "fortnightly": "every two weeks",
    "monthly": "every month",
}


def effective_policy() -> Dict[str, Any]:
    """What the next backup will actually do, and what it will cost.

    The backup runs on the host and this app cannot start one, so the panel's
    job is to make the standing policy legible: what is included, how often,
    where it goes, and what that costs. Everything here is read-only.
    """
    from app.services.app_settings import get_app_settings

    settings = get_app_settings(create=False)
    include = bool(getattr(settings, "backup_include_deliverables", False)) if settings else False
    frequency = str(getattr(settings, "backup_deliverables_frequency", "") or "monthly") if settings else "monthly"
    destination = str(getattr(settings, "backup_deliverables_dest", "") or "") if settings else ""
    deliverables_bytes = 0
    if include:
        # What one deliverables archive would cost, before compression. The
        # honest number for "should I turn this on?".
        deliverables_bytes = _dir_size_bytes("/data/deliverables")
    return {
        "database_included": True,
        "deliverables_included": include,
        "deliverables_frequency": frequency,
        "deliverables_frequency_label": _FREQUENCY_LABELS.get(frequency, frequency),
        "deliverables_destination": destination,
        # Empty destination means the archive lands beside the database backup,
        # which is the same disk as the data it protects.
        "deliverables_offsite": bool(destination),
        "deliverables_estimated_bytes": deliverables_bytes,
        "retention_days": getattr(settings, "backup_retention_days", None) if settings else None,
        "keep_full": getattr(settings, "backup_keep_full", None) if settings else None,
        "keep_db": getattr(settings, "backup_keep_db", None) if settings else None,
    }


def summary(limit: int = 50) -> Dict[str, Any]:
    """Everything the dashboard needs, in one call."""
    rows = list_backups(limit=limit)
    try:
        policy = effective_policy()
    except Exception:
        # The panel is diagnostic. It must render even when settings cannot be
        # read, because that is exactly when somebody is looking at it.
        policy = None
    return {
        "available": backups_available(),
        "backups": rows,
        "count": len(rows),
        "total_bytes": sum(int(r.get("size_bytes") or 0) for r in rows),
        "full_count": sum(1 for r in rows if r.get("kind") == "full"),
        "database_count": sum(1 for r in rows if r.get("kind") != "full"),
        "offsite_bytes": sum(int(r.get("deliverables_bytes") or 0) for r in rows if r.get("deliverables_elsewhere")),
        "latest": rows[0] if rows else None,
        "latest_full": next((r for r in rows if r.get("kind") == "full"), None),
        "policy": policy,
        "disk": disk_usage(),
    }

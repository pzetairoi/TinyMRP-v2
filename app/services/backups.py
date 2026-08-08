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
        rows.append(
            {
                "name": name,
                "size_bytes": _dir_size_bytes(path),
                "created_at": created,
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


def summary(limit: int = 50) -> Dict[str, Any]:
    """Everything the dashboard needs, in one call."""
    rows = list_backups(limit=limit)
    return {
        "available": backups_available(),
        "backups": rows,
        "count": len(rows),
        "total_bytes": sum(int(r.get("size_bytes") or 0) for r in rows),
        "latest": rows[0] if rows else None,
        "disk": disk_usage(),
    }

# app/services/file_rescan.py — admin-triggered full storage rescan with progress.
"""Reconcile every Part's file records against storage.

Discovery is per-part and a full estate is thousands of parts, so the rescan
runs in a background thread and publishes progress that the admin page polls.
State is deliberately in-process: this is a single-instance maintenance action,
not a durable queue, and a restart simply clears it.
"""
import logging
import threading
from typing import Any, Dict

from flask import current_app

from app.models.part import Part
from app.services.filescan import (
    discover_part_files,
    remove_stale_part_files,
    scan_cache,
    upsert_part_files_detailed,
)
from app.services.thumbs_gen import generate_thumbs_for_parts

logger = logging.getLogger(__name__)

# Records are flushed in batches so progress advances steadily and one huge
# write never holds everything in memory.
_BATCH = 200

_LOCK = threading.Lock()
_STATE: Dict[str, Any] = {"status": "idle"}


def get_progress() -> Dict[str, Any]:
    """Snapshot of the current or most recent rescan."""
    with _LOCK:
        return dict(_STATE)


def _set(**fields: Any) -> None:
    with _LOCK:
        _STATE.update(fields)


def _render_thumbs(pairs: set[tuple[str, str]]) -> int:
    """Best effort: a thumbnail that will not render must not fail the rescan."""
    if not pairs:
        return 0
    try:
        return int(generate_thumbs_for_parts(sorted(pairs)) or 0)
    except Exception:
        logger.warning("thumbnail generation failed during rescan", exc_info=True)
        return 0


def _scan(*, remove_stale: bool) -> None:
    processed = files_seen = removed = 0
    try:
        pairs = [
            (str(row.part_number or "").strip(), str(row.revision or ""), row.attrs or {})
            for row in Part.objects.only("part_number", "revision", "attrs").order_by(
                "part_number", "revision"
            )
        ]
        _set(status="running", total=len(pairs), processed=0, files=0, removed=0, thumbs=0)
        batch: list[Dict[str, Any]] = []
        # Parts whose batch carried a PNG. The per-part refresh has always
        # rendered thumbnails; the bulk rescan did not, so images relinked here
        # stayed pictureless. Thumbnails already current are skipped, so this
        # only builds the missing ones.
        thumb_pairs: set[tuple[str, str]] = set()
        thumbs = 0
        # One cache for the whole run: each storage directory is listed once
        # instead of once per candidate filename per part.
        with scan_cache():
            for pn, rev, attrs in pairs:
                if _STATE.get("cancel"):
                    _set(status="cancelled")
                    return
                if pn:
                    found = discover_part_files(pn, rev, attrs=attrs)
                    for (group, drawing), record in found.items():
                        batch.append(
                            {
                                "part_number": pn,
                                "revision": rev,
                                "ext_group": group,
                                "is_dwg": drawing,
                                **record,
                            }
                        )
                        if str(group or "").casefold() == "png":
                            thumb_pairs.add((pn, rev))
                    if remove_stale:
                        removed += int(
                            remove_stale_part_files(pn, rev, found).get("count") or 0
                        )
                processed += 1
                if len(batch) >= _BATCH:
                    files_seen += int(upsert_part_files_detailed(batch).get("count") or 0)
                    batch = []
                    thumbs += _render_thumbs(thumb_pairs)
                    thumb_pairs = set()
                _set(processed=processed, files=files_seen, removed=removed, thumbs=thumbs)
            if batch:
                files_seen += int(upsert_part_files_detailed(batch).get("count") or 0)
            thumbs += _render_thumbs(thumb_pairs)
        _set(
            status="done",
            processed=processed,
            files=files_seen,
            removed=removed,
            thumbs=thumbs,
            error="",
        )
    except Exception as exc:  # surfaced verbatim on the admin page
        try:
            current_app.logger.exception("file rescan failed")
        except Exception:
            pass
        _set(status="error", error=str(exc), processed=processed, files=files_seen)


def run_now(*, remove_stale: bool = False) -> Dict[str, Any]:
    """Run the rescan synchronously inside the caller's app context."""
    with _LOCK:
        _STATE.clear()
        _STATE.update({"status": "running", "total": 0, "processed": 0, "files": 0, "removed": 0})
    _scan(remove_stale=remove_stale)
    return get_progress()


def start(app, *, remove_stale: bool = False) -> Dict[str, Any]:
    """Begin a background rescan unless one is already running."""
    with _LOCK:
        if _STATE.get("status") == "running":
            return dict(_STATE)
        _STATE.clear()
        _STATE.update(
            {"status": "running", "total": 0, "processed": 0, "files": 0, "removed": 0, "error": ""}
        )

    def _worker() -> None:
        with app.app_context():
            _scan(remove_stale=remove_stale)

    threading.Thread(target=_worker, daemon=True, name="tinymrp-file-rescan").start()
    return get_progress()


def cancel() -> Dict[str, Any]:
    """Ask a running rescan to stop at the next part boundary."""
    with _LOCK:
        if _STATE.get("status") == "running":
            _STATE["cancel"] = True
    return get_progress()

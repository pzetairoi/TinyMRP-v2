from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple
from uuid import uuid4

from flask import g, has_request_context

from app.models.audit import AuditLog
from app.models.part import Part
from app.models.part_annotation import PartAnnotation
from app.services.attrs import comments_search_text
from app.services.part_norm import clean_rev
from app.services.timezone_utils import utc_iso, utc_now


ANNOTATION_ATTR_KEYS = {"notes", "comments", "comments_search"}


def _part_key(part: Part) -> tuple[str, str]:
    return ((getattr(part, "part_number", None) or "").strip(), clean_rev(getattr(part, "revision", "") or ""))


def _cache_bucket(name: str) -> dict:
    if not has_request_context():
        return {}
    bucket = getattr(g, name, None)
    if not isinstance(bucket, dict):
        bucket = {}
        setattr(g, name, bucket)
    return bucket


def _doc_cache() -> dict[tuple[str, str], Optional[PartAnnotation]]:
    return _cache_bucket("_part_annotation_doc_cache")


def _payload_cache() -> dict[tuple[str, str], dict[str, Any]]:
    return _cache_bucket("_part_annotation_payload_cache")


def _audit_cache() -> dict[tuple[str, str, str], bool]:
    return _cache_bucket("_part_annotation_audit_cache")


def _get_doc(part: Part) -> Optional[PartAnnotation]:
    key = _part_key(part)
    cache = _doc_cache()
    if key in cache:
        return cache[key]
    doc = PartAnnotation.objects(part_number=key[0], revision=key[1]).first() if key[0] else None
    cache[key] = doc
    return doc


def preload_annotations(parts: Iterable[Part]) -> None:
    """Warm the per-request document cache for a whole listing in one query.

    ``_get_doc`` caches per part, so a page of rows would otherwise issue one
    query each. Misses are cached as ``None`` so parts without annotations do
    not fall back to individual lookups.
    """
    if not has_request_context():
        return
    cache = _doc_cache()
    wanted = {key for key in (_part_key(part) for part in parts) if key[0] and key not in cache}
    if not wanted:
        return
    for doc in PartAnnotation.objects(part_number__in=sorted({key[0] for key in wanted})):
        key = ((doc.part_number or "").strip(), clean_rev(doc.revision or ""))
        if key in wanted:
            cache[key] = doc
    for key in wanted:
        cache.setdefault(key, None)


def _set_doc_cache(part: Part, doc: Optional[PartAnnotation]) -> None:
    if not has_request_context():
        return
    _doc_cache()[_part_key(part)] = doc


def _set_payload_cache(part: Part, payload: dict[str, Any]) -> None:
    if not has_request_context():
        return
    _payload_cache()[_part_key(part)] = dict(payload or {})


def _normalize_notes(value: Any) -> str:
    return str(value or "").strip()


COMMENT_PRIORITIES = ("low", "normal", "high")
MAX_COMMENT_REPLIES = 200


def _normalize_comment_reply(value: Any) -> Optional[dict[str, str]]:
    if not isinstance(value, dict):
        return None
    text = str(value.get("text") or "").strip()
    if not text:
        return None
    reply_id = str(value.get("id") or "").strip()[:64]
    return {
        "id": reply_id or uuid4().hex,
        "ts": str(value.get("ts") or "").strip(),
        "author": str(value.get("author") or "").strip(),
        "text": text,
    }


def _normalize_comment(value: Any) -> Optional[dict[str, str]]:
    priority = ""
    comment_id = ""
    status = "open"
    replies: list[dict[str, str]] = []
    if isinstance(value, dict):
        text = str(value.get("text") or "").strip()
        author = str(value.get("author") or "").strip()
        ts = str(value.get("ts") or "").strip()
        raw_priority = str(value.get("priority") or "").strip().lower()
        if raw_priority in COMMENT_PRIORITIES:
            priority = raw_priority
        raw_id = str(value.get("id") or "").strip()
        if raw_id and len(raw_id) <= 64:
            comment_id = raw_id
        if str(value.get("status") or "").strip().lower() == "resolved":
            status = "resolved"
        raw_replies = value.get("replies")
        if isinstance(raw_replies, list):
            for raw_reply in raw_replies[:MAX_COMMENT_REPLIES]:
                normalized_reply = _normalize_comment_reply(raw_reply)
                if normalized_reply:
                    replies.append(normalized_reply)
    else:
        text = str(value or "").strip()
        author = ""
        ts = ""
    if not text and not author and not ts:
        return None
    out = {"ts": ts, "author": author, "text": text}
    if comment_id:
        out["id"] = comment_id
    if priority:
        out["priority"] = priority
    if replies:
        out["replies"] = replies
    out["status"] = status
    return out


def normalize_comment_rows(values: Any) -> list[dict[str, str]]:
    if values is None:
        return []
    rows = values if isinstance(values, list) else [values]
    out: list[dict[str, str]] = []
    for row in rows:
        normalized = _normalize_comment(row)
        if normalized:
            out.append(normalized)
    return out


def _payload(notes: Any = "", comments: Any = None) -> dict[str, Any]:
    notes_text = _normalize_notes(notes)
    comment_rows = normalize_comment_rows(comments)
    return {
        "notes": notes_text,
        "comments": comment_rows,
        "comments_search": comments_search_text(comment_rows),
    }


def _comments_look_legacy_system_managed(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in value for key in ("text", "author", "ts"))
    if isinstance(value, list):
        if not value:
            return False
        return all(isinstance(item, dict) and any(key in item for key in ("text", "author", "ts")) for item in value)
    return False


def _has_notes_audit(part: Part) -> bool:
    pn, rev = _part_key(part)
    if not pn:
        return False
    cache_key = (pn, rev, "part.notes.update")
    cache = _audit_cache()
    if cache_key in cache:
        return cache[cache_key]
    found = AuditLog.objects(action="part.notes.update", resource=f"{pn}:{rev}").limit(1).count() > 0
    cache[cache_key] = bool(found)
    return bool(found)


def legacy_annotation_attr_keys(part: Part, attrs: Optional[Dict[str, Any]] = None) -> set[str]:
    raw_attrs = dict(attrs or getattr(part, "attrs", {}) or {})
    doc = _get_doc(part)
    raw_comments = raw_attrs.get("comments")
    has_legacy_comments = _comments_look_legacy_system_managed(raw_comments) or bool(raw_attrs.get("comments_search"))
    if doc and has_legacy_comments:
        raw_comment_rows = normalize_comment_rows(raw_comments)
        doc_comment_rows = normalize_comment_rows(getattr(doc, "comments", []) or [])
        raw_comment_search = comments_search_text(raw_comment_rows)
        doc_comment_search = comments_search_text(doc_comment_rows)
        has_legacy_comments = bool(raw_comment_rows) and raw_comment_rows == doc_comment_rows and raw_comment_search == doc_comment_search
    out: set[str] = {"comments_search"} if raw_attrs.get("comments_search") is not None else set()
    if has_legacy_comments:
        out.update({"comments", "comments_search"})
    if raw_attrs.get("notes") is not None and doc is None and (_has_notes_audit(part) or has_legacy_comments):
        out.add("notes")
    return out


def legacy_annotation_payload(part: Part, attrs: Optional[Dict[str, Any]] = None) -> dict[str, Any]:
    raw_attrs = dict(attrs or getattr(part, "attrs", {}) or {})
    keys = legacy_annotation_attr_keys(part, raw_attrs)
    if not keys:
        return _payload()
    notes = raw_attrs.get("notes") if "notes" in keys else ""
    comments = raw_attrs.get("comments") if "comments" in keys else []
    return _payload(notes=notes, comments=comments)


def annotation_payload(part: Optional[Part], attrs: Optional[Dict[str, Any]] = None) -> dict[str, Any]:
    if not part:
        return _payload()
    key = _part_key(part)
    cache = _payload_cache()
    if key in cache:
        return dict(cache[key])

    doc = _get_doc(part)
    if doc:
        payload = _payload(notes=getattr(doc, "notes", ""), comments=getattr(doc, "comments", []))
    else:
        payload = legacy_annotation_payload(part, attrs)
    _set_payload_cache(part, payload)
    return dict(payload)


def _save_search_fields(part: Part, payload: dict[str, Any]) -> bool:
    changed = False
    notes_search = str(payload.get("notes") or "")
    comments_search = str(payload.get("comments_search") or "")
    if getattr(part, "notes_search", "") != notes_search:
        part.notes_search = notes_search
        changed = True
    if getattr(part, "comments_search", "") != comments_search:
        part.comments_search = comments_search
        changed = True
    return changed


def sync_annotation_search_fields(part: Part) -> bool:
    payload = annotation_payload(part)
    changed = _save_search_fields(part, payload)
    if changed:
        part.save()
    return changed


def migrate_legacy_annotations(part: Part) -> dict[str, Any]:
    if not part:
        return _payload()

    legacy_keys = legacy_annotation_attr_keys(part)
    legacy_payload = legacy_annotation_payload(part)
    doc = _get_doc(part)
    doc_changed = False

    if (legacy_payload.get("notes") or legacy_payload.get("comments")) and not doc:
        doc = PartAnnotation(part_number=part.part_number, revision=clean_rev(part.revision or ""))
        doc.notes = str(legacy_payload.get("notes") or "")
        doc.comments = list(legacy_payload.get("comments") or [])
        doc.created_at = utc_now()
        doc.updated_at = utc_now()
        doc.save()
        doc_changed = True
        _set_doc_cache(part, doc)
    elif doc:
        if legacy_payload.get("notes") and not getattr(doc, "notes", ""):
            doc.notes = str(legacy_payload.get("notes") or "")
            doc_changed = True
        if legacy_payload.get("comments") and not list(getattr(doc, "comments", []) or []):
            doc.comments = list(legacy_payload.get("comments") or [])
            doc_changed = True
        if doc_changed:
            doc.updated_at = utc_now()
            doc.save()

    part_changed = False
    attrs = dict(getattr(part, "attrs", {}) or {})
    for key in legacy_keys:
        if key in attrs:
            attrs.pop(key, None)
            part_changed = True

    if doc:
        payload = _payload(notes=getattr(doc, "notes", ""), comments=getattr(doc, "comments", []))
    else:
        payload = legacy_annotation_payload(part, attrs)
    if _save_search_fields(part, payload):
        part_changed = True

    if part_changed:
        part.attrs = attrs
        part.save()

    if doc_changed or part_changed:
        _set_payload_cache(part, payload)
    return payload


def _is_stale(base_updated_at: Any, stored_at: Any) -> bool:
    """True when the editor loaded an older copy than the one now stored.

    Parsing failures return False on purpose: an unreadable timestamp from a
    client must not manufacture a conflict warning that did not happen.
    """
    from datetime import datetime

    try:
        if isinstance(base_updated_at, str):
            base = datetime.fromisoformat(base_updated_at.replace("Z", "+00:00"))
        else:
            base = base_updated_at
        if base.tzinfo is None or stored_at.tzinfo is None:
            base = base.replace(tzinfo=None)
            stored_at = stored_at.replace(tzinfo=None)
        return stored_at > base
    except Exception:
        return False


def set_part_notes(part: Part, notes: str, base_updated_at: Any = None) -> dict[str, Any]:
    """Replace the free-text notes on a part.

    Notes are the ONE place a browser user types prose that another browser
    user can silently overwrite - comments are append-only, and status and
    priority are single-field toggles. So this is where a lost update actually
    costs someone their work.

    base_updated_at is what the editor loaded. If the stored copy has moved on
    since then the save still goes through (a hard reject would lose the text
    the user just typed, which is the same harm from the other direction), but
    the result reports the conflict AND returns the text that was replaced. A
    warning that says "you overwrote someone" without handing back what was
    lost is barely better than silence.
    """
    migrate_legacy_annotations(part)
    notes_text = _normalize_notes(notes)
    doc = _get_doc(part)
    comments = list(getattr(doc, "comments", []) or []) if doc else []

    conflict = None
    if base_updated_at is not None and doc is not None:
        stored_at = getattr(doc, "updated_at", None)
        if stored_at is not None and _is_stale(base_updated_at, stored_at):
            conflict = {
                "conflict": True,
                "replaced_notes": _normalize_notes(getattr(doc, "notes", "")),
                "replaced_at": stored_at.isoformat(),
            }

    if notes_text or comments:
        if not doc:
            doc = PartAnnotation(part_number=part.part_number, revision=clean_rev(part.revision or ""))
        doc.notes = notes_text
        doc.comments = comments
        now = utc_now()
        if not getattr(doc, "created_at", None):
            doc.created_at = now
        doc.updated_at = now
        doc.save()
        _set_doc_cache(part, doc)
        payload = _payload(notes=notes_text, comments=comments)
    else:
        if doc:
            doc.delete()
        _set_doc_cache(part, None)
        payload = _payload()

    _set_payload_cache(part, payload)
    part.notes_search = str(payload.get("notes") or "")
    part.comments_search = str(payload.get("comments_search") or "")
    part.updated_at = utc_now()
    part.save()
    if conflict:
        payload = {**payload, **conflict}
    payload["notes_updated_at"] = (
        doc.updated_at.isoformat() if doc is not None and getattr(doc, "updated_at", None) else None
    )
    return payload


def add_part_comment(
    part: Part,
    *,
    author: str,
    text: str,
    ts: Optional[str] = None,
    priority: Optional[str] = None,
) -> dict[str, Any]:
    migrate_legacy_annotations(part)
    doc = _get_doc(part)
    notes_text = str(getattr(doc, "notes", "") or "") if doc else ""
    comments = normalize_comment_rows(getattr(doc, "comments", []) if doc else [])
    comment = {
        "id": uuid4().hex,
        "ts": str(ts or utc_iso(utc_now()) or ""),
        "author": str(author or "").strip(),
        "text": str(text or "").strip(),
        "status": "open",
    }
    priority_text = str(priority or "").strip().lower()
    if priority_text in COMMENT_PRIORITIES:
        comment["priority"] = priority_text
    comments.append(comment)

    if not doc:
        doc = PartAnnotation(part_number=part.part_number, revision=clean_rev(part.revision or ""))
    doc.notes = notes_text
    doc.comments = comments
    now = utc_now()
    if not getattr(doc, "created_at", None):
        doc.created_at = now
    doc.updated_at = now
    doc.save()
    _set_doc_cache(part, doc)

    payload = _payload(notes=notes_text, comments=comments)
    _set_payload_cache(part, payload)
    part.notes_search = str(payload.get("notes") or "")
    part.comments_search = str(payload.get("comments_search") or "")
    part.updated_at = now
    part.save()
    from app.services.part_review_status import sync_part_review_status
    sync_part_review_status(part)
    return comment


def _persist_comment_rows(part: Part, doc: PartAnnotation, comments: list[dict[str, Any]]) -> None:
    doc.comments = comments
    doc.updated_at = utc_now()
    doc.save()
    _set_doc_cache(part, doc)
    payload = _payload(notes=str(doc.notes or ""), comments=comments)
    _set_payload_cache(part, payload)
    part.comments_search = str(payload.get("comments_search") or "")
    part.updated_at = utc_now()
    part.save()
    from app.services.part_review_status import sync_part_review_status
    sync_part_review_status(part)


def _find_comment_row(comments: list[dict[str, Any]], comment_id: str) -> Optional[dict[str, Any]]:
    key = str(comment_id or "").strip()
    if not key:
        return None
    for row in comments:
        if str(row.get("id") or "") == key:
            return row
    return None


def _comment_row_matches(
    row: dict[str, Any],
    comment_id: Optional[str],
    ts: Optional[str],
    text: Optional[str],
) -> bool:
    """Identify one comment by id (preferred) or, for older clients, (ts, text)."""
    id_key = str(comment_id or "").strip()
    if id_key:
        return str(row.get("id") or "") == id_key
    ts_key = str(ts or "").strip()
    text_key = str(text or "").strip()
    return bool(ts_key) and str(row.get("ts") or "") == ts_key and (
        not text_key or str(row.get("text") or "") == text_key
    )


def find_part_comment(
    part: Part,
    *,
    comment_id: Optional[str] = None,
    ts: Optional[str] = None,
    text: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """One comment, matched exactly as remove_part_comment would match it.

    Callers need the author before mutating, to decide whether this user is
    allowed to. Sharing the matching rule keeps the comment that gets checked
    and the comment that gets changed the same one.
    """
    doc = _get_doc(part)
    if not doc:
        return None
    for row in normalize_comment_rows(getattr(doc, "comments", []) or []):
        if _comment_row_matches(row, comment_id, ts, text):
            return row
    return None


def set_part_comment_status(part: Part, *, comment_id: str, status: str) -> Optional[dict[str, Any]]:
    migrate_legacy_annotations(part)
    doc = _get_doc(part)
    if not doc:
        return None
    next_status = "resolved" if str(status or "").strip().lower() == "resolved" else "open"
    comments = normalize_comment_rows(getattr(doc, "comments", []) or [])
    updated = _find_comment_row(comments, comment_id)
    if updated is None:
        return None
    updated["status"] = next_status
    _persist_comment_rows(part, doc, comments)
    return updated


def set_part_comment_priority(part: Part, *, comment_id: str, priority: str) -> Optional[dict[str, Any]]:
    """Set or clear ('' / 'none') the importance of one comment."""
    migrate_legacy_annotations(part)
    doc = _get_doc(part)
    if not doc:
        return None
    comments = normalize_comment_rows(getattr(doc, "comments", []) or [])
    updated = _find_comment_row(comments, comment_id)
    if updated is None:
        return None
    priority_text = str(priority or "").strip().lower()
    if priority_text in COMMENT_PRIORITIES:
        updated["priority"] = priority_text
    else:
        updated.pop("priority", None)
    _persist_comment_rows(part, doc, comments)
    return updated


def add_part_comment_reply(
    part: Part,
    *,
    comment_id: str,
    author: str,
    text: str,
    ts: Optional[str] = None,
) -> Optional[Tuple[dict[str, Any], dict[str, Any]]]:
    """Append a reply to one comment. Returns (comment, reply) or None."""
    reply_text = str(text or "").strip()
    if not reply_text:
        return None
    migrate_legacy_annotations(part)
    doc = _get_doc(part)
    if not doc:
        return None
    comments = normalize_comment_rows(getattr(doc, "comments", []) or [])
    target = _find_comment_row(comments, comment_id)
    if target is None:
        return None
    replies = list(target.get("replies") or [])
    if len(replies) >= MAX_COMMENT_REPLIES:
        return None
    reply = {
        "id": uuid4().hex,
        "ts": str(ts or utc_iso(utc_now()) or ""),
        "author": str(author or "").strip(),
        "text": reply_text,
    }
    replies.append(reply)
    target["replies"] = replies
    _persist_comment_rows(part, doc, comments)
    return target, reply


def remove_part_comment(
    part: Part,
    *,
    comment_id: Optional[str] = None,
    ts: Optional[str] = None,
    text: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Remove one comment identified by id (preferred) or by (ts, text).

    Returns the removed comment dict, or None when no match was found.
    """
    migrate_legacy_annotations(part)
    doc = _get_doc(part)
    if not doc:
        return None
    notes_text = str(getattr(doc, "notes", "") or "")
    comments = normalize_comment_rows(getattr(doc, "comments", []) or [])

    removed: Optional[dict[str, Any]] = None
    remaining: list[dict[str, str]] = []
    for row in comments:
        if removed is None and _comment_row_matches(row, comment_id, ts, text):
            removed = row
            continue
        remaining.append(row)
    if removed is None:
        return None

    if notes_text or remaining:
        doc.notes = notes_text
        doc.comments = remaining
        doc.updated_at = utc_now()
        doc.save()
        _set_doc_cache(part, doc)
    else:
        doc.delete()
        _set_doc_cache(part, None)

    payload = _payload(notes=notes_text, comments=remaining)
    _set_payload_cache(part, payload)
    part.notes_search = str(payload.get("notes") or "")
    part.comments_search = str(payload.get("comments_search") or "")
    part.updated_at = utc_now()
    part.save()
    from app.services.part_review_status import sync_part_review_status
    sync_part_review_status(part)
    return removed


def filtered_part_attrs(part: Part, attrs: Optional[Dict[str, Any]] = None) -> dict[str, Any]:
    if isinstance(attrs, dict):
        raw_attrs = dict(attrs or {})
    else:
        raw_attrs = dict(getattr(part, "attrs", {}) or {})
    suppressed = legacy_annotation_attr_keys(part, raw_attrs)
    out: dict[str, Any] = {}
    for key, value in raw_attrs.items():
        normalized = str(key or "").strip().lower()
        if key in suppressed or normalized in suppressed or normalized == "comments_search":
            continue
        out[key] = value
    return out


def bulk_sync_annotation_search_fields(parts: Iterable[Part]) -> dict[str, int]:
    updated = 0
    migrated = 0
    for part in parts:
        before_attrs = dict(getattr(part, "attrs", {}) or {})
        before_notes_search = getattr(part, "notes_search", "")
        before_comments_search = getattr(part, "comments_search", "")
        migrate_legacy_annotations(part)
        after_attrs = dict(getattr(part, "attrs", {}) or {})
        if before_attrs != after_attrs:
            migrated += 1
        if before_notes_search != getattr(part, "notes_search", "") or before_comments_search != getattr(part, "comments_search", ""):
            updated += 1
    return {"updated": updated, "migrated": migrated}

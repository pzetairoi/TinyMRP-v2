from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
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


def _normalize_comment(value: Any) -> Optional[dict[str, str]]:
    priority = ""
    comment_id = ""
    status = "open"
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


def set_part_notes(part: Part, notes: str) -> dict[str, Any]:
    migrate_legacy_annotations(part)
    notes_text = _normalize_notes(notes)
    doc = _get_doc(part)
    comments = list(getattr(doc, "comments", []) or []) if doc else []

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


def set_part_comment_status(part: Part, *, comment_id: str, status: str) -> Optional[dict[str, Any]]:
    migrate_legacy_annotations(part)
    doc = _get_doc(part)
    if not doc:
        return None
    next_status = "resolved" if str(status or "").strip().lower() == "resolved" else "open"
    comments = normalize_comment_rows(getattr(doc, "comments", []) or [])
    updated = None
    for row in comments:
        if str(row.get("id") or "") == str(comment_id or ""):
            row["status"] = next_status
            updated = row
            break
    if updated is None:
        return None
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
    return updated


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

    id_key = str(comment_id or "").strip()
    ts_key = str(ts or "").strip()
    text_key = str(text or "").strip()
    removed: Optional[dict[str, Any]] = None
    remaining: list[dict[str, str]] = []
    for row in comments:
        if removed is None:
            if id_key and str(row.get("id") or "") == id_key:
                removed = row
                continue
            if not id_key and ts_key and str(row.get("ts") or "") == ts_key and (
                not text_key or str(row.get("text") or "") == text_key
            ):
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

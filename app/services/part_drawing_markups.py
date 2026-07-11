# app/services/part_drawing_markups.py — drawing markup layers + review threads
from __future__ import annotations

import hashlib
import uuid
from typing import Any, Optional

from app.models.artifact import PartFile
from app.models.part import Part
from app.models.part_drawing_markup import (
    THREAD_PRIORITIES,
    THREAD_STATUSES,
    PartDrawingMarkup,
    PartDrawingMarkupMessage,
    PartDrawingMarkupThread,
)
from app.services.part_norm import clean_rev
from app.services.timezone_utils import format_display_ts, local_input_value, utc_iso, utc_now
from app.services.user_profile import resolve_identity_profile, resolve_identity_profiles


CANVAS_SCHEMA_VERSION = 1

MAX_CANVAS_BYTES = 2 * 1024 * 1024   # request payload cap (2 MiB)
MAX_CANVAS_OBJECTS = 500
MAX_TEXT_LEN = 5000
MAX_THREAD_TITLE_LEN = 200
MAX_MESSAGE_LEN = 5000
MAX_OBJECT_ID_LEN = 64
MAX_NESTING_DEPTH = 6
MAX_KEYS_PER_OBJECT = 120

# Only the Fabric types our editor actually creates (compared lowercase so both
# Fabric v6/v7 class-style names like "Rect" and legacy "rect" are accepted).
ALLOWED_FABRIC_TYPES = {"line", "rect", "ellipse", "path", "textbox", "group", "triangle"}

# Keys that must never appear anywhere in stored canvas JSON.
DANGEROUS_KEYS = {"__proto__", "prototype", "constructor", "src", "crossorigin", "href", "xlink:href"}

# String fragments that indicate embedded images/HTML/script content.
DANGEROUS_VALUE_FRAGMENTS = (
    "data:image",
    ";base64,",
    "<script",
    "<svg",
    "<iframe",
    "<img",
    "javascript:",
)


class MarkupValidationError(ValueError):
    """Invalid markup payload (HTTP 400)."""


class MarkupTooLargeError(MarkupValidationError):
    """Payload exceeds configured limits (HTTP 413)."""


class MarkupConflictError(Exception):
    """Optimistic concurrency conflict (HTTP 409). Carries the current doc."""

    def __init__(self, current: Optional[PartDrawingMarkup]):
        super().__init__("markup version conflict")
        self.current = current


# ---------------------------------------------------------------------------
# Source fingerprint
# ---------------------------------------------------------------------------

def source_fingerprint_for(pf: PartFile) -> str:
    """Canonical fingerprint for a drawing PartFile.

    Prefers the stored sha256; otherwise derives a deterministic value from
    stable metadata. Never hashes file bytes here.
    """
    sha = str(getattr(pf, "sha256", "") or "").strip().lower()
    if sha:
        return f"sha256:{sha}"
    rel = str(getattr(pf, "rel_path", "") or "").strip().replace("\\", "/")
    size = getattr(pf, "size", None)
    mtime = getattr(pf, "mtime_iso", None) or getattr(pf, "mtime", None)
    mtime_text = utc_iso(mtime) or ""
    raw = f"{rel}|{size or 0}|{mtime_text}"
    return "meta:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def find_drawing_source(pn: str, rev: str, source_file_id: str) -> Optional[PartFile]:
    """Resolve a drawing PNG PartFile that belongs to (pn, rev)."""
    source_file_id = str(source_file_id or "").strip()
    if not source_file_id:
        return None
    try:
        pf = PartFile.objects(id=source_file_id).first()
    except Exception:
        return None
    if not pf:
        return None
    if str(pf.part_number or "").strip().lower() != str(pn or "").strip().lower():
        return None
    if clean_rev(pf.revision or "").lower() != clean_rev(rev or "").lower():
        return None
    if str(getattr(pf, "ext_group", "") or "").lower() != "png" or not bool(getattr(pf, "is_dwg", False)):
        return None
    return pf


# ---------------------------------------------------------------------------
# Canvas JSON validation
# ---------------------------------------------------------------------------

def _reject_dangerous_string(value: str, where: str) -> None:
    lowered = value.lower()
    for fragment in DANGEROUS_VALUE_FRAGMENTS:
        if fragment in lowered:
            raise MarkupValidationError(f"disallowed content in {where}")


def _validate_value(value: Any, where: str, depth: int) -> None:
    if depth > MAX_NESTING_DEPTH:
        raise MarkupValidationError(f"canvas JSON nested too deeply at {where}")
    if value is None or isinstance(value, (bool, int, float)):
        return
    if isinstance(value, str):
        if len(value) > MAX_TEXT_LEN:
            raise MarkupTooLargeError(f"text value too long at {where}")
        _reject_dangerous_string(value, where)
        return
    if isinstance(value, list):
        for idx, item in enumerate(value):
            _validate_value(item, f"{where}[{idx}]", depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > MAX_KEYS_PER_OBJECT:
            raise MarkupValidationError(f"too many keys at {where}")
        for key, item in value.items():
            key_text = str(key)
            if key_text.strip().lower() in DANGEROUS_KEYS:
                raise MarkupValidationError(f"disallowed key '{key_text}' at {where}")
            _validate_value(item, f"{where}.{key_text}", depth + 1)
        return
    raise MarkupValidationError(f"unsupported value type at {where}")


def _count_objects(obj: dict) -> int:
    total = 1
    nested = obj.get("objects")
    if isinstance(nested, list):
        for child in nested:
            if isinstance(child, dict):
                total += _count_objects(child)
    return total


def _validate_fabric_object(obj: Any, where: str, *, top_level: bool) -> None:
    if not isinstance(obj, dict):
        raise MarkupValidationError(f"canvas object must be an object at {where}")
    obj_type = str(obj.get("type") or "").strip().lower()
    if obj_type not in ALLOWED_FABRIC_TYPES:
        raise MarkupValidationError(f"unsupported fabric object type '{obj_type}' at {where}")
    if top_level:
        tm_id = obj.get("tmObjectId")
        if not isinstance(tm_id, str) or not tm_id.strip() or len(tm_id) > MAX_OBJECT_ID_LEN:
            raise MarkupValidationError(f"missing or invalid tmObjectId at {where}")
    _validate_value(obj, where, 0)
    nested = obj.get("objects")
    if nested is not None:
        if not isinstance(nested, list):
            raise MarkupValidationError(f"nested objects must be a list at {where}")
        for idx, child in enumerate(nested):
            _validate_fabric_object(child, f"{where}.objects[{idx}]", top_level=False)


def validate_canvas_json(payload: Any) -> dict:
    """Validate and normalize a submitted Fabric canvas JSON document.

    Returns a sanitized dict containing only 'version' and 'objects'.
    Raises MarkupValidationError / MarkupTooLargeError on bad input.
    """
    if not isinstance(payload, dict):
        raise MarkupValidationError("canvas_json must be an object")
    allowed_top = {"version", "objects"}
    extra = set(str(k) for k in payload.keys()) - allowed_top
    if extra:
        raise MarkupValidationError(f"unsupported canvas keys: {', '.join(sorted(extra))}")

    version = payload.get("version")
    if version is not None and (not isinstance(version, str) or len(version) > 32):
        raise MarkupValidationError("canvas version must be a short string")

    objects = payload.get("objects")
    if objects is None:
        objects = []
    if not isinstance(objects, list):
        raise MarkupValidationError("canvas objects must be a list")

    total = 0
    seen_ids: set[str] = set()
    for idx, obj in enumerate(objects):
        _validate_fabric_object(obj, f"objects[{idx}]", top_level=True)
        tm_id = str(obj.get("tmObjectId"))
        if tm_id in seen_ids:
            raise MarkupValidationError(f"duplicate tmObjectId '{tm_id}'")
        seen_ids.add(tm_id)
        total += _count_objects(obj)
        if total > MAX_CANVAS_OBJECTS:
            raise MarkupTooLargeError(f"too many canvas objects (max {MAX_CANVAS_OBJECTS})")

    out: dict[str, Any] = {"objects": objects}
    if isinstance(version, str):
        out["version"] = version
    return out


def canvas_object_ids(canvas_json: dict) -> set[str]:
    ids: set[str] = set()
    for obj in (canvas_json or {}).get("objects") or []:
        if isinstance(obj, dict):
            tm_id = obj.get("tmObjectId")
            if isinstance(tm_id, str) and tm_id.strip():
                ids.add(tm_id)
    return ids


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _ts_fields(value) -> dict[str, Any]:
    return {
        "ts": utc_iso(value),
        "ts_display": format_display_ts(value, fmt="%Y-%m-%d %H:%M:%S %Z") or None,
        "ts_local": local_input_value(value) or None,
    }


def _author_fields(author: str, resolved: dict[str, dict[str, object]]) -> dict[str, Any]:
    author = str(author or "").strip()
    profile = resolved.get(author.lower()) if author else None
    if author and profile is None:
        profile = resolve_identity_profile(author)
    return {
        "author": author,
        "author_display": (profile or {}).get("label") or author or "User",
        "author_profile": profile,
    }


def _serialize_message(msg: PartDrawingMarkupMessage, resolved: dict) -> dict[str, Any]:
    out = {"id": str(msg.id or ""), "text": str(msg.text or "")}
    out.update(_ts_fields(msg.ts))
    out.update(_author_fields(msg.author or "", resolved))
    return out


def _serialize_thread(thread: PartDrawingMarkupThread, resolved: dict, present_ids: set[str]) -> dict[str, Any]:
    object_ids = [str(x) for x in (thread.object_ids or [])]
    messages = [_serialize_message(m, resolved) for m in (thread.messages or [])]
    created = _author_fields(thread.created_by or "", resolved)
    return {
        "id": str(thread.id or ""),
        "object_ids": object_ids,
        "linked": any(oid in present_ids for oid in object_ids),
        "title": str(thread.title or ""),
        "priority": str(thread.priority or "normal"),
        "status": str(thread.status or "open"),
        "created_by": created["author"],
        "created_by_display": created["author_display"],
        "created_by_profile": created["author_profile"],
        "created_at": utc_iso(thread.created_at),
        "created_at_display": format_display_ts(thread.created_at, fmt="%Y-%m-%d %H:%M:%S %Z") or None,
        "created_at_local": local_input_value(thread.created_at) or None,
        "updated_by": str(thread.updated_by or ""),
        "updated_at": utc_iso(thread.updated_at),
        "updated_at_display": format_display_ts(thread.updated_at, fmt="%Y-%m-%d %H:%M:%S %Z") or None,
        "resolved_by": str(thread.resolved_by or ""),
        "resolved_at": utc_iso(thread.resolved_at),
        "resolved_at_display": format_display_ts(thread.resolved_at, fmt="%Y-%m-%d %H:%M:%S %Z") or None,
        "messages": messages,
        "reply_count": max(0, len(messages) - 1),
    }


def _collect_identities(doc: Optional[PartDrawingMarkup]) -> dict[str, dict[str, object]]:
    if not doc:
        return {}
    identities: list[str] = []
    for thread in doc.threads or []:
        identities.append(str(thread.created_by or ""))
        for msg in thread.messages or []:
            identities.append(str(msg.author or ""))
    return resolve_identity_profiles(identities)


def stale_layers_count(pn: str, rev: str, source_file_id: str, current_fingerprint: str) -> int:
    try:
        return PartDrawingMarkup.objects(
            part_number__iexact=(pn or "").strip(),
            revision__iexact=clean_rev(rev or ""),
            source_file_id=str(source_file_id or ""),
            source_fingerprint__ne=str(current_fingerprint or ""),
        ).count()
    except Exception:
        return 0


def serialize_markup(
    doc: Optional[PartDrawingMarkup],
    *,
    part_number: str,
    revision: str,
    source_file: PartFile,
    fingerprint: str,
    page_number: int = 1,
    can_edit: bool = False,
) -> dict[str, Any]:
    """Build the canonical API representation for a markup layer.

    A missing doc serializes as an empty version-0 layer (never persisted).
    """
    resolved = _collect_identities(doc)
    canvas_json = dict(doc.canvas_json or {}) if doc else {"objects": []}
    if "objects" not in canvas_json:
        canvas_json["objects"] = []
    present_ids = canvas_object_ids(canvas_json)
    threads = [_serialize_thread(t, resolved, present_ids) for t in (doc.threads or [])] if doc else []
    mtime = getattr(source_file, "mtime_iso", None) or getattr(source_file, "mtime", None)
    return {
        "ok": True,
        "part_number": part_number,
        "revision": revision,
        "source": {
            "source_file_id": str(source_file.id),
            "rel_path": str(getattr(source_file, "rel_path", "") or ""),
            "fingerprint": fingerprint,
            "size": getattr(source_file, "size", None),
            "mtime": utc_iso(mtime),
        },
        "page_number": int(page_number or 1),
        "version": int(doc.version or 0) if doc else 0,
        "canvas_schema_version": int(doc.canvas_schema_version or CANVAS_SCHEMA_VERSION) if doc else CANVAS_SCHEMA_VERSION,
        "canvas_json": canvas_json,
        "threads": threads,
        "open_thread_count": sum(1 for t in threads if t.get("status") == "open"),
        "stale_layers_count": stale_layers_count(part_number, revision, str(source_file.id), fingerprint),
        "can_edit": bool(can_edit),
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def get_markup_layer(pn: str, rev: str, source_file_id: str, fingerprint: str, page_number: int = 1) -> Optional[PartDrawingMarkup]:
    return PartDrawingMarkup.objects(
        part_number__iexact=(pn or "").strip(),
        revision__iexact=clean_rev(rev or ""),
        source_file_id=str(source_file_id or ""),
        source_fingerprint=str(fingerprint or ""),
        page_number=int(page_number or 1),
    ).first()


def _pruned_threads(doc: PartDrawingMarkup, present_ids: set[str]) -> list[PartDrawingMarkupThread]:
    """Drop references to canvas objects that no longer exist.

    Threads themselves are always preserved (possibly unlinked) so discussion
    history is never silently discarded.
    """
    threads: list[PartDrawingMarkupThread] = []
    for thread in doc.threads or []:
        kept = [oid for oid in (thread.object_ids or []) if oid in present_ids]
        if kept != list(thread.object_ids or []):
            thread.object_ids = kept
        threads.append(thread)
    return threads


def save_markup_layer(
    *,
    part: Part,
    source_file: PartFile,
    fingerprint: str,
    page_number: int,
    canvas_json: dict,
    expected_version: int,
    user_email: str,
) -> PartDrawingMarkup:
    """Create or update a markup layer with optimistic concurrency.

    Raises MarkupConflictError (carrying the current doc) when
    expected_version does not match the stored version.
    """
    pn = str(part.part_number or "").strip()
    rev = clean_rev(part.revision or "")
    now = utc_now()
    doc = get_markup_layer(pn, rev, str(source_file.id), fingerprint, page_number)

    if doc is None:
        if int(expected_version) != 0:
            raise MarkupConflictError(None)
        doc = PartDrawingMarkup(
            part_number=pn,
            revision=rev,
            source_file_id=str(source_file.id),
            source_rel_path=str(getattr(source_file, "rel_path", "") or ""),
            source_fingerprint=fingerprint,
            page_number=int(page_number or 1),
            canvas_schema_version=CANVAS_SCHEMA_VERSION,
            canvas_json=canvas_json,
            threads=[],
            version=1,
            created_by=user_email,
            created_at=now,
            updated_by=user_email,
            updated_at=now,
        )
        try:
            doc.save()
        except Exception:
            # Unique index hit: another writer created the layer first.
            current = get_markup_layer(pn, rev, str(source_file.id), fingerprint, page_number)
            raise MarkupConflictError(current)
        return doc

    if int(expected_version) != int(doc.version or 0):
        raise MarkupConflictError(doc)

    doc.threads = _pruned_threads(doc, canvas_object_ids(canvas_json))
    updated = PartDrawingMarkup.objects(id=doc.id, version=int(expected_version)).update_one(
        set__canvas_json=canvas_json,
        set__threads=doc.threads,
        set__version=int(expected_version) + 1,
        set__updated_by=user_email,
        set__updated_at=now,
    )
    if not updated:
        current = PartDrawingMarkup.objects(id=doc.id).first()
        raise MarkupConflictError(current)
    doc.reload()
    return doc


def _bump_version(doc: PartDrawingMarkup, user_email: str) -> None:
    doc.version = int(doc.version or 0) + 1
    doc.updated_by = user_email
    doc.updated_at = utc_now()
    doc.save()


def _normalize_priority(value: Any) -> str:
    text = str(value or "normal").strip().lower()
    if text not in THREAD_PRIORITIES:
        raise MarkupValidationError("invalid priority")
    return text


def _clean_message_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise MarkupValidationError("message text is required")
    if len(text) > MAX_MESSAGE_LEN:
        raise MarkupTooLargeError(f"message too long (max {MAX_MESSAGE_LEN})")
    _reject_dangerous_string(text, "message")
    return text


def create_thread(
    doc: PartDrawingMarkup,
    *,
    object_ids: list,
    title: Any,
    priority: Any,
    message_text: Any,
    user_email: str,
) -> PartDrawingMarkupThread:
    if not isinstance(object_ids, list) or not object_ids:
        raise MarkupValidationError("object_ids must be a non-empty list")
    present = canvas_object_ids(doc.canvas_json or {})
    ids: list[str] = []
    for oid in object_ids:
        oid_text = str(oid or "").strip()
        if not oid_text or oid_text not in present:
            raise MarkupValidationError(f"unknown markup object id '{oid_text}'")
        if oid_text not in ids:
            ids.append(oid_text)

    title_text = str(title or "").strip()
    if len(title_text) > MAX_THREAD_TITLE_LEN:
        raise MarkupTooLargeError(f"title too long (max {MAX_THREAD_TITLE_LEN})")
    if title_text:
        _reject_dangerous_string(title_text, "title")
    text = _clean_message_text(message_text)

    now = utc_now()
    thread = PartDrawingMarkupThread(
        id=str(uuid.uuid4()),
        object_ids=ids,
        title=title_text,
        priority=_normalize_priority(priority),
        status="open",
        created_by=user_email,
        created_at=now,
        updated_by=user_email,
        updated_at=now,
        messages=[PartDrawingMarkupMessage(id=str(uuid.uuid4()), author=user_email, ts=now, text=text)],
    )
    doc.threads = list(doc.threads or []) + [thread]
    _bump_version(doc, user_email)
    return thread


def find_thread(doc: PartDrawingMarkup, thread_id: str) -> Optional[PartDrawingMarkupThread]:
    thread_id = str(thread_id or "").strip()
    for thread in doc.threads or []:
        if str(thread.id) == thread_id:
            return thread
    return None


def add_thread_message(doc: PartDrawingMarkup, thread: PartDrawingMarkupThread, *, text: Any, user_email: str) -> PartDrawingMarkupMessage:
    message = PartDrawingMarkupMessage(
        id=str(uuid.uuid4()),
        author=user_email,
        ts=utc_now(),
        text=_clean_message_text(text),
    )
    thread.messages = list(thread.messages or []) + [message]
    thread.updated_by = user_email
    thread.updated_at = utc_now()
    _bump_version(doc, user_email)
    return message


def set_thread_status(doc: PartDrawingMarkup, thread: PartDrawingMarkupThread, *, action: str, user_email: str) -> None:
    action = str(action or "").strip().lower()
    if action == "resolve":
        thread.status = "resolved"
        thread.resolved_by = user_email
        thread.resolved_at = utc_now()
    elif action == "reopen":
        thread.status = "open"
        thread.resolved_by = ""
        thread.resolved_at = None
    else:
        raise MarkupValidationError("action must be 'resolve' or 'reopen'")
    thread.updated_by = user_email
    thread.updated_at = utc_now()
    _bump_version(doc, user_email)


def update_thread_priority(doc: PartDrawingMarkup, thread: PartDrawingMarkupThread, *, priority: Any, user_email: str) -> None:
    thread.priority = _normalize_priority(priority)
    thread.updated_by = user_email
    thread.updated_at = utc_now()
    _bump_version(doc, user_email)


def delete_markups_for_part(pn: str, rev: str) -> int:
    """Remove markup layers for one (pn, rev); returns count. Used by deletion."""
    try:
        return int(
            PartDrawingMarkup.objects(
                part_number__iexact=(pn or "").strip(),
                revision__iexact=clean_rev(rev or ""),
            ).delete()
            or 0
        )
    except Exception:
        return 0

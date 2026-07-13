from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from app.services.canonical_fields import (
    APPROVED_STATUS_ATTR_ALIASES,
    APPROVED_BY_ATTR_ALIASES,
    APPROVED_DATE_ATTR_ALIASES,
    approval_void_regex,
    canonical_attr_key,
    canonical_attrs_for_part,
    default_normalized_attr_alias_map,
    extract_canonical_fields,
    resolve_approval,
    sync_part_canonical_fields,
)

ALIASES: Dict[str, str] = default_normalized_attr_alias_map()

REQUIRED_KEYS: Iterable[str] = (
    "approved_by",
    "approved_date",
    "drawnby",
    "drawndate",
    "checkeddate",
    "checkedby",
    "classified",
    "category",
    "configuration",
    "datasheet",
    "description",
    "file",
    "finish",
    "folder",
    "link",
    "mass",
    "material",
    "oem",
    "oem_partnumber",
    "process",
    "process2",
    "process3",
    "revision",
    "spare_part",
)

def approval_query_keys(*, include_canonical: bool = True, include_legacy: bool = True) -> List[str]:
    keys: List[str] = []
    if include_canonical:
        keys.extend(["canonical.approved", "canonical.approved_by", "field_values.approved", "attrs.approved", "attrs.approved_by"])
    if include_legacy:
        keys.extend(["attrs.approvedby", "attrs.is_approved", "attrs.approval_status"])
    seen = set()
    out: List[str] = []
    for key in keys:
        token = str(key or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def approval_filter_raw(keys: Iterable[str] | None = None, *, approved: bool) -> Dict[str, Any]:
    fields = [str(key or "").strip() for key in (keys or approval_query_keys()) if str(key or "").strip()]
    if not fields:
        return {}

    canonical_field = "canonical.approved" if "canonical.approved" in fields else ""
    fallback_fields = [field for field in fields if field != canonical_field]
    void_re = approval_void_regex()

    positive_clauses = [
        {
            "$and": [
                {field: {"$exists": True}},
                {field: {"$nin": [None, False, 0]}},
                {field: {"$not": void_re}},
            ]
        }
        for field in fallback_fields
    ]
    negative_clauses = [
        condition
        for field in fallback_fields
        for condition in ({field: {"$in": [None, False, 0]}}, {field: void_re})
    ]

    if positive_clauses:
        fallback_approved: Dict[str, Any] = {"$and": [{"$or": positive_clauses}, {"$nor": negative_clauses}]}
        fallback_unapproved: Dict[str, Any] = {"$or": [{"$nor": positive_clauses}, {"$or": negative_clauses}]}
    else:
        fallback_approved = {"_id": {"$exists": False}}
        fallback_unapproved = {}

    if not canonical_field:
        return fallback_approved if approved else fallback_unapproved

    if approved:
        return {
            "$or": [
                {canonical_field: True},
                {"$and": [{canonical_field: {"$exists": False}}, fallback_approved]},
            ]
        }
    return {
        "$or": [
            {canonical_field: {"$exists": True, "$ne": True}},
            {"$and": [{canonical_field: {"$exists": False}}, fallback_unapproved]},
        ]
    }


def approved_by_value(attrs: Dict[str, Any]) -> Any:
    return resolve_approval(attrs or {}).get("approved_by") or None


def approved_date_value(attrs: Dict[str, Any]) -> Any:
    return resolve_approval(attrs or {}).get("approved_date") or None


def approved_value(attrs: Dict[str, Any]) -> Any:
    approval = resolve_approval(attrs or {})
    return approval.get("approved_by") or (True if approval.get("approved") else None)


def approval_field_values(attrs: Dict[str, Any]) -> Dict[str, Any]:
    approval = resolve_approval(attrs or {})
    return {
        "approved": bool(approval.get("approved")),
        "approved_by": str(approval.get("approved_by") or "").strip(),
        "approved_date": str(approval.get("approved_date") or "").strip(),
    }


def _normalize_approved_fields(attrs: Dict[str, Any]) -> None:
    if not isinstance(attrs, dict):
        return
    approval = resolve_approval(attrs)
    groups = {
        "approved": {
            canonical_attr_key(alias)
            for alias in APPROVED_STATUS_ATTR_ALIASES
            if canonical_attr_key(alias)
        },
        "approved_by": {
            canonical_attr_key(alias)
            for alias in APPROVED_BY_ATTR_ALIASES
            if canonical_attr_key(alias)
        },
        "approved_date": {
            canonical_attr_key(alias)
            for alias in APPROVED_DATE_ATTR_ALIASES
            if canonical_attr_key(alias)
        },
    }
    preserved: Dict[str, List[Any]] = {key: [] for key in groups}
    for key in list(attrs.keys()):
        token = canonical_attr_key(key)
        for target, aliases in groups.items():
            if token in aliases:
                value = attrs.pop(key, None)
                if isinstance(value, (list, tuple, set)):
                    preserved[target].extend(value)
                else:
                    preserved[target].append(value)
                break

    # Keep the source values instead of replacing them with a derived boolean.
    # Approval rules are configurable, so preserving the source lets a later
    # rule change consistently re-evaluate already stored parts.
    for target, values in preserved.items():
        if not values:
            continue
        attrs[target] = values[0] if len(values) == 1 else values

    # Preserve the long-standing normalized shape for a real approver identity.
    # This flag is only derived when there was no explicit status value. A
    # configured negative/placeholder remains authoritative in the resolver.
    if not preserved["approved"] and preserved["approved_by"] and approval.get("approved"):
        attrs["approved"] = True


def normalize_record_attrs(raw: Dict[str, Any] | None) -> Dict[str, Any]:
    attrs = dict(raw or {})
    _normalize_approved_fields(attrs)
    return attrs


def comments_search_text(value: Any) -> str:
    if value is None:
        return ""
    parts: List[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                for key in ("author", "text", "ts"):
                    text = str(item.get(key) or "").strip()
                    if text:
                        parts.append(text)
                replies = item.get("replies")
                if isinstance(replies, list):
                    for reply in replies:
                        if not isinstance(reply, dict):
                            continue
                        for key in ("author", "text"):
                            text = str(reply.get(key) or "").strip()
                            if text:
                                parts.append(text)
            else:
                text = str(item).strip()
                if text:
                    parts.append(text)
    elif isinstance(value, dict):
        for key in ("author", "text", "ts"):
            text = str(value.get(key) or "").strip()
            if text:
                parts.append(text)
    else:
        text = str(value).strip()
        if text:
            parts.append(text)
    return " | ".join(parts)


def process_attributes(raw_attrs: Dict[str, Any] | None) -> Tuple[Dict[str, Any], List[str]]:
    attrs = normalize_record_attrs(raw_attrs)
    canonical = extract_canonical_fields(attrs)
    return attrs, list(canonical.get("processes") or [])


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _aliasize(raw: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in (raw or {}).items():
        normalized = canonical_attr_key(key)
        target = ALIASES.get(normalized, normalized)
        out[target] = value
    return out


def normalize_props(raw: Dict[str, Any] | None) -> Dict[str, Any]:
    aliased = _aliasize(raw or {})
    canonical = extract_canonical_fields(raw or {})
    _normalize_approved_fields(aliased)

    for key, value in canonical.items():
        if key == "processes":
            continue
        if value is not None and (key not in aliased or aliased.get(key) in ("", None)):
            aliased[key] = value

    processes = list(canonical.get("processes") or [])
    aliased["processes"] = processes
    aliased["process"] = processes[0] if processes else _as_str(aliased.get("process", ""))
    if len(processes) > 1:
        aliased["process2"] = processes[1]
    else:
        aliased["process2"] = _as_str(aliased.get("process2", ""))
    if len(processes) > 2:
        aliased["process3"] = processes[2]
    else:
        aliased["process3"] = _as_str(aliased.get("process3", ""))

    for key in REQUIRED_KEYS:
        if key == "processes":
            continue
        aliased[key] = _as_str(aliased.get(key, ""))

    aliased["revision"] = _as_str(aliased.get("revision", ""))
    return aliased


def harvest_part_attrs(part) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}

    raw_attrs = dict(getattr(part, "attrs", {}) or {})
    merged.update(raw_attrs)

    if hasattr(part, "props") and isinstance(part.props, dict):
        for key, value in (part.props or {}).items():
            if key not in merged:
                merged[key] = value

    canonical = canonical_attrs_for_part(part, raw_attrs=raw_attrs) if part else {}
    for key, value in canonical.items():
        if key in {"approved", "approved_by", "approved_date"}:
            continue
        if key == "processes":
            if value and not merged.get("processes"):
                merged["processes"] = list(value)
            continue
        if value is not None and merged.get(key) in (None, ""):
            merged[key] = value

    mirrors = {
        "description": getattr(part, "description", None),
        "revision": getattr(part, "revision", None),
        "category": getattr(part, "category", None),
        "uom": getattr(part, "uom", None),
    }
    for key, value in mirrors.items():
        if value is not None and merged.get(key) in (None, ""):
            merged[key] = value

    raw_approval = resolve_approval(merged)
    if not raw_approval.get("has_approval_signal"):
        for key in ("approved", "approved_by", "approved_date"):
            value = canonical.get(key)
            if value not in (None, ""):
                merged[key] = value
    _normalize_approved_fields(merged)
    return merged


def merge_save_part_attrs(part, incoming: Dict[str, Any]) -> None:
    part.attrs = normalize_record_attrs(incoming)
    sync_part_canonical_fields(part, raw_attrs=part.attrs)
    part.save()

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from app.services.canonical_fields import (
    APPROVAL_VOID_RE,
    APPROVED_BY_ATTR_ALIASES,
    APPROVED_DATE_ATTR_ALIASES,
    approved_by_attr_value,
    approved_date_attr_value,
    canonical_attr_key,
    canonical_attrs_for_part,
    default_normalized_attr_alias_map,
    extract_canonical_fields,
    is_blankish_approval,
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

def _is_blankish_approval(value: Any) -> bool:
    return is_blankish_approval(value)


def _is_blankish_text(value: Any) -> bool:
    if value is None:
        return True
    return not str(value).strip()


def approval_query_keys(*, include_canonical: bool = True, include_legacy: bool = True) -> List[str]:
    keys: List[str] = []
    if include_canonical:
        keys.extend(["canonical.approved_by", "attrs.approved_by"])
    if include_legacy:
        keys.extend(["attrs.approvedby", "attrs.approved"])
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

    if approved:
        return {
            "$or": [
                {
                    "$and": [
                        {field: {"$exists": True}},
                        {field: {"$nin": [None, False, 0]}},
                        {field: {"$not": APPROVAL_VOID_RE}},
                    ]
                }
                for field in fields
            ]
        }

    return {
        "$and": [
            {
                "$or": [
                    {field: {"$exists": False}},
                    {field: {"$in": [None, False, 0]}},
                    {field: APPROVAL_VOID_RE},
                ]
            }
            for field in fields
        ]
    }


def approved_by_value(attrs: Dict[str, Any]) -> Any:
    return approved_by_attr_value(attrs)


def approved_date_value(attrs: Dict[str, Any]) -> Any:
    return approved_date_attr_value(attrs)


def approved_value(attrs: Dict[str, Any]) -> Any:
    return approved_by_value(attrs)


def _normalize_alias_group(attrs: Dict[str, Any], aliases: Iterable[str], canonical_key: str, *, blankish) -> None:
    if not isinstance(attrs, dict):
        return
    alias_tokens = {canonical_attr_key(alias) for alias in aliases if canonical_attr_key(alias)}
    matching_keys = [key for key in list(attrs.keys()) if canonical_attr_key(key) in alias_tokens]
    value = None
    if tuple(aliases) == tuple(APPROVED_BY_ATTR_ALIASES):
        value = approved_by_value(attrs)
    elif tuple(aliases) == tuple(APPROVED_DATE_ATTR_ALIASES):
        value = approved_date_value(attrs)
    else:
        for key in matching_keys:
            raw_value = attrs.get(key)
            if not blankish(raw_value):
                value = raw_value
                break
    for key in matching_keys:
        attrs.pop(key, None)
    if value is not None:
        attrs[canonical_key] = value


def _normalize_approved_fields(attrs: Dict[str, Any]) -> None:
    _normalize_alias_group(attrs, APPROVED_BY_ATTR_ALIASES, "approved_by", blankish=_is_blankish_approval)
    _normalize_alias_group(attrs, APPROVED_DATE_ATTR_ALIASES, "approved_date", blankish=_is_blankish_text)


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

    _normalize_approved_fields(merged)
    return merged


def merge_save_part_attrs(part, incoming: Dict[str, Any]) -> None:
    part.attrs = normalize_record_attrs(incoming)
    sync_part_canonical_fields(part, raw_attrs=part.attrs)
    part.save()

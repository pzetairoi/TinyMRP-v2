from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

from app.services.canonical_fields import (
    canonical_attr_key,
    canonical_attrs_for_part,
    default_normalized_attr_alias_map,
    extract_canonical_fields,
    sync_part_canonical_fields,
)

ALIASES: Dict[str, str] = default_normalized_attr_alias_map()

REQUIRED_KEYS: Iterable[str] = (
    "approvedby",
    "approveddate",
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

# Add default title-block placeholder tokens here so approval remains based on
# meaningful approver data rather than field-label defaults.
_APPROVAL_EMPTY = {
    "",
    "-",
    "--",
    "0",
    "approved",
    "approved by",
    "approved_by",
    "approver",
    "false",
    "n/a",
    "na",
    "none",
    "null",
    "pending",
    "tbc",
    "tbd",
}
_APPROVAL_EMPTY_RE = re.compile(
    r"^\s*(?:"
    + "|".join(sorted(re.escape(token) for token in _APPROVAL_EMPTY))
    + r")\s*$",
    re.IGNORECASE,
)


def _is_blankish_approval(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return not value
    return bool(_APPROVAL_EMPTY_RE.match(str(value)))


def approval_filter_raw(keys: Iterable[str], *, approved: bool) -> Dict[str, Any]:
    fields = [str(key or "").strip() for key in keys if str(key or "").strip()]
    if not fields:
        return {}

    if approved:
        return {
            "$or": [
                {
                    "$and": [
                        {field: {"$exists": True}},
                        {field: {"$nin": [None, False, 0]}},
                        {field: {"$not": _APPROVAL_EMPTY_RE}},
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
                    {field: _APPROVAL_EMPTY_RE},
                ]
            }
            for field in fields
        ]
    }


def approved_value(attrs: Dict[str, Any]) -> Any:
    if not isinstance(attrs, dict):
        return None
    for key in ("approvedby", "approved_by", "approved"):
        if key in attrs and not _is_blankish_approval(attrs.get(key)):
            return attrs.get(key)
    for key, value in attrs.items():
        key_l = canonical_attr_key(key)
        if key_l in ("approvedby", "approved_by", "approved") and not _is_blankish_approval(value):
            return value
    return None


def _normalize_approved_fields(attrs: Dict[str, Any]) -> None:
    if not isinstance(attrs, dict):
        return
    value = approved_value(attrs)
    if value is None:
        return
    attrs["approvedby"] = value
    attrs["approved_by"] = value
    attrs["approved"] = value


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
    attrs = dict(raw_attrs or {})
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
    part.attrs = dict(incoming or {})
    sync_part_canonical_fields(part, raw_attrs=part.attrs)
    part.save()

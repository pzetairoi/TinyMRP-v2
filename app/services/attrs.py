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

APPROVAL_QUERY_FIELD = "canonical.approved"


def approval_filter_raw(*, approved: bool) -> Dict[str, Any]:
    """Match parts by their stored approval boolean.

    Approval is resolved once on write (see ``extract_canonical_fields``),
    which is the only place aliases and blank-ish values are interpreted. Reads
    are therefore a single indexed equality test: anything not explicitly
    ``True`` is unapproved, so a part that has never been written by the
    resolver is fail-closed rather than treated as approved.
    """

    if approved:
        return {APPROVAL_QUERY_FIELD: True}
    return {APPROVAL_QUERY_FIELD: {"$ne": True}}


def approval_field_values(
    attrs: Dict[str, Any],
    *,
    part: Any = None,
) -> Dict[str, Any]:
    """Return the approval triple for a response payload.

    Prefers the boolean already resolved on write. ``attrs`` is only consulted
    for records that have not been through the resolver yet (previews and
    import planning), so a stored part and its filters can never disagree.
    """

    stored = getattr(part, "canonical", None) if part is not None else None
    if isinstance(stored, dict) and "approved" in stored:
        return {
            "approved": bool(stored.get("approved")),
            "approved_by": str(stored.get("approved_by") or "").strip(),
            "approved_date": str(stored.get("approved_date") or "").strip(),
        }
    approval = resolve_approval(attrs or {})
    return {
        "approved": bool(approval.get("approved")),
        "approved_by": str(approval.get("approved_by") or "").strip(),
        "approved_date": str(approval.get("approved_date") or "").strip(),
    }


# Derived from module-level constants, so these sets never change. Building
# them per call showed up while normalising a page of parts.
_APPROVAL_ALIAS_GROUPS: Dict[str, set[str]] = {
    target: {token for token in map(canonical_attr_key, aliases) if token}
    for target, aliases in (
        ("approved", APPROVED_STATUS_ATTR_ALIASES),
        ("approved_by", APPROVED_BY_ATTR_ALIASES),
        ("approved_date", APPROVED_DATE_ATTR_ALIASES),
    )
}


def _normalize_approved_fields(attrs: Dict[str, Any]) -> None:
    if not isinstance(attrs, dict):
        return
    approval = resolve_approval(attrs)
    preserved: Dict[str, List[Any]] = {key: [] for key in _APPROVAL_ALIAS_GROUPS}
    for key in list(attrs.keys()):
        token = canonical_attr_key(key)
        for target, aliases in _APPROVAL_ALIAS_GROUPS.items():
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

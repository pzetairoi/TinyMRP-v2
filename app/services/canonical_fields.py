from __future__ import annotations

import re
from copy import deepcopy
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

from flask import current_app, g, has_app_context

from app.models.app_settings import AppSettings
from app.models.part import Part
from app.services.processmeta import normalize_processes

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

APPROVED_FIELD_ID = "approved"
APPROVED_BY_FIELD_ID = "approved_by"
APPROVED_DATE_FIELD_ID = "approved_date"
APPROVED_STATUS_ATTR_ALIASES: tuple[str, ...] = ("approved", "is_approved", "approval_status", "released")
APPROVED_BY_ATTR_ALIASES: tuple[str, ...] = ("approvedby", "approved_by", "approver", "released_by")
APPROVED_DATE_ATTR_ALIASES: tuple[str, ...] = ("approveddate", "approved_date")
APPROVAL_TRUE_VALUES: set[str] = {
    "1",
    "approved",
    "released",
    "true",
    "y",
    "yes",
    "on",
}
APPROVAL_FALSE_VALUES: set[str] = {
    "",
    "-",
    "--",
    "0",
    "absent",
    "draft",
    "false",
    "in progress",
    "missing",
    "n/a",
    "na",
    "n",
    "no",
    "none",
    "not approved",
    "not-approved",
    "not_approved",
    "notapproved",
    "null",
    "off",
    "pending",
    "pending approval",
    "pending review",
    "rejected",
    "tbc",
    "tbd",
    "unapproved",
    "wip",
    "work in progress",
}
APPROVAL_IDENTITY_PLACEHOLDERS: set[str] = {
    "approved by",
    "approved_by",
    "approver",
}
APPROVAL_VOID_VALUES: set[str] = APPROVAL_FALSE_VALUES | APPROVAL_IDENTITY_PLACEHOLDERS
APPROVAL_VOID_RE = re.compile(
    r"^\s*(?:"
    + "|".join(sorted(re.escape(token) for token in APPROVAL_VOID_VALUES))
    + r")\s*$",
    re.IGNORECASE,
)

CANONICAL_FIELD_DEFINITIONS: List[Dict[str, Any]] = [
    {"field_id": "description", "label": "Description", "aliases": ["description", "desc", "desc1", "summary_text"]},
    {"field_id": "revision", "label": "Revision", "aliases": ["revision", "rev"]},
    {"field_id": "category", "label": "Category", "aliases": ["category"]},
    {"field_id": "material", "label": "Material", "aliases": ["material"]},
    {"field_id": "finish", "label": "Finish", "aliases": ["finish", "treatment", "colour", "color"]},
    {"field_id": "mass", "label": "Mass", "aliases": ["mass", "weight"]},
    {"field_id": "uom", "label": "UoM", "aliases": ["uom", "unit", "unit_of_measure"]},
    {"field_id": "link", "label": "Link", "aliases": ["link", "oem_internet", "oem_link"]},
    {"field_id": "oem", "label": "OEM", "aliases": ["oem", "manufacturer", "oem_supplier"]},
    {
        "field_id": "oem_partnumber",
        "label": "OEM Part Number",
        "aliases": ["oem_partnumber", "oem_part_number", "supplier_partnumber", "supplier_part_number"],
    },
    {
        "field_id": "datasheet",
        "label": "Datasheet",
        "aliases": ["datasheet", "oem_data_sheet", "oem_datasheet", "data_sheet", "datasheet_url"],
    },
    {"field_id": "classified", "label": "Classified", "aliases": ["classified"]},
    {"field_id": APPROVED_FIELD_ID, "label": "Approved Status", "aliases": list(APPROVED_STATUS_ATTR_ALIASES)},
    {"field_id": APPROVED_BY_FIELD_ID, "label": "Approved By", "aliases": list(APPROVED_BY_ATTR_ALIASES)},
    {"field_id": APPROVED_DATE_FIELD_ID, "label": "Approved Date", "aliases": list(APPROVED_DATE_ATTR_ALIASES)},
    {"field_id": "drawn_by", "label": "Drawn By", "aliases": ["drawnby", "drawn_by"]},
    {"field_id": "drawn_date", "label": "Drawn Date", "aliases": ["drawndate", "drawn_date"]},
    {"field_id": "checked_by", "label": "Checked By", "aliases": ["checkedby", "checked_by"]},
    {"field_id": "checked_date", "label": "Checked Date", "aliases": ["checkeddate", "checked_date"]},
    {"field_id": "manufacturer", "label": "Manufacturer", "aliases": ["manufacturer"]},
    {"field_id": "mfr_part", "label": "Manufacturer Part", "aliases": ["mfr_part", "manufacturer_part"]},
    {
        "field_id": "process",
        "label": "Process",
        "aliases": [
            "process",
            "processes",
            "process2",
            "process3",
            "secondprocess",
            "thirdprocess",
            "second_process",
            "third_process",
            "second process",
            "third process",
        ],
        "multi_value": True,
    },
]

_DEF_BY_ID = {item["field_id"]: item for item in CANONICAL_FIELD_DEFINITIONS}
_TOP_LEVEL_MIRRORS = {
    "description": "description",
    "revision": "revision",
    "category": "category",
    "uom": "uom",
    "manufacturer": "manufacturer",
    "mfr_part": "mfr_part",
}
_DEFAULT_NORMALIZED_ATTR_ALIASES: Dict[str, str] = {
    "approvedby": "approved_by",
    "approved": "approved",
    "is_approved": "approved",
    "approval_status": "approved",
    "approved_by": "approved_by",
    "approveddate": "approved_date",
    "approveddate_": "approved_date",
    "approvedby_": "approved_by",
    "drawnby": "drawnby",
    "drawnby_": "drawnby",
    "drawndate": "drawndate",
    "checkedby": "checkedby",
    "checkeddate": "checkeddate",
    "checkeddate_": "checkeddate",
    "classified": "classified",
    "category": "category",
    "configuration": "configuration",
    "sw_configuration": "configuration",
    "datasheet": "datasheet",
    "oem_data_sheet": "datasheet",
    "oem_datasheet": "datasheet",
    "data_sheet": "datasheet",
    "datasheet_url": "datasheet",
    "description": "description",
    "file": "file",
    "finish": "finish",
    "folder": "folder",
    "link": "link",
    "oem_internet": "link",
    "oem_link": "link",
    "mass": "mass",
    "weight": "mass",
    "material": "material",
    "oem": "oem",
    "manufacturer": "oem",
    "oem_partnumber": "oem_partnumber",
    "oem_part_number": "oem_partnumber",
    "mfr_part": "oem_partnumber",
    "process": "process",
    "processes": "processes",
    "secondprocess": "process2",
    "thirdprocess": "process3",
    "process2": "process2",
    "process3": "process3",
    "revision": "revision",
    "rev": "revision",
    "spare_part": "spare_part",
}


@lru_cache(maxsize=4096)
def _canonical_attr_key_normalized(text: str) -> str:
    return _NON_ALNUM.sub("_", text).strip("_")


def canonical_attr_key(value: Any) -> str:
    # Hot path: called per (attrs key x alias) pair while resolving approval/
    # canonical fields for every row. The regex substitution is memoized on
    # the coerced string so callers can still pass any value.
    text = str(value or "").strip().lower()
    return _canonical_attr_key_normalized(text)


def is_blankish_approval(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return not value
    if isinstance(value, (list, tuple, set)):
        return not any(not is_blankish_approval(item) for item in value)
    if isinstance(value, dict):
        return not bool(value)
    return bool(APPROVAL_VOID_RE.match(str(value)))


def default_normalized_attr_alias_map() -> Dict[str, str]:
    return dict(_DEFAULT_NORMALIZED_ATTR_ALIASES)


def default_canonical_alias_entries() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in CANONICAL_FIELD_DEFINITIONS:
        aliases = [canonical_attr_key(alias) for alias in item.get("aliases", []) if canonical_attr_key(alias)]
        field_id = item["field_id"]
        field_key = canonical_attr_key(field_id)
        aliases = [field_key] + [alias for alias in aliases if alias != field_key]
        out.append(
            {
                "field_id": field_id,
                "label": item["label"],
                "multi_value": bool(item.get("multi_value")),
                "aliases": aliases,
            }
        )
    return out


def default_approval_rules() -> Dict[str, List[str]]:
    return {
        "approved_values": sorted(APPROVAL_TRUE_VALUES),
        "unapproved_values": sorted(APPROVAL_FALSE_VALUES),
        "identity_placeholders": sorted(APPROVAL_IDENTITY_PLACEHOLDERS),
    }


def _normalize_approval_rule_values(values: Any, defaults: Iterable[str]) -> List[str]:
    if isinstance(values, str):
        raw_items: Iterable[Any] = re.split(r"[,;\r\n]+", values)
    elif isinstance(values, (list, tuple, set)):
        raw_items = values
    else:
        raw_items = defaults
    seen: set[str] = set()
    out: List[str] = []
    for value in raw_items:
        raw_token = str(value or "").strip().lower()
        token = raw_token if re.fullmatch(r"-+", raw_token) else re.sub(r"\s+", " ", raw_token.replace("_", " ").replace("-", " "))
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def sanitize_approval_rules(raw: Any) -> Dict[str, List[str]]:
    source = raw if isinstance(raw, dict) else {}
    defaults = default_approval_rules()
    approved = _normalize_approval_rule_values(
        source.get("approved_values") if "approved_values" in source else None,
        defaults["approved_values"],
    )
    unapproved = _normalize_approval_rule_values(
        source.get("unapproved_values") if "unapproved_values" in source else None,
        defaults["unapproved_values"],
    )
    placeholders = _normalize_approval_rule_values(
        source.get("identity_placeholders") if "identity_placeholders" in source else None,
        defaults["identity_placeholders"],
    )
    # A negative or placeholder rule is conservative and wins collisions.
    blocked = set(unapproved) | set(placeholders)
    approved = [value for value in approved if value not in blocked]
    return {
        "approved_values": approved,
        "unapproved_values": unapproved,
        "identity_placeholders": placeholders,
    }


def approval_rules_from_field_config(config: Optional[Dict[str, Any]]) -> Dict[str, List[str]]:
    if not isinstance(config, dict):
        return default_approval_rules()
    return sanitize_approval_rules(config.get("approval_rules"))


def _settings_doc(create: bool = False) -> Optional[AppSettings]:
    settings = AppSettings.objects().order_by("-updated_at").first()
    if settings or not create:
        return settings
    settings = AppSettings()
    settings.save()
    return settings


def _normalize_alias_list(values: Any, field_id: str) -> List[str]:
    raw_items: Iterable[Any]
    if isinstance(values, str):
        raw_items = re.split(r"[,;\r\n]+", values)
    elif isinstance(values, (list, tuple, set)):
        raw_items = values
    else:
        raw_items = []

    seen = set()
    out: List[str] = []
    base_key = canonical_attr_key(field_id)
    for item in raw_items:
        token = canonical_attr_key(item)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    if base_key and base_key not in seen:
        out.insert(0, base_key)
    return out


def sanitize_canonical_alias_entries(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, dict):
        raw_index = {canonical_attr_key(key): value for key, value in raw.items()}
    elif isinstance(raw, list):
        raw_index = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            field_id = canonical_attr_key(item.get("field_id") or item.get("id"))
            if field_id:
                raw_index[field_id] = item.get("aliases")
    else:
        raw_index = {}

    defaults = default_canonical_alias_entries()
    out: List[Dict[str, Any]] = []
    for item in defaults:
        field_id = item["field_id"]
        aliases = _normalize_alias_list(raw_index.get(field_id, item.get("aliases") or []), field_id)
        out.append(
            {
                "field_id": field_id,
                "label": item["label"],
                "multi_value": bool(item.get("multi_value")),
                "aliases": aliases,
            }
        )
    # Canonical field ids own their names, and a raw alias may map to only one
    # canonical field. This makes collisions deterministic and migrates the
    # legacy `approved` alias from approved_by to the status field.
    reserved = {canonical_attr_key(item["field_id"]) for item in out}
    claimed: set[str] = set()
    for item in out:
        field_key = canonical_attr_key(item["field_id"])
        unique_aliases: List[str] = []
        for alias in item.get("aliases") or []:
            token = canonical_attr_key(alias)
            if not token:
                continue
            if token in reserved and token != field_key:
                continue
            if token in claimed:
                continue
            claimed.add(token)
            unique_aliases.append(token)
        if field_key not in unique_aliases:
            unique_aliases.insert(0, field_key)
            claimed.add(field_key)
        item["aliases"] = unique_aliases
    return out


def canonical_alias_entries_from_field_config(config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(config, dict):
        return default_canonical_alias_entries()
    return sanitize_canonical_alias_entries(config.get("canonical_aliases"))


def set_runtime_canonical_aliases(config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    aliases = canonical_alias_entries_from_field_config(config)
    if has_app_context():
        g._canonical_field_aliases = deepcopy(aliases)
        g._canonical_field_aliases_snapshot = aliases
        approval_rules = approval_rules_from_field_config(config)
        g._approval_rules = deepcopy(approval_rules)
        g._approval_rules_snapshot = approval_rules
    return aliases


def get_runtime_canonical_aliases() -> List[Dict[str, Any]]:
    # Every caller of this function only reads the returned list (verified: no
    # mutation anywhere in this module). Re-deepcopying on every call was
    # previously the dominant cost of resolving fields for a page of parts
    # (called ~3-4x per row via resolve_approval()). Deepcopy once per
    # request/app-context and hand out that same read-only snapshot to every
    # caller within it.
    if has_app_context():
        snapshot = getattr(g, "_canonical_field_aliases_snapshot", None)
        if isinstance(snapshot, list) and snapshot:
            return snapshot
        cached = getattr(g, "_canonical_field_aliases", None)
        if isinstance(cached, list) and cached:
            snapshot = deepcopy(cached)
            g._canonical_field_aliases_snapshot = snapshot
            return snapshot

    settings = _settings_doc(create=False)
    stored = getattr(settings, "field_config", None) if settings else None
    aliases = canonical_alias_entries_from_field_config(stored if isinstance(stored, dict) else {})
    if has_app_context():
        g._canonical_field_aliases = deepcopy(aliases)
        g._canonical_field_aliases_snapshot = aliases
        g._approval_rules = deepcopy(approval_rules_from_field_config(stored if isinstance(stored, dict) else {}))
    return aliases


def get_runtime_approval_rules() -> Dict[str, List[str]]:
    # Same read-only-caller reasoning as get_runtime_canonical_aliases() above:
    # deepcopy once per request and reuse, instead of once per call.
    if has_app_context():
        snapshot = getattr(g, "_approval_rules_snapshot", None)
        if isinstance(snapshot, dict):
            return snapshot
        cached = getattr(g, "_approval_rules", None)
        if isinstance(cached, dict):
            snapshot = deepcopy(cached)
            g._approval_rules_snapshot = snapshot
            return snapshot
        get_runtime_canonical_aliases()
        cached = getattr(g, "_approval_rules", None)
        if isinstance(cached, dict):
            snapshot = deepcopy(cached)
            g._approval_rules_snapshot = snapshot
            return snapshot
    settings = _settings_doc(create=False)
    stored = getattr(settings, "field_config", None) if settings else None
    return approval_rules_from_field_config(stored if isinstance(stored, dict) else {})


def approval_void_regex(config: Optional[Dict[str, Any]] = None) -> re.Pattern[str]:
    """Build an exact negative/placeholder matcher from the active admin rules."""
    rules = approval_rules_from_field_config(config) if isinstance(config, dict) else get_runtime_approval_rules()
    patterns = [""]  # Blank approval fields are always unapproved.
    for value in [*(rules.get("unapproved_values") or []), *(rules.get("identity_placeholders") or [])]:
        token = str(value or "").strip()
        if not token:
            continue
        if re.fullmatch(r"-+", token):
            pattern = re.escape(token)
        else:
            words = [re.escape(word) for word in re.split(r"[\s_-]+", token) if word]
            pattern = r"[\s_-]+".join(words)
        if pattern and pattern not in patterns:
            patterns.append(pattern)
    return re.compile(r"^\s*(?:" + "|".join(patterns) + r")\s*$", re.IGNORECASE)


def _alias_lookups(
    entries: List[Dict[str, Any]],
) -> tuple[Dict[str, str], Dict[str, List[str]]]:
    """Derive the alias->field and field->aliases lookups in one pass.

    Both are pure functions of ``entries``. Rebuilding them per call made
    resolving a page of parts O(rows x fields x aliases); the per-request memo
    below keeps it O(entries) once. Keyed on the entries' identity so a config
    change (which produces a new list) invalidates on its own.
    """

    by_alias: Dict[str, str] = {}
    by_field: Dict[str, List[str]] = {}
    for item in entries:
        raw_field_id = str(item.get("field_id") or "").strip()
        aliases = [
            token
            for token in (canonical_attr_key(alias) for alias in item.get("aliases") or [])
            if token
        ]
        by_field.setdefault(canonical_attr_key(item.get("field_id")), aliases)
        if not raw_field_id:
            continue
        for token in aliases:
            if token not in by_alias:
                by_alias[token] = raw_field_id
    return by_alias, by_field


def _cached_alias_lookups(
    config: Optional[Dict[str, Any]] = None,
) -> tuple[Dict[str, str], Dict[str, List[str]]]:
    if isinstance(config, dict):
        return _alias_lookups(canonical_alias_entries_from_field_config(config))
    entries = get_runtime_canonical_aliases()
    if not has_app_context():
        return _alias_lookups(entries)
    cached = getattr(g, "_canonical_alias_lookups", None)
    if cached is not None and cached[0] is entries:
        return cached[1]
    lookups = _alias_lookups(entries)
    g._canonical_alias_lookups = (entries, lookups)
    return lookups


def canonical_alias_index(config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    return _cached_alias_lookups(config)[0]


def canonical_field_for_attr_key(raw_key: Any, config: Optional[Dict[str, Any]] = None) -> str:
    return canonical_alias_index(config).get(canonical_attr_key(raw_key), "")


def canonical_aliases_for_field(field_id: str, config: Optional[Dict[str, Any]] = None) -> List[str]:
    target = canonical_attr_key(field_id)
    # An entry with no usable aliases falls back to the field id itself, as
    # does a field with no entry at all.
    return _cached_alias_lookups(config)[1].get(target) or ([target] if target else [])


def _approval_text_token(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if re.fullmatch(r"-+", raw):
        return raw
    return re.sub(r"\s+", " ", raw.replace("_", " ").replace("-", " "))


_APPROVAL_FALSE_TOKENS = {_approval_text_token(item) for item in APPROVAL_FALSE_VALUES}
_APPROVAL_TRUE_TOKENS = {_approval_text_token(item) for item in APPROVAL_TRUE_VALUES}
def _approval_scalar_status(
    value: Any,
    *,
    true_tokens: Optional[set[str]] = None,
    false_tokens: Optional[set[str]] = None,
) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if not isinstance(value, str):
        return None
    token = _approval_text_token(value)
    if not token:
        return None
    if token in (false_tokens if false_tokens is not None else _APPROVAL_FALSE_TOKENS):
        return False
    if token in (true_tokens if true_tokens is not None else _APPROVAL_TRUE_TOKENS):
        return True
    return None


def _canonical_attr_index(attrs: Dict[str, Any]) -> Dict[str, List[tuple[str, Any]]]:
    """Group an attrs mapping by canonical key, preserving insertion order.

    Canonicalising every attrs key once per call keeps approval resolution
    linear; the previous per-alias rescan made it O(aliases x attrs) on a path
    that runs for every row of every parts and BOM listing.
    """
    index: Dict[str, List[tuple[str, Any]]] = {}
    for raw_key, raw_value in (attrs or {}).items():
        index.setdefault(canonical_attr_key(raw_key), []).append((str(raw_key), raw_value))
    return index


def _iter_approval_values(attrs: Dict[str, Any], aliases: Iterable[str]) -> List[tuple[str, Any]]:
    return _iter_approval_values_indexed(_canonical_attr_index(attrs), aliases)


def _iter_approval_values_indexed(
    index: Dict[str, List[tuple[str, Any]]],
    aliases: Iterable[str],
) -> List[tuple[str, Any]]:
    out: List[tuple[str, Any]] = []
    seen_keys: set[str] = set()
    for alias in aliases:
        token = canonical_attr_key(alias)
        if not token:
            continue
        for raw_key, raw_value in index.get(token, ()):
            if raw_key not in seen_keys:
                seen_keys.add(raw_key)
                out.append((raw_key, raw_value))
    return out


def _flatten_approval_value(value: Any) -> List[Any]:
    if isinstance(value, (list, tuple, set)):
        out: List[Any] = []
        for item in value:
            out.extend(_flatten_approval_value(item))
        return out
    return [value]


def resolve_approval(
    attrs: Optional[Dict[str, Any]],
    *,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Resolve approval once for imports, canonical fields, APIs, filters and files."""
    raw = dict(attrs or {})
    rules = approval_rules_from_field_config(config) if isinstance(config, dict) else get_runtime_approval_rules()
    false_tokens = set(rules.get("unapproved_values") or [])
    true_tokens = set(rules.get("approved_values") or [])
    placeholder_tokens = set(rules.get("identity_placeholders") or [])
    # Build the canonical index once and reuse it for all three approval fields.
    index = _canonical_attr_index(raw)
    status_values = _iter_approval_values_indexed(index, canonical_aliases_for_field(APPROVED_FIELD_ID, config))
    identity_values = _iter_approval_values_indexed(index, canonical_aliases_for_field(APPROVED_BY_FIELD_ID, config))
    date_values = _iter_approval_values_indexed(index, canonical_aliases_for_field(APPROVED_DATE_FIELD_ID, config))

    explicit_statuses: List[bool] = []
    approved_by = ""
    status_source = ""
    identity_source = ""
    ambiguous: List[Dict[str, str]] = []

    for raw_key, raw_value in status_values:
        for value in _flatten_approval_value(raw_value):
            if isinstance(value, dict):
                if value:
                    ambiguous.append({"source": raw_key, "reason": "unsupported_approval_value"})
                continue
            status = _approval_scalar_status(value, true_tokens=true_tokens, false_tokens=false_tokens)
            if status is not None:
                explicit_statuses.append(status)
                if not status_source:
                    status_source = raw_key
                continue
            text = str(value or "").strip()
            token = _approval_text_token(text)
            if not text:
                continue
            if token in placeholder_tokens:
                explicit_statuses.append(False)
                if not status_source:
                    status_source = raw_key
                continue
            # Legacy `approved` fields sometimes contain a person's name rather
            # than a boolean. Preserve that useful identity while recording it
            # as an implicit approval.
            if not approved_by:
                approved_by = text
                identity_source = raw_key
            elif approved_by.casefold() != text.casefold():
                ambiguous.append({"source": raw_key, "reason": "conflicting_approver_identity"})

    for raw_key, raw_value in identity_values:
        for value in _flatten_approval_value(raw_value):
            if isinstance(value, dict):
                if value:
                    ambiguous.append({"source": raw_key, "reason": "unsupported_approval_value"})
                continue
            status = _approval_scalar_status(value, true_tokens=true_tokens, false_tokens=false_tokens)
            if status is not None:
                explicit_statuses.append(status)
                if not status_source:
                    status_source = raw_key
                continue
            text = str(value or "").strip()
            token = _approval_text_token(text)
            if not text:
                continue
            if token in placeholder_tokens:
                explicit_statuses.append(False)
                if not status_source:
                    status_source = raw_key
                continue
            if not approved_by:
                approved_by = text
                identity_source = raw_key
            elif approved_by.casefold() != text.casefold():
                ambiguous.append({"source": raw_key, "reason": "conflicting_approver_identity"})

    approved_date = ""
    date_source = ""
    for raw_key, raw_value in date_values:
        for value in _flatten_approval_value(raw_value):
            text = str(value or "").strip()
            if text:
                approved_date = text
                date_source = raw_key
                break
        if approved_date:
            break

    # An explicit negative status is authoritative. Otherwise either an
    # explicit positive status or a real approver identity establishes approval.
    if False in explicit_statuses and True in explicit_statuses:
        ambiguous.append({"source": status_source, "reason": "conflicting_approval_status"})
    approved = False if False in explicit_statuses else bool(True in explicit_statuses or approved_by)
    if not approved:
        approved_by = ""
        identity_source = ""

    return {
        "approved": approved,
        "approved_by": approved_by,
        "approved_date": approved_date,
        "status_source": status_source,
        "identity_source": identity_source,
        "date_source": date_source,
        "has_approval_signal": bool(status_values or identity_values),
        "ambiguous": ambiguous,
    }


def approved_by_attr_value(attrs: Optional[Dict[str, Any]], *, config: Optional[Dict[str, Any]] = None) -> Any:
    result = resolve_approval(attrs, config=config)
    return result.get("approved_by") or (True if result.get("approved") else None)


def approved_date_attr_value(attrs: Optional[Dict[str, Any]], *, config: Optional[Dict[str, Any]] = None) -> Any:
    return resolve_approval(attrs, config=config).get("approved_date") or None


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _process_meta(meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if isinstance(meta, dict):
        return meta
    if has_app_context():
        return current_app.config.get("PROCESS_META", {}) or {}
    return {}


def extract_canonical_fields(
    raw_attrs: Optional[Dict[str, Any]],
    *,
    config: Optional[Dict[str, Any]] = None,
    process_meta: Optional[Dict[str, Any]] = None,
    top_level: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    attrs = dict(raw_attrs or {})
    alias_index = canonical_alias_index(config)
    canonical: Dict[str, Any] = {}
    process_values: List[Any] = []

    for raw_key, raw_value in attrs.items():
        field_id = alias_index.get(canonical_attr_key(raw_key))
        if not field_id or not _has_value(raw_value):
            continue
        if field_id in {APPROVED_FIELD_ID, APPROVED_BY_FIELD_ID, APPROVED_DATE_FIELD_ID}:
            continue
        if field_id == "process":
            process_values.append(raw_value)
            continue
        if field_id not in canonical:
            canonical[field_id] = raw_value

    top = dict(top_level or {})
    for field_id, value in top.items():
        if field_id == "process":
            process_values.append(value)
            continue
        if _has_value(value):
            canonical[field_id] = value

    approval = resolve_approval(attrs, config=config)
    canonical[APPROVED_FIELD_ID] = bool(approval.get("approved"))
    if approval.get("approved_by"):
        canonical[APPROVED_BY_FIELD_ID] = approval["approved_by"]
    if approval.get("approved_date"):
        canonical[APPROVED_DATE_FIELD_ID] = approval["approved_date"]

    processes = normalize_processes({"processes": process_values}, _process_meta(process_meta))
    if not processes:
        top_processes = top.get("processes")
        if _has_value(top_processes):
            processes = normalize_processes({"processes": top_processes}, _process_meta(process_meta))
    canonical["processes"] = processes
    return canonical


def canonical_attrs_for_part(
    part: Optional[Part],
    *,
    raw_attrs: Optional[Dict[str, Any]] = None,
    process_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not part:
        return {}

    current = dict(getattr(part, "canonical", {}) or {})
    raw = raw_attrs if isinstance(raw_attrs, dict) else getattr(part, "attrs", {}) or {}
    top_level = {
        field_id: getattr(part, attr_name, None)
        for field_id, attr_name in _TOP_LEVEL_MIRRORS.items()
    }
    top_level["processes"] = list(getattr(part, "processes", None) or [])

    if current:
        merged = dict(current)
        for field_id, value in top_level.items():
            if field_id == "processes":
                if not merged.get("processes") and _has_value(value):
                    merged["processes"] = normalize_processes({"processes": value}, _process_meta(process_meta))
                continue
            if not _has_value(merged.get(field_id)) and _has_value(value):
                merged[field_id] = value

        approval = resolve_approval(raw)
        if approval.get("has_approval_signal"):
            merged[APPROVED_FIELD_ID] = bool(approval.get("approved"))
            if approval.get("approved_by"):
                merged[APPROVED_BY_FIELD_ID] = approval["approved_by"]
            else:
                merged.pop(APPROVED_BY_FIELD_ID, None)
        if approval.get("approved_date"):
            merged[APPROVED_DATE_FIELD_ID] = approval["approved_date"]
        elif APPROVED_FIELD_ID not in merged:
            current_approval = resolve_approval(current)
            merged[APPROVED_FIELD_ID] = bool(current_approval.get("approved"))
            if current_approval.get("approved_by"):
                merged[APPROVED_BY_FIELD_ID] = current_approval["approved_by"]
        return merged

    return extract_canonical_fields(
        raw,
        process_meta=process_meta,
        top_level=top_level,
    )


def canonical_processes_for_part(
    part: Optional[Part],
    *,
    raw_attrs: Optional[Dict[str, Any]] = None,
    process_meta: Optional[Dict[str, Any]] = None,
) -> List[str]:
    canonical = canonical_attrs_for_part(part, raw_attrs=raw_attrs, process_meta=process_meta)
    values = canonical.get("processes")
    return normalize_processes({"processes": values}, _process_meta(process_meta)) if _has_value(values) else []


def canonical_process_label_for_part(
    part: Optional[Part],
    *,
    raw_attrs: Optional[Dict[str, Any]] = None,
    process_meta: Optional[Dict[str, Any]] = None,
) -> str:
    return ", ".join(canonical_processes_for_part(part, raw_attrs=raw_attrs, process_meta=process_meta))


def sync_part_canonical_fields(
    part: Part,
    *,
    raw_attrs: Optional[Dict[str, Any]] = None,
    top_level_overrides: Optional[Dict[str, Any]] = None,
    process_meta: Optional[Dict[str, Any]] = None,
    process_override: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    raw = dict(raw_attrs if isinstance(raw_attrs, dict) else getattr(part, "attrs", {}) or {})
    top_level = {
        field_id: (top_level_overrides or {}).get(field_id, getattr(part, attr_name, None))
        for field_id, attr_name in _TOP_LEVEL_MIRRORS.items()
    }
    top_level["processes"] = list((top_level_overrides or {}).get("processes") or list(getattr(part, "processes", None) or []))

    canonical = extract_canonical_fields(raw, process_meta=process_meta, top_level=top_level)
    if process_override is not None:
        canonical["processes"] = normalize_processes({"processes": list(process_override or [])}, _process_meta(process_meta))

    for field_id, attr_name in _TOP_LEVEL_MIRRORS.items():
        value = canonical.get(field_id)
        if _has_value(value):
            setattr(part, attr_name, value)
        elif field_id == "revision":
            setattr(part, attr_name, "")

    part.canonical = canonical
    part.processes = list(canonical.get("processes") or [])
    return canonical


def rebuild_all_part_canonical_fields(*, process_meta: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    scanned = 0
    updated = 0
    for part in Part.objects():
        scanned += 1
        before_canonical = dict(getattr(part, "canonical", {}) or {})
        before_processes = list(getattr(part, "processes", None) or [])
        before_top = {
            attr_name: getattr(part, attr_name, None)
            for attr_name in _TOP_LEVEL_MIRRORS.values()
        }

        sync_part_canonical_fields(part, process_meta=process_meta)

        after_top = {
            attr_name: getattr(part, attr_name, None)
            for attr_name in _TOP_LEVEL_MIRRORS.values()
        }
        if (
            before_canonical != dict(getattr(part, "canonical", {}) or {})
            or before_processes != list(getattr(part, "processes", None) or [])
            or before_top != after_top
        ):
            part.save()
            updated += 1
    return {"scanned": scanned, "updated": updated}

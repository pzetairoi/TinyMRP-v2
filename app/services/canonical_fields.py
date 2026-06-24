from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from flask import current_app, has_app_context

from app.models.app_settings import AppSettings
from app.models.part import Part
from app.services.processmeta import normalize_processes

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

APPROVED_BY_FIELD_ID = "approved_by"
APPROVED_DATE_FIELD_ID = "approved_date"
APPROVED_BY_ATTR_ALIASES: tuple[str, ...] = ("approvedby", "approved_by", "approved")
APPROVED_DATE_ATTR_ALIASES: tuple[str, ...] = ("approveddate", "approved_date")
APPROVAL_VOID_VALUES: set[str] = {
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
    "approved": "approved_by",
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


def canonical_attr_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = _NON_ALNUM.sub("_", text)
    return text.strip("_")


def is_blankish_approval(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return not value
    return bool(APPROVAL_VOID_RE.match(str(value)))


def _is_blankish_text(value: Any) -> bool:
    if value is None:
        return True
    return not str(value).strip()


def _first_alias_value(attrs: Optional[Dict[str, Any]], aliases: Iterable[str], *, blankish) -> Any:
    if not isinstance(attrs, dict):
        return None
    items = list(attrs.items())
    tokens = [canonical_attr_key(alias) for alias in aliases if canonical_attr_key(alias)]
    for token in tokens:
        for raw_key, raw_value in items:
            if canonical_attr_key(raw_key) == token and not blankish(raw_value):
                return raw_value
    return None


def approved_by_attr_value(attrs: Optional[Dict[str, Any]]) -> Any:
    return _first_alias_value(attrs, APPROVED_BY_ATTR_ALIASES, blankish=is_blankish_approval)


def approved_date_attr_value(attrs: Optional[Dict[str, Any]]) -> Any:
    return _first_alias_value(attrs, APPROVED_DATE_ATTR_ALIASES, blankish=_is_blankish_text)


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
    return out


def canonical_alias_entries_from_field_config(config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(config, dict):
        return default_canonical_alias_entries()
    return sanitize_canonical_alias_entries(config.get("canonical_aliases"))


def set_runtime_canonical_aliases(config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    aliases = canonical_alias_entries_from_field_config(config)
    if has_app_context():
        current_app.config["CANONICAL_FIELD_ALIASES"] = deepcopy(aliases)
    return aliases


def get_runtime_canonical_aliases() -> List[Dict[str, Any]]:
    if has_app_context():
        cached = current_app.config.get("CANONICAL_FIELD_ALIASES")
        if isinstance(cached, list) and cached:
            return deepcopy(cached)

    settings = _settings_doc(create=False)
    stored = getattr(settings, "field_config", None) if settings else None
    aliases = canonical_alias_entries_from_field_config(stored if isinstance(stored, dict) else {})
    if has_app_context():
        current_app.config["CANONICAL_FIELD_ALIASES"] = deepcopy(aliases)
    return aliases


def canonical_alias_index(config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    entries = canonical_alias_entries_from_field_config(config) if isinstance(config, dict) else get_runtime_canonical_aliases()
    out: Dict[str, str] = {}
    for item in entries:
        field_id = str(item.get("field_id") or "").strip()
        if not field_id:
            continue
        for alias in item.get("aliases") or []:
            token = canonical_attr_key(alias)
            if token and token not in out:
                out[token] = field_id
    return out


def canonical_field_for_attr_key(raw_key: Any, config: Optional[Dict[str, Any]] = None) -> str:
    return canonical_alias_index(config).get(canonical_attr_key(raw_key), "")


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

    approved_by = approved_by_attr_value(attrs)
    if approved_by is not None:
        canonical[APPROVED_BY_FIELD_ID] = approved_by
    else:
        canonical.pop(APPROVED_BY_FIELD_ID, None)

    approved_date = approved_date_attr_value(attrs)
    if approved_date is not None:
        canonical[APPROVED_DATE_FIELD_ID] = approved_date

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

        approved_by = approved_by_attr_value(raw)
        if approved_by is not None:
            merged[APPROVED_BY_FIELD_ID] = approved_by
        elif is_blankish_approval(merged.get(APPROVED_BY_FIELD_ID)):
            merged.pop(APPROVED_BY_FIELD_ID, None)

        approved_date = approved_date_attr_value(raw)
        if approved_date is not None:
            merged[APPROVED_DATE_FIELD_ID] = approved_date
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
    current = dict(getattr(part, "canonical", {}) or {})
    top_level = {
        field_id: (top_level_overrides or {}).get(field_id, getattr(part, attr_name, None))
        for field_id, attr_name in _TOP_LEVEL_MIRRORS.items()
    }
    top_level["processes"] = list((top_level_overrides or {}).get("processes") or list(getattr(part, "processes", None) or []))

    canonical = extract_canonical_fields(raw, process_meta=process_meta, top_level=top_level)
    if APPROVED_BY_FIELD_ID not in canonical:
        current_approved_by = current.get(APPROVED_BY_FIELD_ID)
        if _has_value(current_approved_by) and not is_blankish_approval(current_approved_by):
            canonical[APPROVED_BY_FIELD_ID] = current_approved_by
    if APPROVED_DATE_FIELD_ID not in canonical:
        current_approved_date = current.get(APPROVED_DATE_FIELD_ID)
        if _has_value(current_approved_date):
            canonical[APPROVED_DATE_FIELD_ID] = current_approved_date
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

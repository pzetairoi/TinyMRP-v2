from __future__ import annotations

import re
from copy import deepcopy
from datetime import date, datetime, time, timezone
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional

from flask import current_app, g, has_app_context

from app.models.app_settings import AppSettings
from app.models.part import Part
from app.services.attrs import ALIASES, canonical_attr_key, harvest_part_attrs, normalize_props
from app.services.canonical_fields import (
    approval_rules_from_field_config,
    canonical_alias_entries_from_field_config,
    canonical_field_for_attr_key,
    canonical_process_label_for_part,
    default_canonical_alias_entries,
    default_approval_rules,
    set_runtime_canonical_aliases,
)
from app.services.filescan import datasheet_attr_present, datasheet_url_from_attrs
from app.services.part_annotations import annotation_payload
from app.services.part_norm import clean_rev
from app.services.processmeta import normalize_processes
from app.services.timezone_utils import utc_now


_FIELD_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SOURCE_PATH_RE = re.compile(r"^(part|attrs)(?:\.[A-Za-z0-9_]+)+$")
_BOOLEAN_TRUE = {"1", "true", "yes", "on", "y"}
_BOOLEAN_FALSE = {"0", "false", "no", "off", "n", "missing", "none", "absent"}
_NUMBER_RANGE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:\.\.|to|-)\s*(-?\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
_NUMBER_COMPARE_RE = re.compile(r"^\s*(<=|>=|=|<|>)?\s*(-?\d+(?:\.\d+)?)\s*$")
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_FIELD_CANDIDATE_EXCLUDED_IDS = {"process", "process2", "process3", "processes", "comments_search"}
# Date fields backed directly by a native Part timestamp (not attrs-derived) already store a
# real, consistently-typed BSON date on every document, so they don't need the
# field_values materialization pass that normalizes messy attrs-sourced date strings.
_NATIVE_DATE_FIELD_IDS = {"created_at"}
_ARENA_BOM_FIXED_FIELD_IDS = {"thumbnail", "part_number", "description", "qty", "level"}
_FINAL_APPROVAL_CONTEXTS = {"parts_list", "part_detail_summary", "bom_tree", "where_used"}
_DEFAULT_ARENA_HEADERS = {
    "description": "item name",
    "category": "item category",
    "classified": "classification",
    "oem": "oem",
    "oem_partnumber": "OEM PART NUMBER",
    "process": "process",
    "material": "material",
    "finish": "finish",
    "link": "link",
    "revision": "Revision",
    "mass": "Mass",
    "uom": "UoM",
    "level_qty": "Level Qty",
    "total_qty": "Total Qty",
}


DEFAULT_FIELDS: List[Dict[str, Any]] = [
    {
        "id": "thumbnail",
        "label": "Thumbnail",
        "kind": "special",
        "data_type": "image",
        "source_locked": True,
        "sortable": False,
        "filterable": False,
    },
    {
        "id": "part_number",
        "label": "Part Number",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.part_number",
        "fallback_paths": ["part.part_number"],
        "source_locked": True,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "revision",
        "label": "Revision",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.revision",
        "fallback_paths": ["part.canonical.revision", "part.revision", "attrs.revision"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "description",
        "label": "Description",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.description",
        "fallback_paths": ["part.description", "attrs.description"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "created_at",
        "label": "Added",
        "kind": "builtin",
        "data_type": "date",
        "source_path": "part.created_at",
        "fallback_paths": ["part.created_at"],
        "source_locked": True,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "notes",
        "label": "Notes",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.notes_search",
        "fallback_paths": ["part.notes_search"],
        "source_locked": False,
        "sortable": False,
        "filterable": True,
    },
    {
        "id": "comments",
        "label": "Comments",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.comments_search",
        "fallback_paths": ["part.comments_search"],
        "source_locked": False,
        "sortable": False,
        "filterable": True,
    },
    {
        "id": "display_code",
        "label": "Display Code",
        "kind": "builtin",
        "data_type": "text",
        "source_locked": True,
        "sortable": False,
        "filterable": False,
    },
    {
        "id": "category",
        "label": "Category",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.category",
        "fallback_paths": ["part.canonical.category", "part.category", "attrs.category"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "material",
        "label": "Material",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.material",
        "fallback_paths": ["part.canonical.material", "attrs.material"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "finish",
        "label": "Finish",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.finish",
        "fallback_paths": ["part.canonical.finish", "attrs.finish"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "mass",
        "label": "Mass",
        "kind": "builtin",
        "data_type": "number",
        "source_path": "part.canonical.mass",
        "fallback_paths": ["part.canonical.mass", "attrs.mass"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "process",
        "label": "Process",
        "kind": "builtin",
        "data_type": "text",
        # Normalised to a canonical list on write and indexed, so filtering and
        # sorting query it directly. Aliases (process2, secondprocess, ...) are
        # collapsed by the resolver and never queried.
        "source_path": "part.processes",
        "fallback_paths": ["part.processes"],
        "source_locked": True,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "uom",
        "label": "UoM",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.uom",
        "fallback_paths": ["part.canonical.uom", "part.uom", "attrs.uom"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "status",
        "label": "Status",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.status",
        "fallback_paths": ["part.status", "attrs.status"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "link",
        "label": "Link",
        "kind": "builtin",
        "data_type": "link",
        "source_path": "part.canonical.link",
        "fallback_paths": ["part.canonical.link", "attrs.link"],
        "source_locked": False,
        "sortable": False,
        "filterable": True,
    },
    {
        "id": "oem",
        "label": "OEM",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.oem",
        "fallback_paths": ["part.canonical.oem", "attrs.oem", "attrs.manufacturer", "part.manufacturer"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "oem_partnumber",
        "label": "OEM Part Number",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.oem_partnumber",
        "fallback_paths": ["part.canonical.oem_partnumber", "attrs.oem_partnumber", "attrs.mfr_part", "part.mfr_part"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "datasheet",
        "label": "Datasheet",
        "kind": "builtin",
        "data_type": "link",
        "source_path": "part.canonical.datasheet",
        "fallback_paths": [
            "part.canonical.datasheet",
            "attrs.datasheet",
            "attrs.oem_data_sheet",
            "attrs.oem_datasheet",
            "attrs.data_sheet",
            "attrs.datasheet_url",
        ],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "classified",
        "label": "Classified",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.classified",
        "fallback_paths": ["part.canonical.classified", "attrs.classified"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "approved",
        "label": "Approved",
        "kind": "builtin",
        "data_type": "boolean",
        # Resolved once on write and read straight back, like approved_by and
        # approved_date. No alias fallback: a part the resolver has not written
        # is not approved.
        "source_path": "part.canonical.approved",
        "source_locked": True,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "approved_by",
        "label": "Approved By",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.approved_by",
        "fallback_paths": ["part.canonical.approved_by", "attrs.approved_by"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "approved_date",
        "label": "Approved Date",
        "kind": "builtin",
        "data_type": "date",
        "source_path": "part.canonical.approved_date",
        "fallback_paths": ["part.canonical.approved_date", "attrs.approved_date"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "drawn_by",
        "label": "Drawn By",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.drawn_by",
        "fallback_paths": ["part.canonical.drawn_by", "attrs.drawnby"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "drawn_date",
        "label": "Drawn Date",
        "kind": "builtin",
        "data_type": "date",
        "source_path": "part.canonical.drawn_date",
        "fallback_paths": ["part.canonical.drawn_date", "attrs.drawndate"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "checked_by",
        "label": "Checked By",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.checked_by",
        "fallback_paths": ["part.canonical.checked_by", "attrs.checkedby"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "checked_date",
        "label": "Checked Date",
        "kind": "builtin",
        "data_type": "date",
        "source_path": "part.canonical.checked_date",
        "fallback_paths": ["part.canonical.checked_date", "attrs.checkeddate"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "manufacturer",
        "label": "Manufacturer",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.manufacturer",
        "fallback_paths": ["part.canonical.manufacturer", "part.manufacturer", "attrs.manufacturer", "attrs.oem"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "mfr_part",
        "label": "Manufacturer Part",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.canonical.mfr_part",
        "fallback_paths": ["part.canonical.mfr_part", "part.mfr_part", "attrs.mfr_part", "attrs.oem_partnumber"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
]


FILE_AVAILABILITY_FIELDS: List[tuple[str, str, str]] = [
    ("has_pdf", "Has PDF", "pdf"),
    ("has_png", "Has PNG", "png"),
    ("has_dxf", "Has DXF", "dxf"),
    ("has_step", "Has STEP", "step"),
    ("has_edr", "Has EDR", "edr"),
    ("has_3mf", "Has 3MF", "3mf"),
    ("has_ply", "Has PLY", "ply"),
    ("has_stl", "Has STL", "stl"),
    ("has_datasheet", "Has Datasheet", "datasheet"),
]


DEFAULT_FIELDS.extend(
    [
        {
            "id": field_id,
            "label": label,
            "kind": "special",
            "data_type": "boolean",
            "source_path": f"part.{field_id}",
            "fallback_paths": [f"part.{field_id}"],
            "source_locked": True,
            "sortable": False,
            "filterable": True,
        }
        for field_id, label, _group in FILE_AVAILABILITY_FIELDS
    ]
    + [
        {
            "id": "qty",
            "label": "Qty",
            "kind": "special",
            "data_type": "number",
            "source_locked": True,
            "sortable": True,
            "filterable": True,
        },
        {
            "id": "alt_group",
            "label": "Alt Group",
            "kind": "special",
            "data_type": "text",
            "source_locked": True,
            "sortable": True,
            "filterable": True,
        },
        {
            "id": "level",
            "label": "Level",
            "kind": "special",
            "data_type": "text",
            "source_locked": True,
            "sortable": False,
            "filterable": False,
        },
        {
            "id": "level_qty",
            "label": "Level Qty",
            "kind": "special",
            "data_type": "text",
            "source_locked": True,
            "sortable": False,
            "filterable": False,
        },
        {
            "id": "total_qty",
            "label": "Total Qty",
            "kind": "special",
            "data_type": "number",
            "source_locked": True,
            "sortable": False,
            "filterable": False,
        },
    ]
)


DEFAULT_CONTEXTS: Dict[str, Dict[str, Any]] = {
    "parts_list": {
        "label": "Parts Table",
        "required_field_ids": ["part_number"],
        "allowed_field_ids": [
            "thumbnail",
            "part_number",
            "revision",
            "description",
            "notes",
            "comments",
            "category",
            "material",
            "finish",
            "mass",
            "process",
            "uom",
            "status",
            "approved",
            "link",
            "oem",
            "oem_partnumber",
            "created_at",
            *[field_id for field_id, _label, _group in FILE_AVAILABILITY_FIELDS],
        ],
        "default_field_ids": [
            "thumbnail",
            "part_number",
            "revision",
            "created_at",
            "description",
            "material",
            "finish",
            "process",
            "approved",
        ],
    },
    "part_detail_summary": {
        "label": "Part Summary",
        "required_field_ids": [],
        "allowed_field_ids": [
            "revision",
            "description",
            "notes",
            "comments",
            "category",
            "material",
            "finish",
            "mass",
            "process",
            "uom",
            "status",
            "link",
            "oem",
            "oem_partnumber",
            "datasheet",
            "classified",
            "approved",
            "approved_by",
            "approved_date",
            "drawn_by",
            "drawn_date",
            "checked_by",
            "checked_date",
            *[field_id for field_id, _label, _group in FILE_AVAILABILITY_FIELDS],
        ],
        "default_field_ids": [
            "material",
            "finish",
            "mass",
            "process",
            "oem",
            "oem_partnumber",
            "approved",
        ],
    },
    "bom_tree": {
        "label": "BOM Tree",
        "required_field_ids": ["part_number"],
        "allowed_field_ids": [
            "thumbnail",
            "part_number",
            "revision",
            "description",
            "process",
            "finish",
            "material",
            "mass",
            "uom",
            "approved",
            "qty",
            "alt_group",
            *[field_id for field_id, _label, _group in FILE_AVAILABILITY_FIELDS],
        ],
        "default_field_ids": [
            "thumbnail",
            "part_number",
            "revision",
            "description",
            "process",
            "finish",
            "material",
            "approved",
            "qty",
        ],
    },
    "where_used": {
        "label": "Where Used",
        "required_field_ids": ["part_number"],
        "allowed_field_ids": [
            "thumbnail",
            "part_number",
            "revision",
            "description",
            "process",
            "finish",
            "material",
            "category",
            "uom",
            "approved",
            "qty",
            "alt_group",
            *[field_id for field_id, _label, _group in FILE_AVAILABILITY_FIELDS],
        ],
        "default_field_ids": [
            "thumbnail",
            "part_number",
            "revision",
            "description",
            "approved",
            "qty",
        ],
    },
    "excel_bom": {
        "label": "Excel BOM",
        "required_field_ids": ["part_number", "revision", "description", "total_qty"],
        "allowed_field_ids": [
            "thumbnail",
            "part_number",
            "revision",
            "description",
            "total_qty",
            "material",
            "process",
            "finish",
            "mass",
            "link",
            "oem",
            "oem_partnumber",
            "uom",
            "category",
            "level",
            "level_qty",
            *[field_id for field_id, _label, _group in FILE_AVAILABILITY_FIELDS],
        ],
        "default_field_ids": [
            "thumbnail",
            "part_number",
            "revision",
            "description",
            "total_qty",
            "material",
            "process",
            "finish",
            "mass",
            "link",
            "oem",
            "oem_partnumber",
            "level",
            "level_qty",
        ],
    },
    "arena_bom": {
        "label": "Arena BOM",
        "required_field_ids": [],
        "allowed_field_ids": [
            "revision",
            "notes",
            "comments",
            "category",
            "material",
            "finish",
            "mass",
            "process",
            "uom",
            "status",
            "approved",
            "link",
            "oem",
            "oem_partnumber",
            "datasheet",
            "classified",
            "approved",
            "approved_by",
            "approved_date",
            "drawn_by",
            "drawn_date",
            "checked_by",
            "checked_date",
            "manufacturer",
            "mfr_part",
            "alt_group",
            "level_qty",
            "total_qty",
            *[field_id for field_id, _label, _group in FILE_AVAILABILITY_FIELDS],
        ],
        "default_field_ids": [
            "revision",
            "total_qty",
            "material",
            "process",
            "finish",
            "mass",
            "link",
            "oem",
            "oem_partnumber",
            "category",
            "level_qty",
        ],
    },
}


def default_arena_header_for_field(field_id: str, label: str = "") -> str:
    return _DEFAULT_ARENA_HEADERS.get(field_id, _normalize_text(label) or field_id.replace("_", " ").title())


def _default_builtin_map() -> Dict[str, Dict[str, Any]]:
    """Fresh, mutable copy for callers that edit the returned fields."""
    return {field["id"]: deepcopy(field) for field in DEFAULT_FIELDS}


@lru_cache(maxsize=1)
def _default_builtin_index() -> Dict[str, Dict[str, Any]]:
    """Read-only view of the same map.

    DEFAULT_FIELDS is a module constant, so the deep copy only exists to protect
    callers that mutate. Read-only lookups on request hot paths share this one.
    """
    return {field["id"]: field for field in DEFAULT_FIELDS}


def _default_field_order() -> List[str]:
    return [field["id"] for field in DEFAULT_FIELDS]


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_field_id(value: Any) -> str:
    text = canonical_attr_key(value)
    return text


def _normalize_source_path(path: Any) -> str:
    text = _normalize_text(path)
    if not text:
        return ""
    parts = [segment for segment in text.split(".") if _normalize_text(segment)]
    if len(parts) < 2:
        return ""
    head = _normalize_text(parts[0]).lower()
    if head not in {"part", "attrs"}:
        return ""
    tail: List[str] = []
    for segment in parts[1:]:
        normalized = _normalize_field_id(segment)
        if not normalized:
            return ""
        tail.append(normalized)
    return ".".join([head] + tail)


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in _BOOLEAN_TRUE


def _non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _unique_ids(values: Iterable[str], valid_ids: set[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        field_id = _normalize_text(value)
        if not field_id or field_id not in valid_ids or field_id in seen:
            continue
        seen.add(field_id)
        out.append(field_id)
    return out


def _is_valid_source_path(path: Any) -> bool:
    return bool(_SOURCE_PATH_RE.match(_normalize_source_path(path)))


def _coerce_custom_data_type(value: Any) -> str:
    data_type = _normalize_text(value).lower()
    if data_type in {"text", "number", "boolean", "date", "link"}:
        return data_type
    return "text"


def file_field_group(field_id: str) -> Optional[str]:
    for known_id, _label, group in FILE_AVAILABILITY_FIELDS:
        if known_id == field_id:
            return group
    return None


def boolean_filter_value(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    text = _normalize_text(value).lower()
    if not text:
        return None
    if text in _BOOLEAN_TRUE:
        return True
    if text in _BOOLEAN_FALSE:
        return False
    return None


def _number_filter(value: Any) -> Optional[tuple[str, float, Optional[float]]]:
    text = _normalize_text(value).lower()
    if not text:
        return None
    match = _NUMBER_RANGE_RE.match(text)
    if match:
        start = float(match.group(1))
        end = float(match.group(2))
        if start > end:
            start, end = end, start
        return ("range", start, end)
    match = _NUMBER_COMPARE_RE.match(text)
    if not match:
        return None
    op = match.group(1) or "="
    return (op, float(match.group(2)), None)


def number_filter_value(value: Any) -> Optional[tuple[str, float, Optional[float]]]:
    return _number_filter(value)


def _value_as_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = _normalize_text(value)
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def text_terms_match(value: Any, filter_value: Any) -> bool:
    text = _normalize_text(filter_value).lower()
    if not text:
        return True
    hay = _normalize_text(value).lower()
    terms = [term for term in re.split(r"\s+", text) if term]
    return all(term in hay for term in terms)


def date_filter_value(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    text = _normalize_text(value)
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _is_empty_filter_value(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def matches_field_filter_value(
    value: Any,
    filter_value: Any,
    data_type: str = "text",
    match_mode: str = "contains",
) -> bool:
    if match_mode == "isEmpty":
        return _is_empty_filter_value(value)
    if match_mode == "isNotEmpty":
        return not _is_empty_filter_value(value)
    text = _normalize_text(filter_value)
    if not text:
        return True
    if data_type == "boolean":
        expected = boolean_filter_value(text)
        if expected is not None:
            matched = _is_truthy(value) == expected
            return not matched if match_mode == "notEquals" else matched
        normalized = "true yes" if _is_truthy(value) else "false no"
        return text_terms_match(normalized, text)
    if data_type == "number":
        mode_to_op = {"equals": "=", "notEquals": "!=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}
        parsed = None
        if match_mode == "between" and isinstance(filter_value, (list, tuple)) and len(filter_value) >= 2:
            left = _value_as_number(filter_value[0])
            right = _value_as_number(filter_value[1])
            if left is not None and right is not None:
                parsed = ("range", min(left, right), max(left, right))
        elif match_mode in mode_to_op:
            # Preserve the compact legacy grammar (">10", "4..8") when a
            # client omits matchMode and the type's default is equals.
            inline = _number_filter(text) if match_mode == "equals" else None
            if inline is not None and inline[0] != "=":
                parsed = inline
            else:
                target = _value_as_number(filter_value)
                if target is not None:
                    parsed = (mode_to_op[match_mode], target, None)
        else:
            parsed = _number_filter(text)
        if parsed is None:
            return text_terms_match(value, text)
        actual = _value_as_number(value)
        if actual is None:
            return False
        op, start, end = parsed
        if op == "range":
            return start <= actual <= float(end if end is not None else start)
        if op == ">":
            return actual > start
        if op == ">=":
            return actual >= start
        if op == "<":
            return actual < start
        if op == "<=":
            return actual <= start
        if op == "!=":
            return actual != start
        return actual == start
    if data_type == "date":
        actual = date_filter_value(value)
        target = date_filter_value(filter_value)
        if actual is None or target is None:
            return False
        actual_day = actual.date()
        target_day = target.date()
        if match_mode == "dateIsNot":
            return actual_day != target_day
        if match_mode == "dateBefore":
            return actual_day < target_day
        if match_mode == "dateAfter":
            return actual_day > target_day
        return actual_day == target_day

    hay = _normalize_text(value).lower()
    needle = text.lower()
    if match_mode == "equals":
        return hay == needle
    if match_mode == "notEquals":
        return hay != needle
    if match_mode == "startsWith":
        return hay.startswith(needle)
    if match_mode == "endsWith":
        return hay.endswith(needle)
    if match_mode == "notContains":
        return needle not in hay
    return text_terms_match(value, text)


def matches_field_filter_constraints(
    value: Any,
    constraints: Iterable[Dict[str, Any]],
    operator: str,
    data_type: str = "text",
) -> bool:
    results = [
        matches_field_filter_value(value, item.get("value"), data_type, str(item.get("match_mode") or "contains"))
        for item in constraints
    ]
    if not results:
        return True
    return any(results) if str(operator).lower() == "or" else all(results)


def default_field_config() -> Dict[str, Any]:
    return {
        "builtin_fields": [
            {
                "id": field["id"],
                "label": field["label"],
                "source_path": field.get("source_path", ""),
                "arena_header": default_arena_header_for_field(field["id"], field["label"]),
            }
            for field in DEFAULT_FIELDS
        ],
        "custom_fields": [],
        "contexts": deepcopy(DEFAULT_CONTEXTS),
        "canonical_aliases": default_canonical_alias_entries(),
        "approval_rules": default_approval_rules(),
    }


def _settings_doc(create: bool = True) -> Optional[AppSettings]:
    settings = AppSettings.objects().order_by("-updated_at").first()
    if settings or not create:
        return settings
    settings = AppSettings()
    settings.save()
    return settings


def sanitize_admin_field_config(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    payload = payload or {}
    builtin_default_map = _default_builtin_map()

    builtin_raw = payload.get("builtin_fields")
    builtin_index = {}
    if isinstance(builtin_raw, list):
        for item in builtin_raw:
            if not isinstance(item, dict):
                continue
            field_id = _normalize_text(item.get("id"))
            if field_id in builtin_default_map:
                builtin_index[field_id] = item
    elif isinstance(builtin_raw, dict):
        for field_id, item in builtin_raw.items():
            if field_id in builtin_default_map and isinstance(item, dict):
                builtin_index[field_id] = item

    builtin_fields: List[Dict[str, Any]] = []
    for field_id in _default_field_order():
        default_field = builtin_default_map[field_id]
        raw = builtin_index.get(field_id, {})
        item: Dict[str, Any] = {
            "id": field_id,
            "label": default_field["label"],
            "arena_header": default_arena_header_for_field(field_id, default_field["label"]),
        }
        label = _normalize_text(raw.get("label"))
        if label:
            item["label"] = label
        arena_header = _normalize_text(raw.get("arena_header"))
        if arena_header:
            item["arena_header"] = arena_header
        if not default_field.get("source_locked"):
            source_path = _normalize_source_path(raw.get("source_path") or default_field.get("source_path"))
            if _is_valid_source_path(source_path):
                item["source_path"] = source_path
            elif default_field.get("source_path"):
                item["source_path"] = default_field["source_path"]
        elif default_field.get("source_path"):
            item["source_path"] = default_field["source_path"]
        builtin_fields.append(item)

    custom_fields: List[Dict[str, Any]] = []
    seen_custom = set()
    raw_custom = payload.get("custom_fields")
    if isinstance(raw_custom, list):
        for item in raw_custom:
            if not isinstance(item, dict):
                continue
            field_id = _normalize_field_id(item.get("id"))
            if not _FIELD_ID_RE.match(field_id):
                continue
            if field_id in builtin_default_map or field_id in seen_custom:
                continue
            source_path = _normalize_source_path(item.get("source_path"))
            if not source_path:
                source_path = f"attrs.{field_id}"
            if not _is_valid_source_path(source_path):
                continue
            label = _normalize_text(item.get("label")) or field_id.replace("_", " ").title()
            custom_fields.append(
                {
                    "id": field_id,
                    "label": label,
                    "arena_header": _normalize_text(item.get("arena_header")) or label,
                    "source_path": source_path,
                    "kind": "custom",
                    "data_type": _coerce_custom_data_type(item.get("data_type")),
                    "sortable": _is_truthy(item.get("sortable", True)),
                    "filterable": _is_truthy(item.get("filterable", True)),
                }
            )
            seen_custom.add(field_id)

    field_ids = set(builtin_default_map.keys()) | seen_custom
    contexts: Dict[str, Dict[str, Any]] = {}
    raw_contexts = payload.get("contexts") if isinstance(payload.get("contexts"), dict) else {}
    for name, default_ctx in DEFAULT_CONTEXTS.items():
        raw = raw_contexts.get(name) if isinstance(raw_contexts.get(name), dict) else {}
        allowed = _unique_ids(raw.get("allowed_field_ids") or default_ctx["allowed_field_ids"], field_ids)
        if not allowed:
            allowed = list(default_ctx["allowed_field_ids"])
        # Final approval is a core searchable state. Keep it available in every
        # interactive part context, including configurations saved by older
        # installations before the field was exposed there.
        if name in _FINAL_APPROVAL_CONTEXTS and "approved" in field_ids and "approved" not in allowed:
            allowed.append("approved")
        default_selected = _unique_ids(raw.get("default_field_ids") or default_ctx["default_field_ids"], set(allowed))
        if name == "arena_bom":
            allowed = [field_id for field_id in allowed if field_id not in _ARENA_BOM_FIXED_FIELD_IDS]
            default_selected = [field_id for field_id in default_selected if field_id not in _ARENA_BOM_FIXED_FIELD_IDS]
        required = _unique_ids(default_ctx.get("required_field_ids") or [], field_ids)
        for req in required:
            if req not in allowed:
                allowed.append(req)
            if req not in default_selected:
                default_selected.insert(0, req)
        if not default_selected:
            default_selected = [field_id for field_id in default_ctx["default_field_ids"] if field_id in allowed]
        contexts[name] = {
            "label": default_ctx["label"],
            "required_field_ids": required,
            "allowed_field_ids": allowed,
            "default_field_ids": default_selected,
        }

    return {
        "builtin_fields": builtin_fields,
        "custom_fields": custom_fields,
        "contexts": contexts,
        "canonical_aliases": canonical_alias_entries_from_field_config(payload),
        "approval_rules": approval_rules_from_field_config(payload),
    }


def get_field_config() -> Dict[str, Any]:
    if has_app_context():
        cached = getattr(g, "_part_field_config", None)
        if isinstance(cached, dict):
            return cached
    defaults = default_field_config()
    settings = _settings_doc(create=False)
    stored = {}
    if settings and isinstance(getattr(settings, "field_config", None), dict):
        stored = settings.field_config or {}
    sanitized = sanitize_admin_field_config(stored)

    builtin_map = _default_builtin_map()
    overrides = {
        item["id"]: item
        for item in sanitized.get("builtin_fields", [])
        if isinstance(item, dict) and item.get("id") in builtin_map
    }

    fields: List[Dict[str, Any]] = []
    for field_id in _default_field_order():
        field = deepcopy(builtin_map[field_id])
        override = overrides.get(field_id, {})
        if override.get("label"):
            field["label"] = override["label"]
        field["arena_header"] = override.get("arena_header") or default_arena_header_for_field(field_id, field.get("label", ""))
        if not field.get("source_locked") and override.get("source_path"):
            field["source_path"] = override["source_path"]
        fields.append(field)

    for custom in sanitized.get("custom_fields", []):
        fields.append(
            {
                "id": custom["id"],
                "label": custom["label"],
                "arena_header": custom.get("arena_header") or custom["label"],
                "kind": "custom",
                "data_type": custom.get("data_type", "text"),
                "source_path": custom["source_path"],
                "fallback_paths": [custom["source_path"]],
                "source_locked": False,
                "sortable": bool(custom.get("sortable", True)),
                "filterable": bool(custom.get("filterable", True)),
            }
        )

    field_index_map = {field["id"]: field for field in fields}
    contexts = deepcopy(defaults["contexts"])
    for name, ctx in sanitized.get("contexts", {}).items():
        if name not in contexts:
            continue
        contexts[name]["required_field_ids"] = list(ctx.get("required_field_ids") or contexts[name]["required_field_ids"])
        contexts[name]["allowed_field_ids"] = [field_id for field_id in ctx.get("allowed_field_ids", []) if field_id in field_index_map]
        contexts[name]["default_field_ids"] = [field_id for field_id in ctx.get("default_field_ids", []) if field_id in field_index_map]
        if name == "arena_bom":
            contexts[name]["allowed_field_ids"] = [
                field_id for field_id in contexts[name]["allowed_field_ids"] if field_id not in _ARENA_BOM_FIXED_FIELD_IDS
            ]
            contexts[name]["default_field_ids"] = [
                field_id for field_id in contexts[name]["default_field_ids"] if field_id not in _ARENA_BOM_FIXED_FIELD_IDS
            ]
        if not contexts[name]["allowed_field_ids"]:
            contexts[name]["allowed_field_ids"] = [field_id for field_id in DEFAULT_CONTEXTS[name]["allowed_field_ids"] if field_id in field_index_map]
        if not contexts[name]["default_field_ids"]:
            contexts[name]["default_field_ids"] = [field_id for field_id in DEFAULT_CONTEXTS[name]["default_field_ids"] if field_id in field_index_map]
        for req in contexts[name]["required_field_ids"]:
            if req not in contexts[name]["allowed_field_ids"]:
                contexts[name]["allowed_field_ids"].append(req)
            if req not in contexts[name]["default_field_ids"]:
                contexts[name]["default_field_ids"].insert(0, req)
        contexts[name]["available_fields"] = [deepcopy(field_index_map[field_id]) for field_id in contexts[name]["allowed_field_ids"]]

    result = {
        "fields": fields,
        "contexts": contexts,
        "canonical_aliases": list(sanitized.get("canonical_aliases") or default_canonical_alias_entries()),
        "approval_rules": dict(sanitized.get("approval_rules") or default_approval_rules()),
    }
    if has_app_context():
        g._part_field_config = result
    return result


def save_field_config(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    if has_app_context():
        g.pop("_part_field_config", None)
    sanitized = sanitize_admin_field_config(payload)
    settings = _settings_doc(create=True)
    saved_at = utc_now()
    settings.field_config = sanitized
    settings.updated_at = saved_at
    settings.save()
    # Older/restored installations can contain more than one global settings
    # document. Keep the field configuration identical across them so selecting
    # the newest document cannot make aliases disappear.
    AppSettings.objects(id__ne=settings.id).update(
        set__field_config=sanitized,
        set__updated_at=saved_at,
    )
    set_runtime_canonical_aliases(sanitized)
    return get_field_config()


def reset_field_config() -> Dict[str, Any]:
    if has_app_context():
        g.pop("_part_field_config", None)
    settings = _settings_doc(create=True)
    saved_at = utc_now()
    settings.field_config = {}
    settings.updated_at = saved_at
    settings.save()
    AppSettings.objects(id__ne=settings.id).update(
        set__field_config={},
        set__updated_at=saved_at,
    )
    set_runtime_canonical_aliases({})
    return get_field_config()


def _builtin_candidate_source_paths() -> set[str]:
    paths: set[str] = set()
    for field in DEFAULT_FIELDS:
        for source_path in [field.get("source_path"), *(field.get("fallback_paths") or [])]:
            normalized = _normalize_source_path(source_path)
            if normalized:
                paths.add(normalized)
    return paths


def _candidate_label_from_raw(raw_key: Any, field_id: str) -> str:
    text = _normalize_text(raw_key)
    if not text:
        return field_id.replace("_", " ").title()
    tokens = [token for token in re.split(r"[^A-Za-z0-9]+", text) if token]
    if not tokens:
        return field_id.replace("_", " ").title()
    pretty: List[str] = []
    for token in tokens:
        if token.isupper() and len(token) <= 5:
            pretty.append(token)
        elif token.islower() or token.isupper():
            pretty.append(token.capitalize())
        else:
            pretty.append(token)
    return " ".join(pretty)


def _candidate_label_score(label: str) -> tuple[int, int, str]:
    acronym_count = sum(1 for token in label.split() if token.isupper() and len(token) <= 5)
    return (-acronym_count, len(label), label.lower())


def _candidate_label(field_id: str, raw_keys: Iterable[str]) -> str:
    labels = {
        _candidate_label_from_raw(raw_key, field_id)
        for raw_key in raw_keys
        if _normalize_text(raw_key)
    }
    if not labels:
        return field_id.replace("_", " ").title()
    return sorted(labels, key=_candidate_label_score)[0]


def _candidate_sample_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, (list, tuple, set)):
        text = ", ".join(_candidate_sample_value(item) for item in value if _non_empty(item))
    elif isinstance(value, dict):
        text = ", ".join(
            f"{_normalize_text(key)}: {_candidate_sample_value(item)}"
            for key, item in value.items()
            if _non_empty(item)
        )
    else:
        text = _normalize_text(value)
    if len(text) > 120:
        return text[:117] + "..."
    return text


def _candidate_value_is_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return False
    text = _normalize_text(value).lower()
    return bool(text) and text in (_BOOLEAN_TRUE | _BOOLEAN_FALSE)


def _candidate_value_is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    text = _normalize_text(value)
    if not text:
        return False
    try:
        float(text)
    except Exception:
        return False
    return True


def _candidate_value_is_link(value: Any) -> bool:
    if isinstance(value, (list, tuple, set, dict)):
        return False
    text = _normalize_text(value)
    return bool(text) and bool(_URL_RE.match(text))


def _candidate_data_type(sample_values: Iterable[Any]) -> str:
    values = [value for value in sample_values if _non_empty(value)]
    if not values:
        return "text"
    if all(_candidate_value_is_boolean(value) for value in values):
        return "boolean"
    if all(_candidate_value_is_number(value) for value in values):
        return "number"
    if all(_candidate_value_is_link(value) for value in values):
        return "link"
    return "text"


def discover_part_attr_fields() -> List[Dict[str, Any]]:
    builtin_source_paths = _builtin_candidate_source_paths()
    builtin_ids = {field["id"] for field in DEFAULT_FIELDS}
    discovered: Dict[str, Dict[str, Any]] = {}

    for part in Part.objects.only("attrs").order_by("part_number", "revision"):
        raw_attrs = getattr(part, "attrs", None)
        if not isinstance(raw_attrs, dict) or not raw_attrs:
            continue

        raw_keys_by_id: Dict[str, set[str]] = {}
        for raw_key, raw_value in raw_attrs.items():
            if not _non_empty(raw_value):
                continue
            field_id = canonical_field_for_attr_key(raw_key) or ALIASES.get(canonical_attr_key(raw_key), canonical_attr_key(raw_key))
            if not field_id:
                continue
            raw_keys_by_id.setdefault(field_id, set()).add(str(raw_key))

        normalized_attrs = normalize_props(raw_attrs)
        for key, value in normalized_attrs.items():
            field_id = canonical_field_for_attr_key(key) or _normalize_field_id(key)
            source_path = f"attrs.{field_id}" if field_id else ""
            if not field_id or field_id in _FIELD_CANDIDATE_EXCLUDED_IDS:
                continue
            if source_path in builtin_source_paths or not _non_empty(value):
                continue
            candidate_id = field_id
            candidate_label_suffix = ""
            if field_id in builtin_ids:
                candidate_id = f"attr_{field_id}"
                candidate_label_suffix = " (Attribute)"
            entry = discovered.setdefault(
                candidate_id,
                {
                    "id": candidate_id,
                    "source_path": source_path,
                    "part_count": 0,
                    "raw_keys": set(),
                    "sample_values": [],
                    "label_suffix": candidate_label_suffix,
                },
            )
            entry["part_count"] += 1
            entry["raw_keys"].update(raw_keys_by_id.get(field_id) or [])
            if len(entry["sample_values"]) < 5:
                entry["sample_values"].append(value)

    candidates: List[Dict[str, Any]] = []
    for field_id, item in discovered.items():
        raw_keys = sorted(item["raw_keys"], key=lambda value: value.lower())
        sample_values = list(item["sample_values"])
        label = _candidate_label(field_id, raw_keys)
        if item.get("label_suffix"):
            label = f"{label}{item['label_suffix']}"
        candidates.append(
            {
                "id": field_id,
                "label": label,
                "source_path": item["source_path"],
                "data_type": _candidate_data_type(sample_values),
                "part_count": int(item["part_count"]),
                "sample_value": next((_candidate_sample_value(value) for value in sample_values if _non_empty(value)), ""),
                "raw_keys": raw_keys,
            }
        )

    return sorted(candidates, key=lambda item: (item["label"].lower(), item["id"]))


def field_index(config: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    """Map field id -> field definition.

    Resolving one row's values calls this once per field, so rebuilding the
    dict every time made a listing O(rows x fields x fields). The index is a
    pure function of the config, memoized per request on the config's identity
    so an edited config (a new object) rebuilds on its own.
    """

    config = config or get_field_config()
    if has_app_context():
        cached = getattr(g, "_field_index_cache", None)
        if cached is not None and cached[0] is config:
            return cached[1]
    index = {field["id"]: field for field in config.get("fields", [])}
    if has_app_context():
        g._field_index_cache = (config, index)
    return index


def context_config(context_name: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or get_field_config()
    return deepcopy(config.get("contexts", {}).get(context_name) or {})


def context_field_ids(context_name: str, config: Optional[Dict[str, Any]] = None, *, default: bool = False) -> List[str]:
    cfg = context_config(context_name, config)
    key = "default_field_ids" if default else "allowed_field_ids"
    return list(cfg.get(key) or [])


def sanitize_user_field_preferences(raw: Dict[str, Any] | None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    config = config or get_field_config()
    raw = raw or {}
    raw_contexts = raw.get("contexts") if isinstance(raw.get("contexts"), dict) else {}
    contexts: Dict[str, Dict[str, List[str]]] = {}
    for name, ctx in config.get("contexts", {}).items():
        raw_ctx = raw_contexts.get(name) if isinstance(raw_contexts.get(name), dict) else {}
        allowed = set(ctx.get("allowed_field_ids") or [])
        selected = _unique_ids(raw_ctx.get("field_ids") or ctx.get("default_field_ids") or [], allowed)
        for req in ctx.get("required_field_ids") or []:
            if req not in selected:
                selected.insert(0, req)
        if not selected:
            selected = list(ctx.get("default_field_ids") or [])
        ctx_out: Dict[str, Any] = {"field_ids": selected}
        if "use_default" in raw_ctx:
            ctx_out["use_default"] = bool(raw_ctx.get("use_default"))
        contexts[name] = ctx_out
    raw_review_columns = raw.get("review_columns") if isinstance(raw.get("review_columns"), dict) else {}
    review_columns = {
        name: bool(raw_review_columns.get(name))
        for name in ("parts_list", "bom_tree")
        if name in raw_review_columns
    }
    return {"contexts": contexts, "review_columns": review_columns}


def _get_nested(source: Any, path: List[str]) -> Any:
    cur = source
    for part in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            if part in cur:
                cur = cur.get(part)
                continue
            target = canonical_attr_key(part)
            matched_key = next((key for key in cur.keys() if canonical_attr_key(key) == target), None)
            cur = cur.get(matched_key) if matched_key is not None else None
            continue
        cur = getattr(cur, part, None)
    return cur


def _coerce_value(value: Any, data_type: str) -> Any:
    if value is None:
        return None if data_type in {"boolean", "number", "date"} else ""
    if data_type == "boolean":
        if isinstance(value, bool):
            return value
        if not _normalize_text(value):
            return None
        return _is_truthy(value)
    if data_type == "number":
        if isinstance(value, (int, float)):
            return value
        text = _normalize_text(value)
        if not text:
            return ""
        try:
            num = float(text)
        except Exception:
            return None
        return int(num) if num.is_integer() else num
    if data_type == "date":
        return date_filter_value(value)
    if data_type == "link":
        return _normalize_text(value)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value if item is not None)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    return value


def mongo_field_from_source(source_path: str) -> Optional[str]:
    source_path = _normalize_text(source_path)
    if not _is_valid_source_path(source_path):
        return None
    parts = source_path.split(".")
    head = parts[0]
    tail = parts[1:]
    if head == "part":
        return "__".join(tail)
    if head == "attrs":
        return "attrs__" + "__".join(tail)
    return None


def effective_source_paths(field_id: str, config: Optional[Dict[str, Any]] = None) -> List[str]:
    field = field_index(config).get(field_id)
    if not field:
        return []
    out: List[str] = []
    primary = _normalize_text(field.get("source_path"))
    if primary:
        out.append(primary)
    for item in field.get("fallback_paths") or []:
        path = _normalize_text(item)
        if path and path not in out:
            out.append(path)
    return out


def query_paths_for_field(field_id: str, config: Optional[Dict[str, Any]] = None) -> List[str]:
    field = field_index(config).get(field_id)
    if not field:
        return []
    if field_uses_materialized_value(field_id, config):
        return [f"field_values__{field_id}"]
    out: List[str] = []
    for source_path in effective_source_paths(field_id, config):
        mongo_path = mongo_field_from_source(source_path)
        if mongo_path and mongo_path not in out:
            out.append(mongo_path)
    return out


def primary_query_path(field_id: str, config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    paths = query_paths_for_field(field_id, config)
    return paths[0] if paths else None


def field_uses_materialized_value(field_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
    config = config or get_field_config()
    field = field_index(config).get(field_id)
    if not field:
        return False
    if field_id in _NATIVE_DATE_FIELD_IDS:
        return False
    if str(field.get("kind") or "") == "custom":
        return True
    if str(field.get("data_type") or "") == "date":
        return True
    default_field = _default_builtin_index().get(field_id)
    if not default_field or field.get("source_locked"):
        return False
    current_source = _normalize_source_path(field.get("source_path"))
    default_source = _normalize_source_path(default_field.get("source_path"))
    return bool(current_source and default_source and current_source != default_source)


def materialized_field_ids(config: Optional[Dict[str, Any]] = None) -> List[str]:
    config = config or get_field_config()
    return [field["id"] for field in config.get("fields", []) if field_uses_materialized_value(field["id"], config)]


_PART_FIELD_INDEX_SIGNATURES: set[tuple[str, ...]] = set()


def ensure_active_part_field_indexes(config: Optional[Dict[str, Any]] = None) -> List[str]:
    """Create idempotent indexes for materialized Parts-list fields in active use."""
    config = config or get_field_config()
    active_ids: List[str] = []
    fields = field_index(config)
    for field_id in context_field_ids("parts_list", config):
        field = fields.get(field_id) or {}
        if not field_id or not field_uses_materialized_value(field_id, config):
            continue
        if field.get("filterable") or field.get("sortable"):
            active_ids.append(field_id)
    signature = tuple(sorted(set(active_ids)))
    collection = Part._get_collection()
    expected_names = [
        f"parts_field_values_{(re.sub(r'[^a-zA-Z0-9_]+', '_', field_id).strip('_') or 'field')}_idx"[:120]
        for field_id in signature
    ]
    if signature in _PART_FIELD_INDEX_SIGNATURES and all(name in collection.index_information() for name in expected_names):
        return expected_names
    names: List[str] = []
    for field_id in signature:
        safe_id = re.sub(r"[^a-zA-Z0-9_]+", "_", field_id).strip("_") or "field"
        name = f"parts_field_values_{safe_id}_idx"[:120]
        collection.create_index([(f"field_values.{field_id}", 1)], name=name)
        names.append(name)
    _PART_FIELD_INDEX_SIGNATURES.add(signature)
    return names


def serialize_field_values(
    values: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert typed values to the stable JSON representation used by the UI."""
    fields = field_index(config or get_field_config())
    out = dict(values or {})
    for field_id, value in list(out.items()):
        if str((fields.get(field_id) or {}).get("data_type") or "") != "date" or value is None:
            continue
        parsed = date_filter_value(value)
        out[field_id] = parsed.date().isoformat() if parsed is not None else ""
    return out


def resolve_part_field_value(
    part: Optional[Part],
    field_id: str,
    *,
    attrs: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
    coverage: Optional[set[str]] = None,
) -> Any:
    config = config or get_field_config()
    field = field_index(config).get(field_id)
    if not field:
        return ""
    # Callers resolving multiple fields for the same part (the common case,
    # via resolve_part_field_values) already pass a pre-normalized attrs dict
    # here — re-running normalize_props() per field was the dominant cost of
    # /api/parts_lazy (it walks the whole canonical/approval alias pipeline).
    if attrs is None:
        attrs = normalize_props(harvest_part_attrs(part) if part else {})
    extra = dict(extra or {})
    data_type = field.get("data_type", "text")

    if field_id in extra and _non_empty(extra[field_id]):
        return _coerce_value(extra[field_id], data_type)

    if field_id == "thumbnail":
        return extra.get("thumbnail", "")
    if field_id == "display_code":
        pn = _normalize_text(extra.get("part_number")) or _normalize_text(getattr(part, "part_number", ""))
        rev = _normalize_text(extra.get("revision"))
        if not rev:
            rev = clean_rev(attrs.get("revision") or getattr(part, "revision", ""))
        return f"{pn}-{rev}" if pn and rev else pn
    if field_id == "process":
        meta = current_app.config.get("PROCESS_META", {}) if has_app_context() else {}
        return canonical_process_label_for_part(part, raw_attrs=attrs, process_meta=meta)
    if field_id == "notes":
        return _coerce_value(annotation_payload(part).get("notes"), data_type)
    if field_id == "comments":
        return _coerce_value(annotation_payload(part).get("comments_search"), data_type)
    if field_id == "approved":
        # Single source of truth: the boolean written by the import/save
        # resolver. Re-deriving it from attrs here let the two disagree.
        return bool((getattr(part, "canonical", None) or {}).get("approved"))
    if field_id == "datasheet":
        datasheet_url = datasheet_url_from_attrs(attrs)
        if datasheet_url:
            return _coerce_value(datasheet_url, data_type)
    file_group = file_field_group(field_id)
    if file_group:
        groups = coverage or set()
        if file_group == "datasheet" and datasheet_attr_present(attrs):
            return True
        if groups:
            return file_group in groups
        if part is not None:
            return bool(getattr(part, field_id, False))
        return False
    if field_id in {"qty", "alt_group", "level", "level_qty", "total_qty"}:
        return _coerce_value(extra.get(field_id), data_type)

    for source_path in effective_source_paths(field_id, config):
        root, _, tail = source_path.partition(".")
        path = [part_name for part_name in tail.split(".") if part_name]
        if root == "part":
            value = _get_nested(part, path)
        else:
            value = _get_nested(attrs, path)
        if _non_empty(value):
            return _coerce_value(value, data_type)

    return ""


def field_requires_runtime_scan(field_id: str, config: Optional[Dict[str, Any]] = None) -> bool:
    config = config or get_field_config()
    field = field_index(config).get(field_id)
    if not field:
        return False
    if query_paths_for_field(field_id, config):
        return False
    return field_id not in {"process", "approved"}


def resolve_part_field_values(
    part: Optional[Part],
    field_ids: Iterable[str],
    *,
    attrs: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
    coverage: Optional[set[str]] = None,
) -> Dict[str, Any]:
    config = config or get_field_config()
    attrs = normalize_props(attrs or (harvest_part_attrs(part) if part else {}))
    values: Dict[str, Any] = {}
    for field_id in field_ids:
        values[field_id] = resolve_part_field_value(
            part,
            field_id,
            attrs=attrs,
            config=config,
            extra=extra,
            coverage=coverage,
        )
    return values


def context_row_values(
    context_name: str,
    part: Optional[Part],
    *,
    attrs: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
    coverage: Optional[set[str]] = None,
) -> Dict[str, Any]:
    config = config or get_field_config()
    field_ids = context_field_ids(context_name, config)
    return resolve_part_field_values(
        part,
        field_ids,
        attrs=attrs,
        config=config,
        extra=extra,
        coverage=coverage,
    )

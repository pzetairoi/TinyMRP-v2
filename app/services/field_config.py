from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from app.models.app_settings import AppSettings
from app.models.part import Part
from app.services.attrs import approved_value, comments_search_text, harvest_part_attrs
from app.services.part_norm import clean_rev
from app.services.processmeta import normalize_processes


_FIELD_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SOURCE_PATH_RE = re.compile(r"^(part|attrs)(?:\.[A-Za-z0-9_]+)+$")
_BOOLEAN_TRUE = {"1", "true", "yes", "on", "y"}
_BOOLEAN_FALSE = {"0", "false", "no", "off", "n", "missing", "none", "absent"}
_NUMBER_RANGE_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:\.\.|to|-)\s*(-?\d+(?:\.\d+)?)\s*$", re.IGNORECASE)
_NUMBER_COMPARE_RE = re.compile(r"^\s*(<=|>=|=|<|>)?\s*(-?\d+(?:\.\d+)?)\s*$")


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
        "source_path": "attrs.revision",
        "fallback_paths": ["attrs.revision", "part.revision"],
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
        "id": "notes",
        "label": "Notes",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.notes",
        "fallback_paths": ["attrs.notes"],
        "source_locked": False,
        "sortable": False,
        "filterable": True,
    },
    {
        "id": "comments",
        "label": "Comments",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.comments_search",
        "fallback_paths": ["attrs.comments_search", "attrs.comments"],
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
        "source_path": "attrs.category",
        "fallback_paths": ["attrs.category", "part.category"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "material",
        "label": "Material",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.material",
        "fallback_paths": ["attrs.material"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "finish",
        "label": "Finish",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.finish",
        "fallback_paths": ["attrs.finish"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "mass",
        "label": "Mass",
        "kind": "builtin",
        "data_type": "number",
        "source_path": "attrs.mass",
        "fallback_paths": ["attrs.mass"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "process",
        "label": "Process",
        "kind": "builtin",
        "data_type": "text",
        "source_locked": True,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "uom",
        "label": "UoM",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.uom",
        "fallback_paths": ["attrs.uom", "part.uom"],
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
        "source_path": "attrs.link",
        "fallback_paths": ["attrs.link"],
        "source_locked": False,
        "sortable": False,
        "filterable": True,
    },
    {
        "id": "oem",
        "label": "OEM",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.oem",
        "fallback_paths": ["attrs.oem", "attrs.manufacturer", "part.manufacturer"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "oem_partnumber",
        "label": "OEM Part Number",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.oem_partnumber",
        "fallback_paths": ["attrs.oem_partnumber", "attrs.mfr_part", "part.mfr_part"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "datasheet",
        "label": "Datasheet",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.datasheet",
        "fallback_paths": ["attrs.datasheet"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "classified",
        "label": "Classified",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.classified",
        "fallback_paths": ["attrs.classified"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "approved",
        "label": "Approved",
        "kind": "builtin",
        "data_type": "boolean",
        "source_locked": True,
        "sortable": False,
        "filterable": True,
    },
    {
        "id": "approved_by",
        "label": "Approved By",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.approvedby",
        "fallback_paths": ["attrs.approvedby", "attrs.approved_by", "attrs.approved"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "approved_date",
        "label": "Approved Date",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.approveddate",
        "fallback_paths": ["attrs.approveddate"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "drawn_by",
        "label": "Drawn By",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.drawnby",
        "fallback_paths": ["attrs.drawnby"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "drawn_date",
        "label": "Drawn Date",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.drawndate",
        "fallback_paths": ["attrs.drawndate"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "checked_by",
        "label": "Checked By",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.checkedby",
        "fallback_paths": ["attrs.checkedby"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "checked_date",
        "label": "Checked Date",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "attrs.checkeddate",
        "fallback_paths": ["attrs.checkeddate"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "manufacturer",
        "label": "Manufacturer",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.manufacturer",
        "fallback_paths": ["part.manufacturer", "attrs.manufacturer", "attrs.oem"],
        "source_locked": False,
        "sortable": True,
        "filterable": True,
    },
    {
        "id": "mfr_part",
        "label": "Manufacturer Part",
        "kind": "builtin",
        "data_type": "text",
        "source_path": "part.mfr_part",
        "fallback_paths": ["part.mfr_part", "attrs.mfr_part", "attrs.oem_partnumber"],
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
            *[field_id for field_id, _label, _group in FILE_AVAILABILITY_FIELDS],
        ],
        "default_field_ids": [
            "thumbnail",
            "part_number",
            "revision",
            "description",
            "material",
            "finish",
            "process",
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
            "qty",
            "alt_group",
            *[field_id for field_id, _label, _group in FILE_AVAILABILITY_FIELDS],
        ],
        "default_field_ids": [
            "thumbnail",
            "part_number",
            "revision",
            "description",
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
}


def _default_builtin_map() -> Dict[str, Dict[str, Any]]:
    return {field["id"]: deepcopy(field) for field in DEFAULT_FIELDS}


def _default_field_order() -> List[str]:
    return [field["id"] for field in DEFAULT_FIELDS]


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


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
    return bool(_SOURCE_PATH_RE.match(_normalize_text(path)))


def _coerce_custom_data_type(value: Any) -> str:
    data_type = _normalize_text(value).lower()
    if data_type in {"text", "number", "boolean", "link"}:
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


def matches_field_filter_value(value: Any, filter_value: Any, data_type: str = "text") -> bool:
    text = _normalize_text(filter_value)
    if not text:
        return True
    if data_type == "boolean":
        expected = boolean_filter_value(text)
        if expected is not None:
            return _is_truthy(value) == expected
        normalized = "true yes" if _is_truthy(value) else "false no"
        return text_terms_match(normalized, text)
    if data_type == "number":
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
        return actual == start
    return text_terms_match(value, text)


def default_field_config() -> Dict[str, Any]:
    return {
        "builtin_fields": [
            {"id": field["id"], "label": field["label"], "source_path": field.get("source_path", "")}
            for field in DEFAULT_FIELDS
        ],
        "custom_fields": [],
        "contexts": deepcopy(DEFAULT_CONTEXTS),
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
    defaults = default_field_config()
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
        item: Dict[str, Any] = {"id": field_id, "label": default_field["label"]}
        label = _normalize_text(raw.get("label"))
        if label:
            item["label"] = label
        if not default_field.get("source_locked"):
            source_path = _normalize_text(raw.get("source_path") or default_field.get("source_path"))
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
            field_id = _normalize_text(item.get("id")).lower()
            if not _FIELD_ID_RE.match(field_id):
                continue
            if field_id in builtin_default_map or field_id in seen_custom:
                continue
            source_path = _normalize_text(item.get("source_path"))
            if not _is_valid_source_path(source_path):
                continue
            label = _normalize_text(item.get("label")) or field_id.replace("_", " ").title()
            custom_fields.append(
                {
                    "id": field_id,
                    "label": label,
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
        default_selected = _unique_ids(raw.get("default_field_ids") or default_ctx["default_field_ids"], set(allowed))
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
    }


def get_field_config() -> Dict[str, Any]:
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
        if not field.get("source_locked") and override.get("source_path"):
            field["source_path"] = override["source_path"]
        fields.append(field)

    for custom in sanitized.get("custom_fields", []):
        fields.append(
            {
                "id": custom["id"],
                "label": custom["label"],
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

    return {
        "fields": fields,
        "contexts": contexts,
    }


def save_field_config(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    sanitized = sanitize_admin_field_config(payload)
    settings = _settings_doc(create=True)
    settings.field_config = sanitized
    settings.save()
    return get_field_config()


def reset_field_config() -> Dict[str, Any]:
    settings = _settings_doc(create=True)
    settings.field_config = {}
    settings.save()
    return get_field_config()


def field_index(config: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    config = config or get_field_config()
    return {field["id"]: field for field in config.get("fields", [])}


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
    return {"contexts": contexts}


def _get_nested(source: Any, path: List[str]) -> Any:
    cur = source
    for part in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
            continue
        cur = getattr(cur, part, None)
    return cur


def _coerce_value(value: Any, data_type: str) -> Any:
    if value is None:
        return ""
    if data_type == "boolean":
        if isinstance(value, bool):
            return value
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
            return text
        return int(num) if num.is_integer() else num
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
    out: List[str] = []
    for source_path in effective_source_paths(field_id, config):
        mongo_path = mongo_field_from_source(source_path)
        if mongo_path and mongo_path not in out:
            out.append(mongo_path)
    return out


def primary_query_path(field_id: str, config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    paths = query_paths_for_field(field_id, config)
    return paths[0] if paths else None


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
    attrs = dict(attrs or (harvest_part_attrs(part) if part else {}))
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
        processes = normalize_processes(attrs, {})
        if isinstance(getattr(part, "processes", None), list):
            for item in part.processes or []:
                text = _normalize_text(item).lower()
                if text and text not in processes:
                    processes.append(text)
        return ", ".join(processes)
    if field_id == "comments":
        return comments_search_text(attrs.get("comments") or attrs.get("comments_search"))
    if field_id == "approved":
        return bool(approved_value(attrs))
    file_group = file_field_group(field_id)
    if file_group:
        groups = coverage or set()
        return file_group in groups
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
    attrs = dict(attrs or (harvest_part_attrs(part) if part else {}))
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

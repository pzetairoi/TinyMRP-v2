# app/services/attrs.py
from __future__ import annotations
from typing import Dict, Any, Iterable, List, Tuple
import re

_SPLIT = re.compile(r"[;,]")  # split on commas/semicolons
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Canonical keys that must always exist (as strings)
REQUIRED_KEYS: Iterable[str] = (
    "approvedby", "approveddate",
    "drawnby", "drawndate",
    "checkeddate", "checkedby",
    "classified", "category", "configuration",
    "datasheet", "description",
    "file", "finish", "folder", "link",
    "mass", "material",
    "oem", "oem_partnumber",
    "process", "process2", "process3",   # legacy single fields kept
    "revision", "spare_part",
)

# Map legacy/mixed keys to canonical ones
ALIASES: Dict[str, str] = {
    # common variants / capitalizations
    "approvedby": "approvedby",
    "approved": "approvedby",
    "approved_by": "approvedby",
    "approveddate": "approveddate",
    "approvedby_": "approvedby",
    "approveddate_": "approveddate",
    "drawnby": "drawnby",
    "drawndate": "drawndate",
    "checkedby": "checkedby",
    "checkeddate": "checkeddate",
    "classified": "classified",
    "category": "category",
    "configuration": "configuration",
    "sw_configuration": "configuration",
    "datasheet": "datasheet",
    "oem_data_sheet": "datasheet",
    "description": "description",
    "file": "file",
    "finish": "finish",
    "folder": "folder",
    "link": "link",
    "oem_internet": "link",
    "oem_link": "link",            # accept OEM link variant
    "mass": "mass",
    "weight": "mass",
    "material": "material",
    "oem": "oem",
    "manufacturer": "oem",           # treat manufacturer as OEM name
    "oem_partnumber": "oem_partnumber",
    "oem_part_number": "oem_partnumber",
    "mfr_part": "oem_partnumber",
    "process": "process",
    "secondprocess": "process2",
    "thirdprocess": "process3",
    "process2": "process2",
    "process3": "process3",
    "revision": "revision",
    "rev": "revision",
    "spare_part": "spare_part",
    # mixed-case keys from legacy dumps
    "drawnby_": "drawnby",
    "checkeddate_": "checkeddate",
    "approvedby": "approvedby",
    "approveddate": "approveddate",
    "drawnby": "drawnby",
    "checkeddate": "checkeddate",
    "approvedby": "approvedby",
    "approveddate": "approveddate",
    "drawnby": "drawnby",
    # CamelCase variants
    "drawnby".lower(): "drawnby",
    "drawnby": "drawnby",
    "drawnby_".lower(): "drawnby",
    "checkeddate".lower(): "checkeddate",
    "approvedby".lower(): "approvedby",
    "approveddate".lower(): "approveddate",
    "drawnby".lower(): "drawnby",
    # Exact mixed-case seen in your sample
    "drawnby": "drawnby",
    "checkeddate": "checkeddate",
    "approvedby": "approvedby",
    "approveddate": "approveddate",
    "weight": "mass",
}

_APPROVAL_EMPTY = {"", "n/a", "na", "none", "null", "0", "false"}


def canonical_attr_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = _NON_ALNUM.sub("_", text)
    return text.strip("_")

def _is_blankish_approval(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return not value
    text = str(value).strip().lower()
    return text in _APPROVAL_EMPTY

def approved_value(attrs: Dict[str, Any]) -> Any:
    if not isinstance(attrs, dict):
        return None
    for key in ("approvedby", "approved_by", "approved"):
        if key in attrs and not _is_blankish_approval(attrs.get(key)):
            return attrs.get(key)
    for k, v in attrs.items():
        kl = (str(k) if k is not None else "").strip().lower()
        if kl in ("approvedby", "approved_by", "approved") and not _is_blankish_approval(v):
            return v
    return None

def _normalize_approved_fields(attrs: Dict[str, Any]) -> None:
    if not isinstance(attrs, dict):
        return
    val = approved_value(attrs)
    if val is None:
        return
    attrs["approvedby"] = val
    attrs["approved_by"] = val
    attrs["approved"] = val

def _to_list(v) -> List[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v if x is not None]
    if isinstance(v, str):
        # allow comma/semicolon separated strings
        parts = [p.strip() for p in _SPLIT.split(v) if p.strip()]
        return parts
    return [str(v)]


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


def normalize_processes_from_attrs(attrs: Dict) -> List[str]:
    """
    Read process fields from raw attrs and produce a normalized, lowercased,
    de-duplicated list preserving order.
      - accepts: processes (list or string), process, process2/secondprocess, process3/thirdprocess
    """
    if not isinstance(attrs, dict):
        return []

    raw: List[str] = []
    raw += _to_list(attrs.get("processes"))
    raw += _to_list(attrs.get("process"))
    raw += _to_list(attrs.get("process2") or attrs.get("secondprocess"))
    raw += _to_list(attrs.get("process3") or attrs.get("thirdprocess"))

    out: List[str] = []
    seen = set()
    for p in raw:
        p2 = p.strip().lower()
        if p2 and p2 not in seen:
            seen.add(p2)
            out.append(p2)
    return out


def process_attributes(raw_attrs: Dict | None) -> Tuple[Dict, List[str]]:
    """
    Main entrypoint used by import/update code.
    Returns (attrs_dict, processes_list)

    - Ensures attrs is a dict.
    - Writes the normalized list back into attrs['processes'] (for the Attributes tab).
    - Leaves legacy attrs['process'] intact if present; do NOT overwrite it.
    """
    attrs = dict(raw_attrs or {})
    _normalize_approved_fields(attrs)
    processes = normalize_processes_from_attrs(attrs)
    if "comments" in attrs:
        attrs["comments_search"] = comments_search_text(attrs.get("comments"))

    # Mirror the list into attrs for the UI "All attributes" panel
    attrs["processes"] = processes

    return attrs, processes



def _as_str(x: Any) -> str:
    if x is None:
        return ""
    # keep scalars as strings; lists handled separately
    return str(x)

def _aliasize(raw: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (raw or {}).items():
        kl = canonical_attr_key(k)
        key = ALIASES.get(kl, kl)
        out[key] = v
    return out

def normalize_props(raw: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a fresh dict with canonicalized keys, processes list, and REQUIRED_KEYS present."""
    aliased = _aliasize(raw or {})
    _normalize_approved_fields(aliased)

    # Build processes list from explicit list or process/process2/process3
    processes_list = []
    if isinstance(aliased.get("processes"), list):
        for t in aliased["processes"]:
            s = (str(t) if t is not None else "").strip()
            if s and s not in processes_list:
                processes_list.append(s)
    # also harvest from single fields (keep order)
    for k in ("process", "process2", "process3"):
        s = _as_str(aliased.get(k) or "").strip()
        if s and s not in processes_list:
            processes_list.append(s)
    aliased["processes"] = processes_list
    if "comments" in aliased:
        aliased["comments_search"] = comments_search_text(aliased.get("comments"))

    # Ensure all required keys exist as strings
    for k in REQUIRED_KEYS:
        aliased[k] = _as_str(aliased.get(k, ""))

    # Normalize revision as string (empty allowed)
    aliased["revision"] = _as_str(aliased.get("revision", ""))

    return aliased

def harvest_part_attrs(part) -> Dict[str, Any]:
    """Merge attributes from part.attrs, part.props, and top-level mirrors, then normalize."""
    merged: Dict[str, Any] = {}

    # 1) primary store (your DB uses 'attrs')
    if hasattr(part, "attrs") and isinstance(part.attrs, dict):
        merged.update(part.attrs or {})

    # 2) legacy/aux store
    if hasattr(part, "props") and isinstance(part.props, dict):
        merged.update(part.props or {})

    # 3) mirrors (top-level fields if missing)
    mirrors = {
        "description": getattr(part, "description", None),
        "revision": getattr(part, "revision", None),
        "category": getattr(part, "category", None),
        "uom": getattr(part, "uom", None),
    }
    for k, v in mirrors.items():
        if v is not None and not merged.get(k):
            merged[k] = v

    return normalize_props(merged)

def merge_save_part_attrs(part, incoming: Dict[str, Any]) -> None:
    """Persist normalized attributes into part.attrs and mirror common fields."""
    props = normalize_props(incoming)

    current = dict(getattr(part, "attrs", {}) or {})
    current.update(props)
    part.attrs = current

    # Mirror common fields for convenience
    if "description" in props:
        part.description = props["description"]
    if "revision" in props:
        part.revision = props["revision"]
    if "category" in props:
        part.category = props["category"]

    part.save()

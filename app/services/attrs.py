# app/services/attrs.py
from __future__ import annotations
from typing import Dict, Any, Iterable

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

def _as_str(x: Any) -> str:
    if x is None:
        return ""
    # keep scalars as strings; lists handled separately
    return str(x)

def _aliasize(raw: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (raw or {}).items():
        kl = (k or "").strip().lower()
        key = ALIASES.get(kl, kl)
        out[key] = v
    return out

def normalize_props(raw: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a fresh dict with canonicalized keys, processes list, and REQUIRED_KEYS present."""
    aliased = _aliasize(raw or {})

    # Build processes list from explicit list or process/process2/process3
    processes_list = []
    if isinstance(aliased.get("processes"), list):
        for t in aliased["processes"]:
            s = (str(t) if t is not None else "").strip()
            if s and s not in processes_list:
                processes_list.append(s)
    # also harvest from single fields (keep order)
    for k in ("process", "process2", "process3"):
        s = (aliased.get(k) or "").strip()
        if s and s not in processes_list:
            processes_list.append(s)
    aliased["processes"] = processes_list

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

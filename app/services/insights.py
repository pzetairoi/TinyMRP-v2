from __future__ import annotations

from typing import Dict, List


HARDWARE_TERMS = {"hardware", "fastener", "fasteners"}
SHEET_METAL_TERMS = {"lasercut", "profile cut", "cutting", "folding", "rolling"}
PURCHASE_TERMS = {"purchase"}
ASSEMBLY_TERMS = {"assembly"}
FABRICATION_TERMS = {
    "machine",
    "welding",
    "casting",
    "3d print",
    "paint",
    "zinc",
    "galvanize",
    "nickel",
    "cutting",
    "lasercut",
    "profile cut",
    "folding",
    "rolling",
}


def _safe_lower(value: str | None) -> str:
    return (value or "").strip().lower()


def normalized_processes(attrs: Dict, part_processes: List[str], meta: Dict) -> List[str]:
    """Return a part's canonical processes.

    ``part_processes`` is normalised on write, so it is returned as-is. The
    attrs fallback only serves records that predate the resolver.
    """

    if part_processes:
        return [str(value) for value in part_processes if value]

    from app.services.processmeta import normalize_processes

    return normalize_processes(attrs or {}, meta)


def classify_part(attrs: Dict, part_processes: List[str], meta: Dict, category: str = "") -> str:
    proc_list = normalized_processes(attrs, part_processes, meta)
    proc_set = {p for p in (proc_list or []) if p}
    cat = _safe_lower(category or attrs.get("category"))
    material = _safe_lower(attrs.get("material") or attrs.get("Material") or "")

    if proc_set & HARDWARE_TERMS or "hardware" in cat:
        return "hardware"
    if proc_set & PURCHASE_TERMS or "purchase" in cat or "purchased" in cat:
        return "purchase"
    if proc_set & ASSEMBLY_TERMS or "assembly" in cat:
        return "assembly"
    if proc_set & SHEET_METAL_TERMS or "sheet" in cat or "sheet" in material:
        return "sheet_metal"
    if proc_set & FABRICATION_TERMS:
        return "fabrication"
    return "fabrication"


def missing_fields(attrs: Dict, description: str, part_processes: List[str], meta: Dict) -> List[str]:
    missing = []
    desc = (description or "").strip() or str(attrs.get("description") or "").strip()
    if not desc:
        missing.append("description")
    material = (attrs.get("material") or attrs.get("Material") or "").strip()
    if not material:
        missing.append("material")
    proc_list = normalized_processes(attrs, part_processes, meta)
    if not proc_list:
        missing.append("process")
    return missing


def recommended_deliverables(
    classification: str,
    deliverables_present: Dict[str, bool],
    attrs: Dict,
    has_bom: bool,
) -> List[str]:
    missing = []
    has_pdf = bool(deliverables_present.get("pdf"))
    has_dxf = bool(deliverables_present.get("dxf"))
    has_datasheet = bool(deliverables_present.get("datasheet"))
    link = (attrs.get("link") or attrs.get("oem_internet") or "").strip()

    if classification in ("hardware", "purchase"):
        if not has_datasheet:
            missing.append("datasheet")
        if not link:
            missing.append("link")
    if classification == "sheet_metal":
        if not has_pdf:
            missing.append("pdf")
        if not has_dxf:
            missing.append("dxf")
    if classification == "assembly":
        if not has_pdf:
            missing.append("pdf")
        if not has_bom:
            missing.append("bom")
    return missing

import json, os, re
from typing import Dict, List

_DEFAULT = {
    "purchase":  {"color":"112, 48, 160","icon":"purchase.svg","aliases":["purchasing","buy","procure"]},
    "machine":   {"color":"255, 0, 0","icon":"machine.svg","aliases":["machining","cnc"]},
    "welding":   {"color":"255, 192, 0","icon":"welding.svg","aliases":["stud welding","stud_welding"]},
    "folding":   {"color":"0, 102, 0","icon":"folding.svg","aliases":[]},
    "rolling":   {"color":"0, 102, 0","icon":"roll.svg","aliases":[]},
    "casting":   {"color":"255, 0, 255","icon":"casting.svg","aliases":[]},
    "lasercut":  {"color":"0, 176, 80","icon":"lasercut.svg","aliases":["laser cut","laser-cut"]},
    "profile cut":{"color":"153, 102, 51","icon":"profilecut.svg","aliases":["profile-cut","oxy","plasma"]},
    "3d laser":  {"color":"0, 176, 80","icon":"3d-laser.svg","aliases":["3dlaser"]},
    "cutting":   {"color":"255, 192, 0","icon":"cutting.svg","aliases":[]},
    "sewing":    {"color":"192, 0, 0","icon":"sewing.svg","aliases":[]},
    "3d print":  {"color":"192, 0, 0","icon":"3d-printing.svg","aliases":["3dprint","additive"]},
    "paint":     {"color":"0, 32, 96","icon":"spray.svg","aliases":["painting","powdercoat","powder coat"]},
    "zinc":      {"color":"0, 32, 96","icon":"zinc.svg","aliases":[]},
    "galvanize": {"color":"0, 32, 96","icon":"galvanize.svg","aliases":["galvanised","galvanized"]},
    "nickel":    {"color":"0, 32, 96","icon":"nickel.svg","aliases":[]},
    "assembly":  {"color":"0, 176, 240","icon":"assembly.svg","aliases":["assy","assemble"]},
    "label":     {"color":"0, 176, 240","icon":"label.svg","aliases":[]},
    "hardware":  {"color":"208, 206, 206","icon":"hardware.svg","aliases":["fastener","fasteners"]},
    "others":    {"color":"118, 113, 113","icon":"unknown.svg","aliases":[]},
}

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def load_process_meta(path: str | None = None) -> Dict:
    path = path or os.getenv("PROCESS_META_FILE")
    data = None
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None
    meta = data or _DEFAULT

    # build alias index
    alias_index: Dict[str, str] = {}
    for canon, m in meta.items():
        alias_index[_norm(canon)] = canon
        for a in m.get("aliases", []):
            alias_index[_norm(a)] = canon
    meta["_alias_index"] = alias_index
    return meta

def normalize_processes(attrs: Dict, meta: Dict) -> List[str]:
    # take processes list, else process/process2/process3
    procs = []
    if isinstance(attrs.get("processes"), list):
        procs.extend([_norm(x) for x in attrs.get("processes", []) if x])
    for k in ("process", "process2", "process3"):
        if attrs.get(k):
            procs.append(_norm(attrs.get(k)))
    if not procs:
        return []

    alias = meta.get("_alias_index", {})
    normalized = []
    seen = set()
    for p in procs:
        canon = alias.get(p, p)
        if canon not in meta:
            canon = "others"
        if canon not in seen:
            seen.add(canon)
            normalized.append(canon)
    return normalized

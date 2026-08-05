import copy
import json
import os
import re
from typing import Any, Dict, Iterable, List

_MISSING = object()

_DEFAULT = {
    "purchase": {
        "color": "112, 48, 160",
        "icon": "purchase.svg",
        "aliases": ["purchasing", "buy", "procure"],
        "file_groups": ["pdf", "datasheet"],
    },
    "machine": {"color": "255, 0, 0", "icon": "machine.svg", "aliases": ["machining", "cnc"]},
    "welding": {"color": "255, 192, 0", "icon": "welding.svg", "aliases": ["stud welding", "stud_welding"]},
    "folding": {"color": "0, 102, 0", "icon": "folding.svg", "aliases": []},
    "rolling": {"color": "0, 102, 0", "icon": "roll.svg", "aliases": []},
    "casting": {"color": "255, 0, 255", "icon": "casting.svg", "aliases": []},
    "lasercut": {"color": "0, 176, 80", "icon": "lasercut.svg", "aliases": ["laser cut", "laser-cut"]},
    "profile cut": {
        "color": "153, 102, 51",
        "icon": "profilecut.svg",
        "aliases": ["profile-cut", "oxy", "plasma", "plasma cut", "plasmacut", "waterjet", "water jet", "water-jet"],
    },
    "3d laser": {"color": "0, 176, 80", "icon": "3d-laser.svg", "aliases": ["3dlaser"]},
    "cutting": {"color": "255, 192, 0", "icon": "cutting.svg", "aliases": []},
    "sewing": {"color": "192, 0, 0", "icon": "sewing.svg", "aliases": []},
    "3d print": {"color": "192, 0, 0", "icon": "3d-printing.svg", "aliases": ["3dprint", "additive"]},
    "paint": {"color": "0, 32, 96", "icon": "spray.svg", "aliases": ["painting", "powdercoat", "powder coat"]},
    "zinc": {"color": "0, 32, 96", "icon": "zinc.svg", "aliases": []},
    "galvanize": {"color": "0, 32, 96", "icon": "galvanize.svg", "aliases": ["galvanised", "galvanized"]},
    "nickel": {"color": "0, 32, 96", "icon": "nickel.svg", "aliases": []},
    "assembly": {"color": "0, 176, 240", "icon": "assembly.svg", "aliases": ["assy", "assemble"]},
    "label": {"color": "0, 176, 240", "icon": "label.svg", "aliases": []},
    "hardware": {"color": "208, 206, 206", "icon": "hardware.svg", "aliases": ["fastener", "fasteners"]},
    "others": {"color": "118, 113, 113", "icon": "unknown.svg", "aliases": []},
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _uniq(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        token = text.lower()
        if token in seen:
            continue
        seen.add(token)
        out.append(text)
    return out


def _clean_color(value: Any, default_value: str = "118, 113, 113") -> str:
    text = str(value or "").strip()
    if not text:
        return default_value
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) != 3:
        return default_value
    nums: List[str] = []
    for part in parts:
        try:
            num = max(0, min(255, int(float(part))))
        except Exception:
            return default_value
        nums.append(str(num))
    return ", ".join(nums)


def _clean_icon(value: Any, default_value: str = "unknown.svg") -> str:
    text = os.path.basename(str(value or "").strip())
    return text or default_value


def _clean_file_group(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in ("stp", "step"):
        return "step"
    if text in ("jpg", "jpeg"):
        return "png"
    return text


def default_process_meta(path: str | None = None) -> Dict[str, Dict[str, Any]]:
    path = path or os.getenv("PROCESS_META_FILE")
    data = None
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None
    source = data or _DEFAULT
    return sanitize_process_meta(source, ensure_defaults=False)


def sanitize_process_meta(raw: Any, *, ensure_defaults: bool = True) -> Dict[str, Dict[str, Any]]:
    items: Iterable[tuple[str, Any]]
    if isinstance(raw, dict):
        items = [(str(k or ""), v) for k, v in raw.items() if str(k or "").strip() and not str(k).startswith("_")]
    elif isinstance(raw, list):
        tmp: List[tuple[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            tmp.append((str(item.get("name") or item.get("id") or ""), item))
        items = tmp
    else:
        items = []

    meta: Dict[str, Dict[str, Any]] = {}
    for raw_name, payload in items:
        name = _norm(raw_name)
        if not name:
            continue
        entry = payload if isinstance(payload, dict) else {}
        default_entry = _DEFAULT.get(name) or _DEFAULT.get("others") or {}
        raw_aliases = entry.get("aliases") if "aliases" in entry else _MISSING
        if raw_aliases is _MISSING:
            aliases = _uniq(_norm(alias) for alias in (default_entry.get("aliases") or []))
        elif isinstance(raw_aliases, str):
            aliases = _uniq(_norm(alias) for alias in re.split(r"[,;\r\n]+", str(raw_aliases or "")))
        else:
            aliases = _uniq(_norm(alias) for alias in (raw_aliases or []))
        aliases = [alias for alias in aliases if alias and alias != name]

        raw_file_groups = _MISSING
        for key in ("file_groups", "required_files", "files"):
            if key in entry:
                raw_file_groups = entry.get(key)
                break
        if raw_file_groups is _MISSING:
            file_groups_raw = list(default_entry.get("file_groups") or [])
        else:
            file_groups_raw = raw_file_groups or []
        if isinstance(file_groups_raw, str):
            file_groups_raw = re.split(r"[,;\r\n]+", file_groups_raw)
        file_groups = _uniq(_clean_file_group(item) for item in (file_groups_raw or []))

        out: Dict[str, Any] = {
            "color": _clean_color(entry.get("color"), default_entry.get("color", "118, 113, 113")),
            "icon": _clean_icon(entry.get("icon"), default_entry.get("icon", "unknown.svg")),
            "aliases": aliases,
        }
        if file_groups:
            out["file_groups"] = file_groups
        meta[name] = out

    if ensure_defaults and "others" not in meta:
        fallback = _DEFAULT["others"]
        meta["others"] = {
            "color": fallback["color"],
            "icon": fallback["icon"],
            "aliases": list(fallback.get("aliases") or []),
        }
    return meta


def _with_alias_index(meta: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out = copy.deepcopy(meta)
    alias_index: Dict[str, str] = {}
    for canon, item in out.items():
        alias_index[_norm(canon)] = canon
        for alias in item.get("aliases", []):
            alias_index[_norm(alias)] = canon
    out["_alias_index"] = alias_index
    return out


def load_process_meta(path: str | None = None, overrides: Any | None = None) -> Dict:
    base = default_process_meta(path)
    meta = copy.deepcopy(base)
    custom = sanitize_process_meta(overrides) if overrides else {}
    for name, item in custom.items():
        if str(name).startswith("_"):
            continue
        meta[name] = copy.deepcopy(item)
    if "others" not in meta:
        meta["others"] = copy.deepcopy(base.get("others") or _DEFAULT["others"])
    return _with_alias_index(meta)

def _split_process_value(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        out: List[str] = []
        for item in value:
            out.extend(_split_process_value(item))
        return out
    if isinstance(value, str):
        parts = re.split(r"\s*(?:,|;|/|\||&|\+|\r|\n)\s*", value)
        return [p for p in (p.strip() for p in parts) if p]
    return [str(value)]


def _attr_ci(attrs: Dict, key: str) -> Iterable[Any]:
    if not isinstance(attrs, dict):
        return []
    if key in attrs:
        return [attrs.get(key)]
    key_l = (key or "").strip().lower()
    for k, v in attrs.items():
        try:
            if str(k or "").strip().lower() == key_l:
                return [v]
        except Exception:
            continue
    return []


def normalize_processes(attrs: Dict, meta: Dict) -> List[str]:
    # take processes list, else process/process2/process3 (case-insensitive keys)
    procs = []
    for val in _attr_ci(attrs, "processes"):
        procs.extend(_split_process_value(val))
    for k in ("process", "process2", "process3"):
        for val in _attr_ci(attrs, k):
            procs.extend(_split_process_value(val))
    if not procs:
        return []

    alias = meta.get("_alias_index", {}) if isinstance(meta, dict) else {}
    catalog = {str(key): value for key, value in (meta or {}).items() if not str(key).startswith("_")} if isinstance(meta, dict) else {}
    normalized = []
    seen = set()
    for p in procs:
        token = _norm(p)
        if not token:
            continue
        canon = alias.get(token)
        if canon is None and token in catalog:
            canon = token
        if canon is None:
            canon = "others" if catalog else token
        elif catalog and canon not in catalog:
            canon = "others"
        if canon not in seen:
            seen.add(canon)
            normalized.append(canon)
    return normalized

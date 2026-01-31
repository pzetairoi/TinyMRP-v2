# app/services/filescan.py
import os, re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

from flask import current_app
from app.models.artifact import PartFile

def _roots():
    """Return (local_root, http_base) from unified app config.
    Reads canonical FILES_LOCAL_ROOT and FILES_URL_PREFIX, falling back to
    legacy FILE_ROOT_LOCAL/FILE_ROOT_HTTP if present.
    """
    cfg = current_app.config
    local_root = (cfg.get("FILES_LOCAL_ROOT") or cfg.get("FILE_ROOT_LOCAL") or "").strip()
    http_root  = (cfg.get("FILES_URL_PREFIX") or cfg.get("FILE_ROOT_HTTP")  or "").strip()
    if not local_root and not http_root:
        return None, None
    return local_root, http_root

def _expectations_for(pn: str, rev: str) -> List[Tuple[str, str, bool]]:
    """
    Return list of expected (ext_group, suffix, is_dwg).
    We only special-case PNG:
      - normal preview: {base}.png
      - drawing screenshot: {base}_DWG.png
    """
    # Build candidate basenames in multiple case variants to be robust
    # against filename capitalization differences.
    rev_str = (rev or "")
    base_upper = f"{pn.upper()}_REV_{rev_str.upper()}" if rev_str else f"{pn.upper()}_REV_"
    base_raw   = f"{pn}_REV_{rev_str}" if rev is not None else f"{pn}_REV_"

    # Also consider variant without the _REV_ segment when revision is empty.
    base_no_rev_upper = pn.upper()
    base_no_rev_raw   = pn

    wants: List[Tuple[str, str, bool]] = []
    # png - preview (multiple candidates)
    for b in (base_upper, base_raw) + ((base_no_rev_upper, base_no_rev_raw) if not rev_str else ()):  # type: ignore
        wants.append(("png",  f"{b}.png", False))
        # png - drawing screen
        wants.append(("png",  f"{b}_DWG.png", True))
    # others (one-per-extension)
    for grp, exts in [
        ("pdf",  ("pdf",)),
        ("dxf",  ("dxf",)),
        ("step", ("step","stp")),
        ("edr",  ("edr","eprt","easm","EDR","EPRT","EASM")),
        ("3mf",  ("3mf",)),
        ("ply",  ("ply",)),
        ("stl",  ("stl",)),
        ("datasheet", ("pdf","jpg","jpeg","png")),
    ]:
        # store exactly one file per ext_group -> we’ll accept any of these concrete exts
        # filename is still strictly base + "." + ext (no _DWG here)
        for ext in exts:
            for b in (base_upper, base_raw) + ((base_no_rev_upper, base_no_rev_raw) if not rev_str else ()):  # type: ignore
                wants.append((grp, f"{b}.{ext}", False))
    return wants

def _find_case_insensitive(local_root: Path, rel: str) -> Path | None:
    """
    Try to find file 'rel' under local_root, case-insensitive for both dirs and filename.
    """
    parts = Path(rel).parts
    cur = local_root
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            # filename: select first matching ignoring case
            try:
                # if exact exists
                p = cur / part
                if p.exists():
                    return p
            except Exception:
                pass
            low = part.lower()
            for cand in cur.iterdir():
                if cand.name.lower() == low and cand.is_file():
                    return cand
            return None
        else:
            # directory level
            nextd = cur / part
            if nextd.exists() and nextd.is_dir():
                cur = nextd
            else:
                low = part.lower()
                found = None
                for d in cur.iterdir():
                    if d.is_dir() and d.name.lower() == low:
                        found = d
                        break
                if not found:
                    return None
                cur = found
    return None

def _rel_path_for(candidate: Path, local_root: Path) -> str:
    
    return str(candidate.relative_to(local_root)).replace("\\","/")

def discover_part_files(pn: str, rev: str) -> Dict[Tuple[str,bool], Dict]:
    """
    Return a dict keyed by (ext_group, is_dwg) -> record {ext, rel_path, http_url, size, mtime_iso}
    Only one record per key; if multiple matches exist, last-modified wins.
    """
   #print("discover",pn,rev)
    local, http = _roots()
   #print(local,http)
    if not local:
        return {}
    local_root = Path(local)

    found: Dict[Tuple[str,bool], Dict] = {}
    # We search by expected relative paths from the known subfolders (png, pdf, dxf, step, edr, 3mf, ply, stl, datasheet).
    # The repo uses subfolders named as ext_groups.
    folders = ("png","pdf","dxf","step","edr","3mf","ply","stl","datasheet")
   #print(folders)
    for ext_group, leaf, is_dwg in _expectations_for(pn, rev):
        # try in the matching folder (png in png/, pdf in pdf/, …)
        subdir = ext_group
        candidate_rel = f"{subdir}/{leaf}"
       #print("candidate_rel",candidate_rel)
        p = _find_case_insensitive(local_root, candidate_rel)
       #print("p",p)
        if not p:
            continue
        stat = p.stat()
        key = (ext_group, is_dwg)
        record = {
            "ext": p.suffix.lstrip("."),
            "rel_path": _rel_path_for(p, local_root),
            "http_url": (http.rstrip("/") + "/" + _rel_path_for(p, local_root)) if http else None,
            "size": float(stat.st_size),
            "mtime_iso": datetime.fromtimestamp(stat.st_mtime),
            "is_dwg": is_dwg,
        }
        
        # keep the newest if duplicate
        prev = found.get(key)
        if prev and prev["mtime_iso"] >= record["mtime_iso"]:
            continue
        found[key] = record
       #print("key",key)
       #print("record",record)

    return found



def _group_from_ext(ext: str) -> Optional[str]:
    ext = (ext or "").lower()
    if ext in {"png"}: return "png"
    if ext in {"pdf"}: return "pdf"
    if ext in {"dxf"}: return "dxf"
    if ext in {"step", "stp"}: return "step"
    if ext in {"eprt", "easm", "edrw"}: return "edr"
    if ext in {"3mf"}: return "3mf"
    if ext in {"ply"}: return "ply"
    if ext in {"stl"}: return "stl"
    return None
# app/services/filescan.py

def upsert_part_files(
    recs: List[Dict[str, Any]],
    pn: Optional[str] = None,
    rev: Optional[str] = None,
) -> int:
    """
    Upsert a batch of file records.
    - recs: list of dicts (each may include pn/part_number, rev/revision,
      ext_group/group, ext, rel_path, size, mtime_iso, http_url, is_dwg, etc.)
    - pn, rev: optional defaults applied to all records when missing.
    Returns number of upserts attempted.
    """
    n = 0
    for r in recs or []:
        #print("upsert", r)

        rpn = pn or r.get("pn") or r.get("part_number")
        rrev = (rev if rev is not None else r.get("rev") or r.get("revision") or "")
        group = (r.get("ext_group") or r.get("group") or "").lower()
        ext = (r.get("ext") or "").lower()
        is_dwg = bool(r.get("is_dwg"))

        if not rpn or ext == "":
            # Not enough to identify the artifact; skip quietly
            continue

        # Unique key for your "one file per ext_group+ext per (pn,rev)" rule
        query = dict(part_number=rpn, revision=rrev, ext_group=group, ext=ext, is_dwg=is_dwg)
        #print("query", query)

        # Allowed fields from the model
        allowed = set(PartFile._fields.keys())
        #print("allowed", allowed)

        # Build atomic updates for modify()
        updates: Dict[str, Any] = {}

        # Normalized rel_path -> also use as unique, non-null `path`
        rel_path = r.get("rel_path") or ""
        norm_rel = rel_path.replace("\\", "/").lstrip("/")
        
        #print(rel_path, norm_rel)

        if "rel_path" in allowed and norm_rel:
            updates["set__rel_path"] = norm_rel

        # Ensure `path` is set to a non-null, unique value (avoid dup key on path_1)
        # We intentionally use rel_path (not absolute) to keep it stable & portable.
        if "path" in allowed and norm_rel:
            updates["set__path"] = norm_rel

        # Pass through common metadata if present
        if "http_url" in r and "http_url" in allowed:
            updates["set__http_url"] = r["http_url"]
        if "urls" in r and "urls" in allowed:
            updates["set__urls"] = r["urls"]
        if "size" in r and "size" in allowed:
            updates["set__size"] = r["size"]
        if "mtime_iso" in r and "mtime_iso" in allowed:
            updates["set__mtime_iso"] = r["mtime_iso"]
        if "is_dwg" in r and "is_dwg" in allowed:
            updates["set__is_dwg"] = r["is_dwg"]
        if "content_type" in r and "content_type" in allowed:
            updates["set__content_type"] = r["content_type"]

        # Optional: stamp first discovery without touching on updates
        if "discovered_at" in allowed:
            updates.setdefault("set_on_insert__discovered_at", datetime.utcnow())

        # Safety: never send an empty update
        if not updates:
            continue

        #print("updates", updates)

        # Upsert
        PartFile.objects(**query).modify(upsert=True, new=True, **updates)  # type: ignore
        n += 1

    return n

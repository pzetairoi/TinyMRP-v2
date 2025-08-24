# app/services/filescan.py
import os, re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

from flask import current_app
from app.models.artifact import PartFile

def _roots():
    """Return (local_root, http_base) from config FILE_ROOTS = [{"local": "...", "http": "..."}]."""

    local_root= (os.getenv("FILE_ROOT_LOCAL") or "").strip()
    http_root=(os.getenv("FILE_ROOT_HTTP")  or "").strip()
    print(local_root,http_root)
    # We only support the first root in the simplified setup
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
    print("expect",pn,rev)
    base = f"{pn}_REV_{rev or ''}"
    wants = []
    # png - preview
    wants.append(("png",  f"{base}.png", False))
    # png - drawing screen
    wants.append(("png",  f"{base}_DWG.png", True))
    # others (one-per-extension)
    for grp, exts in [
        ("pdf",  ("pdf",)),
        ("dxf",  ("dxf",)),
        ("step", ("step","stp")),
        ("edr",  ("edr","eprt","easm","EDR","EPRT","EASM")),
        ("3mf",  ("3mf",)),
        ("datasheet", ("pdf","jpg","jpeg","png")),
    ]:
        # store exactly one file per ext_group -> we’ll accept any of these concrete exts
        # filename is still strictly base + "." + ext (no _DWG here)
        for ext in exts:
            wants.append((grp, f"{base}.{ext}", False))
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
    print("discover",pn,rev)
    local, http = _roots()
    print(local,http)
    if not local:
        return {}
    local_root = Path(local)

    found: Dict[Tuple[str,bool], Dict] = {}
    # We search by expected relative paths from the known subfolders (png, pdf, dxf, step, edr, 3mf, datasheet).
    # The repo uses subfolders named as ext_groups.
    folders = ("png","pdf","dxf","step","edr","3mf","datasheet")
    print(folders)
    for ext_group, leaf, is_dwg in _expectations_for(pn, rev):
        # try in the matching folder (png in png/, pdf in pdf/, …)
        subdir = ext_group
        candidate_rel = f"{subdir}/{leaf}"
        p = _find_case_insensitive(local_root, candidate_rel)
        print("p",p)
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
        print("key",key)
        print("record",record)

    return found



def _group_from_ext(ext: str) -> Optional[str]:
    ext = (ext or "").lower()
    if ext in {"png"}: return "png"
    if ext in {"pdf"}: return "pdf"
    if ext in {"dxf"}: return "dxf"
    if ext in {"step", "stp"}: return "step"
    if ext in {"eprt", "easm", "edrw"}: return "edr"
    if ext in {"3mf"}: return "3mf"
    return None

def upsert_part_files(
    recs: List[Dict[str, Any]],
    pn: Optional[str] = None,
    rev: Optional[str] = None,
) -> int:
    n = 0
    for r in recs or []:
        if not isinstance(r, dict):
            continue

        print("upsert", r)

        rpn  = pn
        rrev = rev if rev is not None else ""
        ext  = (r.get("ext") or "").lower()
        group = (r.get("ext_group") or r.get("group") or "").lower()

        # derive group if missing
        if not group:
            rp = r.get("rel_path") or ""
            if isinstance(rp, str) and "/" in rp:
                group = rp.split("/", 1)[0].lower()
            if not group:
                group = _group_from_ext(ext) or "others"

        if not rpn or not ext:
            # cannot uniquely identify
            continue

        print("upsert key", rpn, rrev, group, ext)
        query = dict(part_number=rpn, revision=rrev, ext_group=group, ext=ext)
        print("query", query)

        allowed = set(PartFile._fields.keys())  # type: ignore[attr-defined]
        print("allowed", allowed)

        # Normalize fields we write
        update_doc: Dict[str, Any] = {}
        for k in ("rel_path", "size", "mtime", "mtime_iso", "is_dwg", "http_url", "url", "thumb_rel_path", "thumb_mtime"):
            if k in r and k in allowed:
                update_doc[k] = r[k]

        # Expand into MongoEngine update kwargs (avoid set__=dict)
        updates = {f"set__{k}": v for k, v in update_doc.items()}
        print("updates", updates)

        PartFile.objects(**query).modify(upsert=True, new=True, **updates)  # type: ignore
        n += 1

    return n
# app/services/filescan.py
import os, re, hashlib, mimetypes
from datetime import datetime, timezone
from typing import Dict, List, Iterable
from app.models.artifact import PartFile

# Subfolder name -> allowed extensions
EXT_MAP: Dict[str, List[str]] = {
    "pdf":  [".pdf"],
    "dxf":  [".dxf"],
    "step": [".step", ".stp"],
    "edr":  [".eprt", ".easm", ".edrw", ".eprtx", ".easmtx", ".edrwt"],
    "png":  [".png"],
    "3mf":  [".3mf"],
    # add more if needed
}

def _sha256(path: str, limit_bytes: int) -> str:
    if limit_bytes <= 0:
        return ""
    try:
        sz = os.path.getsize(path)
        if sz > limit_bytes:
            return ""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def _guess_ct(path: str) -> str:
    ct, _ = mimetypes.guess_type(path)
    return ct or "application/octet-stream"

def _build_patterns(pn: str, rev: str):
    """
    Return regexes (case-insensitive) for filename stem. We try strict first,
    then a slightly relaxed variant that allows suffixes like '_REV_A_v2' etc.
    """
    esc_pn  = re.escape(pn)
    esc_rev = re.escape(rev)
    strict  = re.compile(rf'^{esc_pn}_REV_{esc_rev}$', re.IGNORECASE)
    loose   = re.compile(rf'^{esc_pn}_REV_{esc_rev}(?:[\s_\-].*)?$', re.IGNORECASE)
    return strict, loose

def _norm_path(p: str) -> str:
    return p.replace("\\", "/")

def _safe_rel(path: str, root: str) -> str | None:
    try:
        rp = os.path.relpath(path, root)
        if rp.startswith(".."):
            return None
        return _norm_path(rp)
    except Exception:
        return None

def discover_part_files(part_number: str, revision: str, roots: Iterable[dict], hash_limit_bytes: int = 0) -> List[Dict]:
    pn = (part_number or "").strip()
    rv = (revision or "").strip()
    if not pn or not rv:
        return []

    strict, loose = _build_patterns(pn, rv)
    found: List[Dict] = []

    for idx, root in enumerate(roots or []):
        base = (root.get("local") or "").strip()
        if not base or not os.path.isdir(base):
            continue

        for ext_group, exts in EXT_MAP.items():
            folder = os.path.join(base, ext_group)
            if not os.path.isdir(folder):
                continue

            # Recurse in subfolders: png/**/*
            for dirpath, _, filenames in os.walk(folder):
                for name in filenames:
                    name_cf = name.casefold()
                    if not any(name_cf.endswith(e) for e in [x.lower() for x in exts]):
                        continue
                    stem = os.path.splitext(name)[0]
                    # First try strict, then loose
                    if not strict.match(stem) and not loose.match(stem):
                        continue

                    full = os.path.join(dirpath, name)
                    try:
                        st = os.stat(full)
                    except OSError:
                        continue

                    rel_path = _safe_rel(full, base)
                    if rel_path is None:
                        continue

                    rec = {
                        "part_number": pn,
                        "revision": rv,
                        "ext_group": ext_group,
                        "ext": os.path.splitext(name)[1].lower(),
                        "path": full,
                        "rel_path": rel_path,  # includes the ext_group, e.g. "png/PN_REV_A.png" or "png/sub/f.png"
                        "root_idx": idx,
                        "size": st.st_size,
                        "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
                        "sha256": _sha256(full, hash_limit_bytes) if hash_limit_bytes else "",
                        "content_type": _guess_ct(full),
                        "source": "scan",
                        "meta_info": {},
                    }
                    found.append(rec)
    return found

def upsert_part_files(records: List[Dict]) -> int:
    inserts = 0
    for r in records:
        doc = PartFile.objects(path=r["path"]).first()
        if doc:
            # update metadata
            for k in ("part_number","revision","ext_group","ext","rel_path","root_idx","size","mtime","content_type"):
                setattr(doc, k, r.get(k))
            if r.get("sha256"):
                doc.sha256 = r["sha256"]
            meta = doc.meta_info or {}
            meta.update(r.get("meta_info") or {})
            doc.meta_info = meta
            doc.save()
        else:
            PartFile(**r).save()
            inserts += 1
    return inserts

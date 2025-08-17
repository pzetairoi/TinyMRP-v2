# app/services/filescan.py
import os, re, hashlib, mimetypes
from datetime import datetime, timezone
from typing import Dict, List
from flask import current_app
from app.models.artifact import PartFile

EXT_MAP: Dict[str, List[str]] = {
    "pdf":  [".pdf"],
    "dxf":  [".dxf"],
    "step": [".step", ".stp"],
    "edr":  [".eprt", ".easm", ".edrw", ".eprtx", ".easmtx", ".edrwt"],
    "png":  [".png"],   # add ".jpg", ".jpeg" if needed
    "3mf":  [".3mf"],
}

def _sha256(path: str, limit_bytes: int) -> str:
    if limit_bytes <= 0: return ""
    try:
        if os.path.getsize(path) > limit_bytes: return ""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""

def _guess_ct(path: str) -> str:
    ct, _ = mimetypes.guess_type(path)
    return ct or "application/octet-stream"

def _match_stem(pn: str, rev: str, stem: str) -> bool:
    """
    True if filename 'stem' corresponds to (pn, rev).
    - Normal case: <PN>_REV_<REV> (strict), but accept suffixes: ...[_ -]<anything>
    - Empty rev: accept either:
        * exactly <PN>
        * <PN>_REV   (no trailing underscore)
        * <PN>_REV_  (trailing underscore)
      and allow suffixes after those with [_ -]...
    All case-insensitive.
    """
    esc_pn = re.escape(pn)
    if rev:
        esc_rev = re.escape(rev)
        strict  = re.compile(rf'^{esc_pn}_REV_{esc_rev}$', re.IGNORECASE)
        loose   = re.compile(rf'^{esc_pn}_REV_{esc_rev}(?:[\s_\-].+)?$', re.IGNORECASE)
        return bool(strict.match(stem) or loose.match(stem))
    else:
        # empty revision
        pat_exact = re.compile(rf'^{esc_pn}$', re.IGNORECASE)
        pat_rev   = re.compile(rf'^{esc_pn}_REV_?$', re.IGNORECASE)            # PN_REV or PN_REV_
        pat_loose = re.compile(rf'^(?:{esc_pn}|{esc_pn}_REV_?)(?:[\s_\-].+)?$', re.IGNORECASE)
        return bool(pat_exact.match(stem) or pat_rev.match(stem) or pat_loose.match(stem))

def _rel_from_root(full_path: str, root: str) -> str | None:
    try:
        rp = os.path.relpath(full_path, root)
        if rp.startswith(".."): return None
        return rp.replace("\\", "/")
    except Exception:
        return None

def discover_part_files_single_root(part_number: str, revision: str) -> List[Dict]:
    pn = (part_number or "").strip()
    rv = (revision or "")  # allow empty string intentionally
    if not pn: return []

    root = (current_app.config.get("FILE_ROOT_LOCAL") or "").strip()
    if not root or not os.path.isdir(root): return []

    found: List[Dict] = []

    for ext_group, exts in EXT_MAP.items():
        folder = os.path.join(root, ext_group)
        if not os.path.isdir(folder): continue

        for dirpath, _, filenames in os.walk(folder):
            for name in filenames:
                name_cf = name.casefold()
                if not any(name_cf.endswith(e) for e in [x.lower() for x in exts]): continue
                stem = os.path.splitext(name)[0]
                if not _match_stem(pn, rv, stem):
                    continue

                full = os.path.join(dirpath, name)
                try: st = os.stat(full)
                except OSError: continue

                rel = _rel_from_root(full, root)
                if rel is None: continue

                rec = {
                    "part_number": pn,
                    "revision": rv,  # may be ""
                    "ext_group": ext_group,
                    "ext": os.path.splitext(name)[1].lower(),
                    "path": full,
                    "rel_path": rel,
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
                    "sha256": _sha256(full, int(current_app.config.get("FILE_HASH_MAX_BYTES", 0) or 0)),
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
            for k in ("part_number","revision","ext_group","ext","rel_path","size","mtime","content_type"):
                setattr(doc, k, r.get(k))
            if r.get("sha256"): doc.sha256 = r["sha256"]
            meta = doc.meta_info or {}
            meta.update(r.get("meta_info") or {})
            doc.meta_info = meta
            doc.save()
        else:
            PartFile(**r).save()
            inserts += 1
    return inserts

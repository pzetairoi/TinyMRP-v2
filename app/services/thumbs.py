from typing import List, Optional
from flask import current_app
from app.models.artifact import PartFile
from app.services.files_access import file_url_for, public_file_urls_enabled

def _urls_for(pn: str, rev: Optional[str], *, is_dwg: bool):
    """Return best-first URLs for preview/drawing PNGs.

    Order: preview prefers thumbnails; drawings prefer originals.
    """
    if rev is not None:
        rev_clean = rev or ""
        rows = PartFile.objects(part_number__iexact=pn, revision__iexact=rev_clean, ext_group="png", is_dwg=is_dwg)
        if not rows:
            return []
    else:
        rows = PartFile.objects(part_number__iexact=pn, ext_group="png", is_dwg=is_dwg).order_by("-mtime")
        if not rows:
            return []
    pf = rows.first()

    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    prefer_thumb = not is_dwg
    out = _urls_for_doc(pf, http_base, prefer_thumb=prefer_thumb)
    return _dedup_urls(out)

def preview_png_urls_for(pn: str, rev: str | None):
    return _urls_for(pn, rev, is_dwg=False)

def drawing_png_urls_for(pn: str, rev: str | None):
    return _urls_for(pn, rev, is_dwg=True)

# kept for backward compat – use only for places that truly want preview images
def thumb_urls_for(pn: str, rev: str | None):
    return preview_png_urls_for(pn, rev)


# helper: build URL list for a single PartFile doc
def _urls_for_doc(d: PartFile, http_base: str, *, prefer_thumb: bool = True) -> List[str]:
    urls: List[str] = []
    allow_public = public_file_urls_enabled()
    if prefer_thumb and allow_public and http_base and d.thumb_rel_path:
        urls.append(f"{http_base}/{d.thumb_rel_path}")
    if allow_public and http_base and d.rel_path:
        urls.append(f"{http_base}/{d.rel_path}")
    if allow_public and getattr(d, "http_url", None):
        urls.append(d.http_url)
    # fallback to tokenized local file using signed token
    try:
        if prefer_thumb and d.thumb_rel_path:
            urls.append(file_url_for(d, kind="thumb"))
        urls.append(file_url_for(d, kind="file"))
    except Exception:
        pass
    return urls

def _dedup_urls(urls: List[str]) -> List[str]:
    seen = set()
    dedup: List[str] = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup

def drawing_urls_for(pn: str, rev_pref: Optional[str]) -> List[str]:
    """
    Prefer PNG artifacts whose rel_path contains '_DWG' (case-insensitive).
    If none exist, fall back to thumb_urls_for(pn, rev_pref).
    Returns best-first URL list: HTTP thumbnail -> HTTP original -> token fallback.
    """
    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    q = (PartFile.objects(part_number__iexact=pn, ext_group="png")
         .only("path", "rel_path", "thumb_rel_path", "revision", "mtime")
         .order_by("-mtime", "path"))
    docs = list(q)
    if not docs:
        return thumb_urls_for(pn, rev_pref)

    def is_dwg(d: PartFile) -> bool:
        return "_DWG" in ((d.rel_path or d.path or "").upper())

    # If revision provided, stay within that revision only.
    if rev_pref is not None:
        pref = rev_pref or ""
        docs = [d for d in docs if (d.revision or "") == pref]
        if not docs:
            return thumb_urls_for(pn, pref)

    dwg_docs = [d for d in docs if is_dwg(d)]
    if dwg_docs:
        return _dedup_urls(_urls_for_doc(dwg_docs[0], http_base, prefer_thumb=False))

    # fallback to standard thumbnail policy
    return thumb_urls_for(pn, rev_pref)

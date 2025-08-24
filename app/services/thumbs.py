import base64
from typing import List, Optional
from flask import current_app
from app.models.artifact import PartFile

def _token_for(path: str) -> str:
    return base64.urlsafe_b64encode((path or "").encode("utf-8")).decode("ascii")

def _urls_for(pn: str, rev: str, *, is_dwg: bool):
    rows = PartFile.objects(part_number=pn, revision=rev, ext_group="png", is_dwg=is_dwg)
    if not rows:
        return []
    pf = rows.first()
    # return preferred http_url first, you already have a /files/view token fallback elsewhere if needed
    out = []
    if pf.http_url:
        out.append(pf.http_url)
    # (optional) fallback: tokenized local
    out.append(f"/files/view/{pf.rel_path.encode('utf-8').hex()}")  # keep your existing token if you have one
    return out

def preview_png_urls_for(pn: str, rev: str | None):
    return _urls_for(pn, (rev or ""), is_dwg=False)

def drawing_png_urls_for(pn: str, rev: str | None):
    return _urls_for(pn, (rev or ""), is_dwg=True)

# kept for backward compat – use only for places that truly want preview images
def thumb_urls_for(pn: str, rev: str | None):
    return preview_png_urls_for(pn, rev)


# helper: build URL list for a single PartFile doc
def _urls_for_doc(d: PartFile, http_base: str) -> List[str]:
    urls: List[str] = []
    if http_base and d.thumb_rel_path:
        urls.append(f"{http_base}/{d.thumb_rel_path}")
    if http_base and d.rel_path:
        urls.append(f"{http_base}/{d.rel_path}")
    # fallback to tokenized local file
    urls.append(f"/files/view/{_token_for(d.path)}")
    return urls

def drawing_urls_for(pn: str, rev_pref: Optional[str]) -> List[str]:
    """
    Prefer PNG artifacts whose rel_path contains '_DWG' (case-insensitive).
    If none exist, fall back to thumb_urls_for(pn, rev_pref).
    Returns best-first URL list: HTTP thumbnail -> HTTP original -> token fallback.
    """
    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    q = (PartFile.objects(part_number=pn, ext_group="png")
         .only("path", "rel_path", "thumb_rel_path", "revision", "mtime")
         .order_by("-mtime", "path"))
    docs = list(q)
    if not docs:
        # nothing at all, keep existing behavior
        return thumb_urls_for(pn, rev_pref)

    def is_dwg(d: PartFile) -> bool:
        return "_DWG" in ((d.rel_path or "").upper())

    dwg_docs = [d for d in docs if is_dwg(d)]

    # try to honor requested revision first (including empty "")
    if rev_pref is not None:
        pref = rev_pref or ""
        for d in dwg_docs:
            if (d.revision or "") == pref:
                return _urls_for_doc(d, http_base)

    # otherwise first drawing if any
    if dwg_docs:
        return _urls_for_doc(dwg_docs[0], http_base)

    # fallback to standard thumbnail policy
    return thumb_urls_for(pn, rev_pref)

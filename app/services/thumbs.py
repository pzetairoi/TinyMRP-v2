import base64
from typing import List, Optional
from flask import current_app
from app.models.artifact import PartFile

def _token_for(path: str) -> str:
    return base64.urlsafe_b64encode((path or "").encode("utf-8")).decode("ascii")

def thumb_urls_for(pn: str, rev_pref: Optional[str]) -> List[str]:
    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    # 1) pick best PNG doc
    q = PartFile.objects(part_number=pn, ext_group="png").only("path","rel_path","thumb_rel_path","revision","mtime").order_by("-mtime","path")
    if not q:
        return []
    docs = list(q)
    pick = None
    if rev_pref is not None:
        if rev_pref == "":
            for d in docs:
                if (d.revision or "") == "":
                    pick = d; break
        else:
            for d in docs:
                if (d.revision or "") == rev_pref:
                    pick = d; break
    if pick is None:
        pick = next((d for d in docs if (d.revision or "") == ""), None) or docs[0]

    urls: List[str] = []
    # 2) prefer thumbnail URL if present (http + thumb_rel_path)
    if http_base and pick.thumb_rel_path:
        urls.append(f"{http_base}/{pick.thumb_rel_path}")
    # 3) else fall back to original http rel_path
    if http_base and pick.rel_path and f"{http_base}/{pick.rel_path}" not in urls:
        urls.append(f"{http_base}/{pick.rel_path}")
    # 4) always include token fallback
    urls.append(f"/files/view/{_token_for(pick.path)}")
    return urls


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

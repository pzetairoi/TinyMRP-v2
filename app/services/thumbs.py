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

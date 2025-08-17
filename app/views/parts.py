# app/views/parts.py
from flask import Blueprint, request, jsonify
from mongoengine.queryset.visitor import Q
from app.models.part import Part
from app.extensions import csrf

bp = Blueprint("parts_api", __name__, url_prefix="/api")

@bp.post("/parts_lazy")
@csrf.exempt 
def parts_lazy():
    body = request.get_json(force=True, silent=True) or {}
    first = int(body.get("first", 0))
    rows = int(body.get("rows", 25))
    sort_field = (body.get("sortField") or "part_number")
    sort_order = int(body.get("sortOrder", 1))  # 1 asc, -1 desc
    order_by = f"-{sort_field}" if sort_order == -1 else sort_field
    filters = body.get("filters", {})

    ALLOWED = {"part_number", "description", "category"}
    if sort_field not in ALLOWED:
        sort_field = "part_number"
    order_by = f"-{sort_field}" if sort_order == -1 else sort_field

    def add_filter(q: Q, field: str):
        f = filters.get(field) or {}
        val = (f.get("value") or "").strip()
        mode = (f.get("matchMode") or "contains")
        if not val:
            return q
        suffix = {
            "contains": "icontains",
            "equals": "iexact",
            "startsWith": "istartswith",
            "endsWith": "iendswith",
        }.get(mode, "icontains")
        return q & Q(**{f"{field}__{suffix}": val})

    q = Q()
    for fld in ("part_number", "description", "category"):
        q = add_filter(q, fld)

    qs = Part.objects(q)
    filtered = qs.count()

    docs = qs.order_by(order_by).only("part_number", "description", "category").skip(first).limit(rows)
    data = [{"part_number": p.part_number, "description": p.description or "", "category": p.category or ""} for p in docs]

    return jsonify({"data": data, "totalRecords": filtered})






# app/views/parts.py (append at bottom)
from flask import request, jsonify, abort, current_app
from app.models.part import Part
from app.models.bom import BOMLink
from app.models.artifact import PartFile
import base64

def _token_url(path: str) -> str:
    tok = base64.urlsafe_b64encode((path or "").encode("utf-8")).decode("ascii")
    return f"/files/view/{tok}"

@bp.get("/part_detail")
@csrf.exempt  # GET only; CSRF not required
def part_detail():
    pn = (request.args.get("pn") or "").strip()
    if not pn:
        return jsonify({"error": "pn required"}), 400

    p = Part.objects(part_number=pn).first()
    if not p:
        abort(404)

    rev = (p.revision or "").strip()
    # Children (one level)
    links = list(BOMLink.objects(parent_pn=pn))
    child_pns = [l.child_pn for l in links]
    parts_map = {x.part_number: x for x in Part.objects(part_number__in=child_pns)}
    children = [{
        "child_pn": l.child_pn,
        "child_desc": (parts_map.get(l.child_pn).description or "") if parts_map.get(l.child_pn) else "",
        "qty": float(l.qty or 1.0),
        "uom": l.uom or "EA",
        "alt_group": l.alt_group or "",
    } for l in links]

    # Where-used (parents)
    pulinks = list(BOMLink.objects(child_pn=pn))
    parent_pns = [l.parent_pn for l in pulinks]
    parents_map = {x.part_number: x for x in Part.objects(part_number__in=parent_pns)}
    whereused = [{
        "parent_pn": l.parent_pn,
        "parent_desc": (parents_map.get(l.parent_pn).description or "") if parents_map.get(l.parent_pn) else "",
        "qty": float(l.qty or 1.0),
        "uom": l.uom or "EA",
        "alt_group": l.alt_group or "",
    } for l in pulinks]

    # Files & images — prefer empty revision if the part's own revision is ""
    http_base = (current_app.config.get("FILE_ROOT_HTTP") or "").rstrip("/")
    files: list[dict] = []

    def add_files(q):
        for f in PartFile.objects(**q).order_by("ext_group", "rel_path"):
            urls = []
            if http_base and f.rel_path:
                urls.append(f"{http_base}/{f.rel_path}")
            tok = base64.urlsafe_b64encode((f.path or "").encode("utf-8")).decode("ascii")
            urls.append(f"/files/view/{tok}")
            files.append({
                "ext_group": f.ext_group,
                "ext": f.ext,
                "rel_path": f.rel_path,
                "size": f.size,
                "mtime": f.mtime.isoformat() if f.mtime else None,
                "url": urls[0],
                "urls": urls,
            })

    if rev == "":
        add_files({"part_number": pn, "revision": ""})
    else:
        # try exact rev first; if none, prefer empty; then fall back to latest
        add_files({"part_number": pn, "revision": rev})
        if not files:
            add_files({"part_number": pn, "revision": ""})
        if not files:
            all_docs = list(PartFile.objects(part_number=pn).order_by("-mtime", "path"))
            if all_docs:
                latest = (all_docs[0].revision or "")
                add_files({"part_number": pn, "revision": latest})

    images = [x for x in files if x["ext_group"] == "png"]


    return jsonify({
        "part": {
            "part_number": p.part_number,
            "description": p.description or "",
            "revision": rev,
            "category": p.category or "",
            "uom": p.uom or "EA",
            "attrs": (p.attrs or {}),
        },
        "images": images,
        "files": files,
        "children": children,
        "whereused": whereused,
    })

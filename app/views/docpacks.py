from __future__ import annotations
from flask import Blueprint, request, send_file, jsonify
from flask_login import login_required, current_user
from io import BytesIO
from typing import List

from app.services.docpacks import DocPackOptions, build_docpack
from app.services.acl import allowed_parts_for, part_is_allowed
from app.services.acl import require_items_view
from app.services.audit import log_action

bp = Blueprint("docpacks_api", __name__, url_prefix="/api/docpacks")


@bp.get("/options")
@login_required
@require_items_view
def options():
    from app.models.part import Part
    from app.models.bom import BOMLink
    from app.models.artifact import PartFile
    from app.services.docpacks import _flatten_bom
    from flask import current_app

    pn = (request.args.get("pn") or "").strip()
    rev = request.args.get("rev")
    depth = (request.args.get("depth") or "full").lower()
    if not pn:
        return jsonify({"error":"missing pn"}), 400

    # ACL: enforce root access
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, pn, rev or ""):
            return jsonify({"error":"forbidden"}), 403
    except Exception:
        pass
    flat = _flatten_bom(pn, rev, full=(depth != "top"))
    # include the root itself for artifacts
    flat.append((pn, rev or "", 1.0))

    # ext_groups seen
    groups = set()
    for pnr, r, _ in flat:
        q = PartFile.objects(part_number__iexact=pnr)
        if r is not None:
            q = q.filter(revision__iexact=(r or ""))
        for f in q.only("ext_group"):
            if f.ext_group:
                groups.add(f.ext_group)

    # process list from PROCESS_META (canonical names)
    meta = current_app.config.get("PROCESS_META", {})
    procs = [k for k in meta.keys() if not k.startswith("_")]

    try:
        # pn/rev already parsed above
        log_action("docpack.options", resource_type="docpack", resource=f"{pn}:{rev or ''}")
    except Exception:
        pass
    return jsonify({
        "file_types": sorted(groups),
        "processes": sorted(procs),
    })

@bp.post("/build")
@login_required
@require_items_view
def build():
    # Accept JSON, form, or querystring inputs (robust for manual calls)
    payload = request.get_json(silent=True) or {}
    data = request.form or {}
    args = request.args or {}

    def gv(key: str, default=None):
        if key in payload: return payload.get(key)
        if key in data: return data.get(key)
        if key in args: return args.get(key)
        return default

    def _list(key: str) -> List[str]:
        v = gv(key)
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
        return [str(v)]

    def _has_key(key: str) -> bool:
        return key in payload or key in data or key in args

    # Robust PN/REV resolution (supports multiple legacy keys)
    _pn = gv("pn") or gv("part_number") or gv("partnumber") or gv("root_pn") or gv("root")
    _rev = gv("rev") if gv("rev") is not None else (gv("revision") if gv("revision") is not None else None)

    output_name = gv("output_name") if _has_key("output_name") else gv("filename") if _has_key("filename") else None
    if output_name is not None and not str(output_name).strip():
        return jsonify({"error": "Requires a file name"}), 400

    opts = DocPackOptions(
        root_pn=str(_pn or "").strip(),
        root_rev=_rev,
        depth=(str(gv("depth") or "full")).lower(),
        include_consumed=bool(gv("include_consumed") in (True, "true", "1", 1, "on")),
        classified_filter=(str(gv("classified") or "show")).lower(),
        processes=[p for p in _list("processes") if p],
        process_mode=(str(gv("process_mode") or "all")).lower(),
        file_types=[t for t in _list("file_types") if t],
        want_excel_bom=bool(gv("excel_bom") in (True, "true", "1", 1, "on")),
        excel_all_fields=bool(gv("excel_all_fields") in (True, "true", "1", 1, "on")),
        want_selected_files=bool(gv("selected_files") in (True, "true", "1", 1, "on")),
        want_pdf_binder=bool(gv("pdf_binder") in (True, "true", "1", 1, "on")),
        want_index_pdf=bool(gv("index_pdf") in (True, "true", "1", 1, "on") or gv("index") in (True, "true", "1", 1, "on")),
        want_visual_list=bool(gv("visual_list") in (True, "true", "1", 1, "on")),
        want_hardware_summary=bool(
            gv("hardware_summary") in (True, "true", "1", 1, "on")
            or gv("hardware_list") in (True, "true", "1", 1, "on")
        ),
        want_cover_page=bool(gv("cover_page") in (True, "true", "1", 1, "on")),
        want_whereused_report=bool(gv("whereused_report") in (True, "true", "1", 1, "on")),
        binder_add_cover=bool(gv("binder_add_cover") not in (False, None, "false", "0", 0)),
        binder_add_visual_list=bool(gv("binder_add_visual_list") not in (False, None, "false", "0", 0)),
        binder_add_whereused=bool(gv("binder_add_whereused") in (True, "true", "1", 1, "on")),
        binder_add_index=bool(gv("binder_add_index") not in (False, None, "false", "0", 0)),
        binder_add_datasheets=bool(gv("binder_add_datasheets") in (True, "true", "1", 1, "on")),
        binder_add_hardware_summary=bool(gv("binder_add_hardware_summary") not in (False, None, "false", "0", 0)),
        binder_page_numbers=bool(gv("binder_page_numbers") not in (False, None, "false", "0", 0)),
        binder_include_flat_patterns=bool(gv("binder_include_flat_patterns") in (True, "true", "1", 1, "on")),
        stamp_quote=bool(gv("stamp_quote") in (True, "true", "1", 1, "on")),
        stamp_confidential=bool(gv("stamp_confidential") in (True, "true", "1", 1, "on")),
        stamp_approved=bool(gv("stamp_approved") in (True, "true", "1", 1, "on")),
        stamp_wip=bool(gv("stamp_wip") in (True, "true", "1", 1, "on")),
        stamp_inprogress=bool(gv("stamp_inprogress") in (True, "true", "1", 1, "on")),
        output_name=str(output_name).strip() if output_name is not None else None,
    )

    # Fabrication pack convenience
    fab = gv("fabrication_pack")
    if fab in (True, "true", "1", 1, "on"):
        setattr(opts, "fabrication_pack", True)

    if not opts.root_pn:
        current_app.logger.warning("/api/docpacks/build missing pn. payload=%s form=%s args=%s", payload, dict(data), dict(args))
        return jsonify({"error": "Missing parameter 'pn' (also accepted: part_number, partnumber, root_pn)"}), 400

    # ACL: enforce root access
    try:
        allowed = allowed_parts_for(current_user)
        if isinstance(allowed, set) and not part_is_allowed(allowed, opts.root_pn, opts.root_rev or ""):
            return jsonify({"error":"forbidden"}), 403
    except Exception:
        pass
    try:
        name, data, mime = build_docpack(opts)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400
    try:
        log_action(
            "docpack.build",
            resource_type="docpack",
            resource=f"{opts.root_pn}:{(opts.root_rev or '')}",
            meta={
                "depth": opts.depth,
                "types": ",".join(opts.file_types or []),
                "process_mode": opts.process_mode,
                "excel": bool(opts.want_excel_bom),
                "binder": bool(opts.want_pdf_binder),
                "visual": bool(opts.want_visual_list),
            },
        )
    except Exception:
        pass
    bio = BytesIO(data)
    return send_file(bio, mimetype=mime, as_attachment=True, download_name=name)

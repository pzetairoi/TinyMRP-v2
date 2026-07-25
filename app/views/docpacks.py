from __future__ import annotations
from flask import Blueprint, current_app, request, send_file, jsonify
from flask_login import login_required, current_user
from io import BytesIO
from typing import List
import re
import zipfile

from app.services.docpacks import DocPackOptions, build_docpack
from app.services.acl import permissions_required
from app.services.audit import log_action
from app.services.authorization import (
    authorised_get,
    has_permission,
    require_permission,
    scope_queryset,
)
from app.services.export_security import (
    ExportSecurityError,
    exact_bom_pairs,
    preflight_docpack,
    preflight_export_plan,
)

bp = Blueprint("docpacks_api", __name__, url_prefix="/api/docpacks")


@bp.get("/options")
@login_required
@require_permission("exports.run")
@require_permission("parts.read")
@require_permission("bom.read")
@require_permission("files.read")
def options():
    from app.models.part import Part
    from app.models.bom import BOMLink
    from app.models.artifact import PartFile
    from app.services.docpacks import _flatten_bom
    from app.services.markup_documents import markup_document_count_for_pairs
    from flask import current_app

    pn = (request.args.get("pn") or "").strip()
    rev = request.args.get("rev")
    depth = (request.args.get("depth") or "full").lower()
    if not pn:
        return jsonify({"error":"missing pn"}), 400

    try:
        scoped = scope_queryset(Part.objects, current_user, "parts").filter(
            part_number__iexact=pn
        )
        if rev is None:
            root_part = scoped.order_by("-updated_at").first()
        else:
            root_part = scoped.filter(revision__iexact=rev or "").first()
        if not root_part:
            return jsonify({"error": "not found"}), 404
        pn = root_part.part_number
        rev = root_part.revision or ""
        pairs = exact_bom_pairs(pn, rev, full=(depth != "top"))
        preflight_export_plan(
            current_user,
            pairs,
            require_bom=True,
            include_files=True,
            file_groups=None,
        )
    except ExportSecurityError:
        return jsonify({"error": "forbidden"}), 403
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
        "markup_document_count": (
            markup_document_count_for_pairs(
                [(p, r) for p, r, _qty in flat]
            )
            if has_permission(current_user, "markups.read")
            else 0
        ),
    })

def _parse_docpack_request():
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

    output_name = gv("output_name") if _has_key("output_name") else gv("filename") if _has_key("filename") else None
    if output_name is not None and not str(output_name).strip():
        output_name = None
    base_kwargs = dict(
        depth=(str(gv("depth") or "full")).lower(),
        include_consumed=bool(gv("include_consumed") in (True, "true", "1", 1, "on")),
        classified_filter=(str(gv("classified") or "show")).lower(),
        processes=[p for p in _list("processes") if p],
        process_mode=(str(gv("process_mode") or "all")).lower(),
        file_types=[t for t in _list("file_types") if t],
        want_excel_bom=bool(gv("excel_bom") in (True, "true", "1", 1, "on")),
        excel_all_fields=bool(gv("excel_all_fields") in (True, "true", "1", 1, "on")),
        excel_field_ids=[field_id for field_id in _list("excel_field_ids") if field_id],
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
        want_markup_files=bool(gv("markup_files") in (True, "true", "1", 1, "on")),
        want_markup_report=bool(gv("markup_report") in (True, "true", "1", 1, "on")),
        binder_add_cover=bool(gv("binder_add_cover") not in (False, None, "false", "0", 0)),
        binder_add_visual_list=bool(gv("binder_add_visual_list") not in (False, None, "false", "0", 0)),
        binder_add_whereused=bool(gv("binder_add_whereused") in (True, "true", "1", 1, "on")),
        binder_add_index=bool(gv("binder_add_index") not in (False, None, "false", "0", 0)),
        binder_add_datasheets=bool(gv("binder_add_datasheets") in (True, "true", "1", 1, "on")),
        binder_add_hardware_summary=bool(gv("binder_add_hardware_summary") not in (False, None, "false", "0", 0)),
        binder_page_numbers=bool(gv("binder_page_numbers") not in (False, None, "false", "0", 0)),
        binder_include_flat_patterns=bool(gv("binder_include_flat_patterns") in (True, "true", "1", 1, "on")),
        binder_add_markups=bool(gv("binder_add_markups") in (True, "true", "1", 1, "on")),
        stamp_quote=bool(gv("stamp_quote") in (True, "true", "1", 1, "on")),
        stamp_confidential=bool(gv("stamp_confidential") in (True, "true", "1", 1, "on")),
        stamp_approved=bool(gv("stamp_approved") in (True, "true", "1", 1, "on")),
        stamp_wip=bool(gv("stamp_wip") in (True, "true", "1", 1, "on")),
        stamp_inprogress=bool(gv("stamp_inprogress") in (True, "true", "1", 1, "on")),
        output_name=str(output_name).strip() if output_name is not None else None,
    )

    # Fabrication pack convenience
    fab = gv("fabrication_pack")
    fab_enabled = fab in (True, "true", "1", 1, "on")
    return payload, data, args, gv, _list, _has_key, base_kwargs, output_name, fab_enabled


@bp.post("/build")
@login_required
@require_permission("exports.run")
def build():
    parsed = _parse_docpack_request()
    if parsed and parsed[0] is None:
        _, resp, status = parsed
        return resp, status
    payload, data, args, gv, _list, _has_key, base_kwargs, output_name, fab_enabled = parsed

    # Robust PN/REV resolution (supports multiple legacy keys)
    _pn = gv("pn") or gv("part_number") or gv("partnumber") or gv("root_pn") or gv("root")
    _rev = gv("rev") if gv("rev") is not None else (gv("revision") if gv("revision") is not None else None)

    opts = DocPackOptions(
        root_pn=str(_pn or "").strip(),
        root_rev=_rev,
        **base_kwargs,
    )
    if fab_enabled:
        setattr(opts, "fabrication_pack", True)

    if not opts.root_pn:
        current_app.logger.warning("/api/docpacks/build missing pn. payload=%s form=%s args=%s", payload, dict(data), dict(args))
        return jsonify({"error": "Missing parameter 'pn' (also accepted: part_number, partnumber, root_pn)"}), 400

    try:
        from app.models.part import Part
        from app.services.authorization import scope_queryset

        scoped = scope_queryset(Part.objects, current_user, "parts").filter(
            part_number__iexact=opts.root_pn
        )
        if _rev is None:
            root_part = scoped.order_by("-updated_at").first()
        else:
            root_part = scoped.filter(
                revision__iexact=str(_rev or "").strip()
            ).first()
        if not root_part:
            return jsonify({"error": "not found"}), 404
        opts.root_pn = root_part.part_number
        opts.root_rev = root_part.revision or ""
        preflight_docpack(current_user, opts)
    except ExportSecurityError:
        return jsonify({"error": "forbidden"}), 403
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
                "included_categories": "parts,bom,files",
                "financial_content": False,
                "file_content": bool(
                    opts.want_selected_files or opts.want_pdf_binder
                ),
                "outcome": "success",
            },
        )
    except Exception:
        pass
    bio = BytesIO(data)
    return send_file(bio, mimetype=mime, as_attachment=True, download_name=name)


def _safe_slug(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (text or "").strip())
    cleaned = cleaned.strip("_")
    return cleaned or "docpack"


def _resolve_root_rev(pn: str, rev: str | None) -> str:
    if rev is not None:
        return str(rev).strip()
    from app.models.part import Part
    from app.services.attrs import harvest_part_attrs
    p = Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
    if not p:
        return ""
    attrs = harvest_part_attrs(p)
    return (attrs.get("revision") or p.revision or "").strip()


def _job_roots(job) -> List[tuple[str, str]]:
    roots: List[tuple[str, str]] = []
    seen = set()
    for line in (job.bom or []):
        pn = (line.pn or "").strip()
        if not pn:
            continue
        rev = _resolve_root_rev(pn, line.rev or "")
        key = (pn.lower(), rev.lower())
        if key in seen:
            continue
        seen.add(key)
        roots.append((pn, rev))
    if not roots and getattr(job, "part_number", None):
        pn = (job.part_number or "").strip()
        if pn:
            rev = _resolve_root_rev(pn, getattr(job, "part_revision", "") or "")
            roots.append((pn, rev))
    return roots


def _order_roots(order) -> List[tuple[str, str]]:
    roots: List[tuple[str, str]] = []
    seen = set()
    for line in (order.lines or []):
        pn = (line.pn or "").strip()
        if not pn:
            continue
        rev = _resolve_root_rev(pn, line.rev or "")
        key = (pn.lower(), rev.lower())
        if key in seen:
            continue
        seen.add(key)
        roots.append((pn, rev))
    return roots


def _multi_docpack_zip(
    roots: List[tuple[str, str]],
    base_kwargs: dict,
    fab_enabled: bool,
) -> tuple[bytes, List[str]]:
    errors: List[str] = []
    out = BytesIO()
    added = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for pn, rev in roots:
            try:
                opts = DocPackOptions(root_pn=pn, root_rev=rev, **{**base_kwargs, "output_name": None})
                if fab_enabled:
                    setattr(opts, "fabrication_pack", True)
                preflight_docpack(current_user, opts)
                name, data, mime = build_docpack(opts)
            except ExportSecurityError:
                raise
            except RuntimeError:
                errors.append(f"{pn}:{rev or ''} -> generation failed")
                continue
            slug = _safe_slug(f"{pn}_{rev}" if rev else pn)
            zf.writestr(f"{slug}/{name}", data)
            added += 1
        if errors:
            zf.writestr("docpack_manifest.txt", "\n".join(errors))
        if added == 0 and not errors:
            zf.writestr("docpack_manifest.txt", "No docpacks were generated.\n")
    return out.getvalue(), errors


@bp.post("/build_job", endpoint="build_job")
@login_required
@permissions_required("jobs.read")
@require_permission("exports.run")
def build_job_docpack():
    parsed = _parse_docpack_request()
    if parsed and parsed[0] is None:
        _, resp, status = parsed
        return resp, status
    _, _, _, gv, _, _, base_kwargs, output_name, fab_enabled = parsed

    job_id = (gv("job_id") or gv("job") or gv("job_number") or "").strip()
    if not job_id:
        return jsonify({"error": "Missing job_id"}), 400

    from app.models.job import Job
    job = authorised_get(
        Job.objects,
        current_user,
        job_id,
        resource_type="jobs",
    )
    if not job:
        job = authorised_get(
            Job.objects,
            current_user,
            job_id,
            resource_type="jobs",
            identifier_field="job_number",
        )
    if not job:
        return jsonify({"error": "Job not found"}), 404

    roots = _job_roots(job)
    if not roots:
        return jsonify({"error": "Job has no BOM lines to export"}), 400

    try:
        zip_bytes, errors = _multi_docpack_zip(
            roots,
            base_kwargs,
            fab_enabled,
        )
    except ExportSecurityError:
        return jsonify({"error": "forbidden"}), 403
    if not zip_bytes:
        return jsonify({"error": "Failed to build docpack"}), 400

    name = (output_name or f"{job.job_number}_docpack").strip()
    if not name.lower().endswith(".zip"):
        name = f"{name}.zip"
    log_action(
        "docpack.build.job",
        resource_type="job",
        resource=str(job.job_number or job.id),
        meta={
            "root_count": len(roots),
            "financial_content": False,
            "file_content": True,
            "outcome": "success",
        },
    )
    return send_file(BytesIO(zip_bytes), mimetype="application/zip", as_attachment=True, download_name=name)


@bp.post("/build_order", endpoint="build_order")
@login_required
@permissions_required("orders.read")
@require_permission("exports.run")
def build_order_docpack():
    parsed = _parse_docpack_request()
    if parsed and parsed[0] is None:
        _, resp, status = parsed
        return resp, status
    _, _, _, gv, _, _, base_kwargs, output_name, fab_enabled = parsed

    order_id = (gv("order_id") or gv("order") or gv("order_number") or "").strip()
    if not order_id:
        return jsonify({"error": "Missing order_id"}), 400

    from app.models.order import Order
    order = authorised_get(
        Order.objects,
        current_user,
        order_id,
        resource_type="orders",
    )
    if not order:
        order = authorised_get(
            Order.objects,
            current_user,
            order_id,
            resource_type="orders",
            identifier_field="order_number",
        )
    if not order:
        return jsonify({"error": "Order not found"}), 404

    roots = _order_roots(order)
    if not roots:
        return jsonify({"error": "Order has no lines to export"}), 400

    try:
        zip_bytes, errors = _multi_docpack_zip(
            roots,
            base_kwargs,
            fab_enabled,
        )
    except ExportSecurityError:
        return jsonify({"error": "forbidden"}), 403
    if not zip_bytes:
        return jsonify({"error": "Failed to build docpack"}), 400

    name = (output_name or f"{order.order_number}_docpack").strip()
    if not name.lower().endswith(".zip"):
        name = f"{name}.zip"
    log_action(
        "docpack.build.order",
        resource_type="order",
        resource=str(order.order_number or order.id),
        meta={
            "root_count": len(roots),
            "financial_content": False,
            "file_content": True,
            "outcome": "success",
        },
    )
    return send_file(BytesIO(zip_bytes), mimetype="application/zip", as_attachment=True, download_name=name)

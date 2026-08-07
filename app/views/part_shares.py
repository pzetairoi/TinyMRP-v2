from __future__ import annotations

import logging
import mimetypes
import os
from io import BytesIO

from flask import Blueprint, abort, current_app, jsonify, make_response, render_template, request, send_file
from flask_login import current_user, login_required

from app.extensions import csrf
from app.models.artifact import PartFile
from app.models.extra_file import PartExtraFile
from app.models.part import Part
from app.models.part_share import PartShareLink
from app.services.attrs import approval_field_values, harvest_part_attrs
from app.services.audit import log_action
from app.services.extra_files import extra_file_token_for, resolve_extra_file_token
from app.services.field_config import get_field_config
from app.services.files_access import file_token_for, resolve_file_token
from app.services.docpacks import DocPackOptions, build_docpack
from app.services.export_security import (
    ExportSecurityError,
    docpack_file_groups,
    exact_bom_pairs,
    preflight_export_plan,
)
from app.services.file_security import FileSecurityError
from app.services.part_shares import (
    PUBLIC_MANAGED_FILE_GROUPS,
    create_part_share,
    normalize_share_revision,
    public_associated_file_path,
    public_managed_file_path,
    public_part_share_url,
    public_response_headers,
    record_part_share_access,
    resolve_public_part_share_scope,
    share_dict,
)
from app.services.timezone_utils import format_display_ts, local_input_value, utc_iso, utc_now
from app.services.part_norm import clean_rev
from app.services.thumbs import _dedup_urls
from app.views.bom_tree import (
    _child_links,
    _coverage_groups as _bom_coverage_groups,
    _is_hardware_node,
    _link_occurrence_qtys,
    _node,
    _process_label,
)
from app.views.parts import (
    _context_field_values,
    _group_file_overview_rows,
    _normalized_revision,
)
from app.views.ui import vite_assets
from app.services.authorization import (
    authorised_part_pairs,
    has_any_permission,
    has_permission,
    uses_portal_presentation,
    scope_queryset,
)

logger = logging.getLogger(__name__)


bp = Blueprint("part_shares", __name__)

_PUBLIC_ATTRIBUTE_KEYS = frozenset(
    {
        "category",
        "description",
        "finish",
        "manufacturer",
        "mass",
        "material",
        "mfr_part",
        "oem",
        "oem_partnumber",
        "process",
        "processes",
        "revision",
        "status",
        "uom",
    }
)
_PUBLIC_FIELD_IDS = frozenset(
    {
        "thumbnail",
        "part_number",
        "revision",
        "description",
        "display_code",
        "category",
        "material",
        "finish",
        "mass",
        "process",
        "processes",
        "uom",
        "status",
        "oem",
        "oem_partnumber",
        "manufacturer",
        "mfr_part",
        "datasheet",
        "approved",
        "approved_by",
        "approved_date",
        "qty",
        "alt_group",
        "level",
        "level_qty",
        "total_qty",
        "has_pdf",
        "has_png",
        "has_dxf",
        "has_step",
        "has_edr",
        "has_3mf",
        "has_ply",
        "has_stl",
        "has_datasheet",
    }
)
_PUBLIC_DOCPACK_EXCEL_FIELDS = frozenset(
    {
        "thumbnail",
        "part_number",
        "revision",
        "description",
        "qty",
        "material",
        "finish",
        "process",
        "uom",
    }
)
_PUBLIC_CONFIG_FIELD_IDS = _PUBLIC_FIELD_IDS - {"approved_by"}


def _part_share_scope(share) -> tuple[str, str]:
    return (str(share.part_number or "").strip(), normalize_share_revision(share.revision))


def _share_allows_children(share) -> bool:
    return bool(getattr(share, "allow_children", False))


def _share_allows_docpacks(share) -> bool:
    return bool(getattr(share, "allow_docpacks", False))


def _share_allows_attributes(share) -> bool:
    return bool(getattr(share, "allow_attributes", False))


def _share_or_abort(share_id: str, token: str):
    scope, status = resolve_public_part_share_scope(share_id, token)
    if scope and status == "ok":
        scope.share._resolved_public_scope = scope
        return scope.share
    abort(404)


def _resolved_scope(share):
    scope = getattr(share, "_resolved_public_scope", None)
    if scope is None:
        raise RuntimeError("public share scope was not resolved")
    return scope


def _part_or_404(part_number: str, revision: str) -> Part:
    part = Part.objects(
        part_number__iexact=part_number,
        revision__iexact=normalize_share_revision(revision),
    ).first()
    if not part:
        abort(404)
    return part


def _public_json(payload, status: int = 200):
    resp = jsonify(payload)
    resp.status_code = status
    return public_response_headers(resp)


def _flag_enabled(value) -> bool:
    return value in (True, 1, "1", "true", "True", "on", "yes", "Yes")


def _share_allows_part_key(share, pn: str, rev: str | None) -> bool:
    return _resolved_scope(share).allows_part(pn, rev)


def _requested_shared_part_key(share) -> tuple[str, str]:
    root_pn, root_rev = _part_share_scope(share)
    pn = (request.args.get("pn") or "").strip() or root_pn
    rev_arg = request.args.get("rev")
    rev = normalize_share_revision(rev_arg if rev_arg is not None else root_rev)
    if not _share_allows_part_key(share, pn, rev):
        abort(404)
    return pn, rev


def _share_preview_urls_for(share, raw_token: str, pn: str, rev: str, *, is_dwg: bool) -> list[str]:
    rows = list(
        PartFile.objects(
            part_number__iexact=pn,
            revision__iexact=normalize_share_revision(rev),
            ext_group="png",
            is_dwg=is_dwg,
        )
        .only("id", "part_number", "revision", "thumb_rel_path", "rel_path", "path", "mtime_iso")
        .order_by("-mtime_iso", "rel_path")
    )
    if not rows:
        return []
    pf = rows[0]
    if not _allowed_file_for_share(share, pf):
        return []
    try:
        public_managed_file_path(_resolved_scope(share), pf)
    except FileSecurityError:
        return []
    urls: list[str] = []
    if not is_dwg and getattr(pf, "thumb_rel_path", None):
        try:
            public_managed_file_path(_resolved_scope(share), pf, kind="thumb")
            urls.append(
                _shared_part_file_url(share, raw_token, pf, kind="thumb")
            )
        except FileSecurityError:
            pass
    urls.append(_shared_part_file_url(share, raw_token, pf))
    return _dedup_urls(urls)


def _shared_part_file_url(share, raw_token: str, pf: PartFile, *, kind: str = "file") -> str:
    return f"/share/part/{share.id}/{raw_token}/files/{file_token_for(pf, kind=kind)}"


def _shared_extra_file_url(share, raw_token: str, ef: PartExtraFile, *, kind: str = "file") -> str:
    return f"/share/part/{share.id}/{raw_token}/extra/{extra_file_token_for(ef, kind=kind)}"


def _rewrite_share_thumbs(share, raw_token: str, payload: dict) -> dict:
    data = dict(payload or {})
    pn = str(data.get("part_number") or data.get("pn") or "").strip()
    rev = normalize_share_revision(data.get("revision") or data.get("rev") or "")
    if not pn:
        return data
    urls = _share_preview_urls_for(share, raw_token, pn, rev, is_dwg=False)
    if urls:
        data["thumb_urls"] = urls
        data["thumbnail"] = urls[0]
    else:
        data["thumb_urls"] = []
        data["thumbnail"] = ""
    return data


def _public_bom_node(share, raw_token: str, node: dict) -> dict:
    source = dict((node or {}).get("data") or {})
    rewritten = _rewrite_share_thumbs(share, raw_token, source)
    safe_keys = {
        "pn",
        "desc",
        "rev",
        "qty",
        "uom",
        "alt_group",
        "process",
        "thumb_urls",
        "thumbnail",
        "part_number",
        "revision",
        "description",
        "level",
        "level_qty",
        "total_qty",
    }
    if _share_allows_attributes(share):
        safe_keys.update({"category", "material", "finish", "mass", "status"})
    data = {key: value for key, value in rewritten.items() if key in safe_keys}
    pn = str(data.get("pn") or data.get("part_number") or "").strip()
    rev = normalize_share_revision(data.get("rev") or data.get("revision"))
    return {
        "key": f"{pn}::{rev}",
        "leaf": (
            True
            if not _share_allows_children(share)
            else bool((node or {}).get("leaf", True))
        ),
        "data": data,
    }


def _allowed_file_for_share(share, file_record) -> bool:
    scope = _resolved_scope(share)
    if isinstance(file_record, PartFile):
        return scope.allows_managed_file(file_record)
    return scope.allows_associated_file(file_record)


def _extra_file_overview_row_for_share(share, raw_token: str, ef: PartExtraFile) -> dict:
    filename = (ef.original_name or "").strip() or "file"
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "id": "",
        "db_id": "",
        "collection": "",
        "kind": "extra",
        "part_number": ef.part_number,
        "revision": normalize_share_revision(ef.revision),
        "display_revision": normalize_share_revision(ef.revision) or "(no revision)",
        "name": filename,
        "label": ef.label or "",
        "ext_group": "extra",
        "ext": extension,
        "mime": ef.mime or "",
        "rel_path": "",
        "size": ef.size,
        "source": "",
        "recorded_by": "",
        "recorded_at": utc_iso(ef.uploaded_at) or "",
        "recorded_at_display": format_display_ts(
            ef.uploaded_at,
            fmt="%Y-%m-%d %H:%M:%S %Z",
        )
        or "",
        "recorded_at_local": local_input_value(ef.uploaded_at) or "",
        "url": _shared_extra_file_url(share, raw_token, ef),
    }


def _public_part_file_row(share, raw_token: str, pf: PartFile) -> dict:
    name = os.path.basename(pf.rel_path or pf.path or "") or "file"
    recorded_at = pf.mtime_iso or pf.mtime or pf.discovered_at
    return {
        "id": "",
        "db_id": "",
        "collection": "",
        "kind": "scanned",
        "part_number": pf.part_number,
        "revision": normalize_share_revision(pf.revision),
        "display_revision": normalize_share_revision(pf.revision)
        or "(no revision)",
        "name": name,
        "label": "",
        "ext_group": str(pf.ext_group or "").strip().lower(),
        "ext": str(pf.ext or "").strip().lower(),
        "mime": pf.content_type or "",
        "rel_path": "",
        "size": pf.size,
        "source": "",
        "recorded_by": "",
        "recorded_at": utc_iso(recorded_at) or "",
        "recorded_at_display": format_display_ts(
            recorded_at,
            fmt="%Y-%m-%d %H:%M:%S %Z",
        )
        or "",
        "recorded_at_local": local_input_value(recorded_at) or "",
        "url": _shared_part_file_url(share, raw_token, pf),
    }


def _part_detail_payload_for_share(share, raw_token: str, part: Part) -> dict:
    attrs = harvest_part_attrs(part)
    public_attrs = (
        {
            key: value
            for key, value in attrs.items()
            if key in _PUBLIC_ATTRIBUTE_KEYS
        }
        if _share_allows_attributes(share)
        else {}
    )
    norm_rev = _normalized_revision(part, attrs)

    preview_urls = _share_preview_urls_for(share, raw_token, part.part_number, norm_rev, is_dwg=False)
    drawing_urls = _share_preview_urls_for(share, raw_token, part.part_number, norm_rev, is_dwg=True)

    files = {"pdf": [], "dxf": [], "step": [], "edr": [], "3mf": [], "ply": [], "stl": [], "datasheet": []}
    for pf in (
        PartFile.objects(part_number__iexact=part.part_number, revision__iexact=norm_rev)
        .only("ext_group", "rel_path", "path", "http_url", "id", "thumb_rel_path", "part_number", "revision")
        .order_by("ext_group", "rel_path")
    ):
        ext_group = str(getattr(pf, "ext_group", "") or "").strip().lower()
        if ext_group not in files:
            continue
        if not _allowed_file_for_share(share, pf):
            continue
        try:
            public_managed_file_path(
                _resolved_scope(share),
                pf,
                must_exist=False,
            )
        except FileSecurityError:
            continue
        name = os.path.basename(pf.rel_path or pf.path or "") or "file"
        files[ext_group].append(
            {
                "url": _shared_part_file_url(share, raw_token, pf),
                "rel": "",
                "name": name,
            }
        )
    datasheet_summary_url = files["datasheet"][0]["url"] if files["datasheet"] else ""
    _config, _attrs, summary_field_values = _context_field_values(
        part,
        "part_detail_summary",
        extra={"part_number": part.part_number, "revision": norm_rev, "datasheet": datasheet_summary_url},
    )
    approval_values = approval_field_values(attrs, part=part)
    summary_field_values.update(
        {
            "approved": bool(approval_values.get("approved")),
            "approved_by": "",
            "approved_date": approval_values.get("approved_date") or "",
        }
    )
    summary_field_values["datasheet"] = datasheet_summary_url
    summary_field_values["notes"] = ""
    summary_field_values["comments"] = ""
    summary_field_values = {
        key: value
        for key, value in summary_field_values.items()
        if key in _PUBLIC_FIELD_IDS or key in {"notes", "comments"}
    }

    return {
        "part": {
            "part_number": part.part_number,
            "approved": bool(approval_values.get("approved")),
            "description": summary_field_values.get("description", part.description or attrs.get("description", "")),
            "revision": norm_rev,
            "display_code": f"{part.part_number}-{norm_rev}" if norm_rev else part.part_number,
            "category": summary_field_values.get("category", attrs.get("category", "")),
            "material": summary_field_values.get("material", attrs.get("material", "")),
            "finish": summary_field_values.get("finish", attrs.get("finish", "")),
            "mass": summary_field_values.get("mass", attrs.get("mass", "")),
            "process": summary_field_values.get("process", _process_label(part, attrs)),
            "processes": list(part.processes or []),
            "notes": "",
            "field_values": summary_field_values,
            "attributes": public_attrs,
        },
        "images": preview_urls,
        "drawing_urls": drawing_urls,
        "files": files,
        "uploader_profile": None,
        "approver_profile": None,
        "comments": [],
        "whereused": [],
        "other_versions": [],
        "jobs_orders": [],
        "can_jobs_manage": False,
        "can_orders_manage": False,
        "can_parts_delete": False,
        "can_parts_edit": False,
        "can_parts_note": False,
        "public_share": {
            "share_id": str(share.id),
            "created_at": utc_iso(share.created_at),
            "created_at_display": format_display_ts(share.created_at, fmt="%Y-%m-%d %H:%M:%S %Z") or None,
            "created_at_local": local_input_value(share.created_at) or None,
            "expires_at": utc_iso(share.expires_at),
            "expires_at_display": format_display_ts(share.expires_at, fmt="%Y-%m-%d %H:%M:%S %Z") or None,
            "expires_at_local": local_input_value(share.expires_at) or None,
            "access_count": int(share.access_count or 0),
            "allow_children": _share_allows_children(share),
            "allow_docpacks": _share_allows_docpacks(share),
            "allow_attributes": _share_allows_attributes(share),
        },
    }


@bp.get("/share/part/<share_id>/<token>")
def public_part_share_ui(share_id: str, token: str):
    share = _share_or_abort(share_id, token)
    assets = vite_assets()
    if not assets["js"]:
        abort(404, "React build missing. Run `npm run build` in /frontend.")
    part_number, revision = _part_share_scope(share)
    _part_or_404(part_number, revision)
    resp = make_response(render_template(
        "ui/react_shell.html",
        title=f"Shared Part · {part_number}{(' · REV ' + revision) if revision else ''}",
        assets=assets,
        initial={
            "pn": part_number,
            "rev": revision,
            "share_id": str(share.id),
            "share_token": token,
            "public_share": True,
        },
        files_base="",
    ))
    return public_response_headers(resp)


@bp.get("/share/part/<share_id>/<token>/files/<file_token>")
def public_part_share_file(share_id: str, token: str, file_token: str):
    share = _share_or_abort(share_id, token)
    try:
        resolved = resolve_file_token(file_token)
    except Exception:
        resolved = None
    if not resolved:
        abort(404)
    pf, kind = resolved
    if not _allowed_file_for_share(share, pf):
        abort(404)
    try:
        path = public_managed_file_path(
            _resolved_scope(share),
            pf,
            kind=kind,
        )
    except FileSecurityError:
        abort(404)
    ct, _encoding = mimetypes.guess_type(str(path))
    record_part_share_access(share, kind="managed_file")
    resp = send_file(path, mimetype=ct or "application/octet-stream", conditional=True, max_age=0)
    return public_response_headers(resp)


@bp.get("/share/part/<share_id>/<token>/extra/<extra_token>")
def public_part_share_extra_file(share_id: str, token: str, extra_token: str):
    share = _share_or_abort(share_id, token)
    try:
        resolved = resolve_extra_file_token(extra_token)
    except Exception:
        resolved = None
    if not resolved:
        abort(404)
    ef, _kind = resolved
    if not _allowed_file_for_share(share, ef):
        abort(404)
    try:
        abs_path = public_associated_file_path(_resolved_scope(share), ef)
    except FileSecurityError:
        abort(404)
    ct = ef.mime or mimetypes.guess_type(str(abs_path))[0] or "application/octet-stream"
    record_part_share_access(share, kind="associated_file")
    resp = send_file(abs_path, mimetype=ct, conditional=True, max_age=0)
    return public_response_headers(resp)


@bp.get("/api/share/part/<share_id>/<token>/field-config")
def public_share_field_config(share_id: str, token: str):
    _share_or_abort(share_id, token)
    config = get_field_config()
    fields = [
        field
        for field in config.get("fields", [])
        if field.get("id") in _PUBLIC_CONFIG_FIELD_IDS
    ]
    contexts = {}
    for name in ("part_detail_summary", "bom_tree"):
        source = dict(config.get("contexts", {}).get(name, {}))
        source["allowed_field_ids"] = [
            field_id
            for field_id in source.get("allowed_field_ids", [])
            if field_id in _PUBLIC_CONFIG_FIELD_IDS
        ]
        source["default_field_ids"] = [
            field_id
            for field_id in source.get("default_field_ids", [])
            if field_id in _PUBLIC_CONFIG_FIELD_IDS
        ]
        source["required_field_ids"] = [
            field_id
            for field_id in source.get("required_field_ids", [])
            if field_id in _PUBLIC_CONFIG_FIELD_IDS
        ]
        source["available_fields"] = [
            field
            for field in source.get("available_fields", [])
            if field.get("id") in _PUBLIC_CONFIG_FIELD_IDS
        ]
        contexts[name] = source
    resp = jsonify(
        {
            "ok": True,
            "config": {
                "fields": fields,
                "contexts": contexts,
                "canonical_aliases": [],
                "approval_rules": {},
            },
            "user_preferences": {"contexts": {}},
            "permissions": {"can_admin": False},
        }
    )
    return public_response_headers(resp)


@bp.get("/api/share/part/<share_id>/<token>/process-meta")
def public_share_process_meta(share_id: str, token: str):
    _share_or_abort(share_id, token)
    meta = dict(current_app.config.get("PROCESS_META") or {})
    meta.pop("_alias_index", None)
    return _public_json(meta)


@bp.get("/api/share/part/<share_id>/<token>/part_detail")
def public_share_part_detail(share_id: str, token: str):
    share = _share_or_abort(share_id, token)
    part_number, revision = _requested_shared_part_key(share)
    part = _part_or_404(part_number, revision)
    record_part_share_access(share, kind="detail")
    resp = jsonify(_part_detail_payload_for_share(share, token, part))
    return public_response_headers(resp)


@bp.get("/api/share/part/<share_id>/<token>/files_overview")
def public_share_files_overview(share_id: str, token: str):
    share = _share_or_abort(share_id, token)
    part_number, revision = _requested_shared_part_key(share)
    part = _part_or_404(part_number, revision)
    attrs = harvest_part_attrs(part)
    current_rev = _normalized_revision(part, attrs)
    rows: list[dict] = []

    for pf in (
        PartFile.objects(
            part_number__iexact=part.part_number,
            revision__iexact=current_rev,
        )
        .only(
            "part_number",
            "revision",
            "ext_group",
            "ext",
            "rel_path",
            "path",
            "http_url",
            "size",
            "mtime_iso",
            "mtime",
            "discovered_at",
            "content_type",
            "source",
            "thumb_rel_path",
        )
        .order_by("revision", "ext_group", "rel_path")
    ):
        if _allowed_file_for_share(share, pf):
            try:
                public_managed_file_path(
                    _resolved_scope(share),
                    pf,
                    must_exist=False,
                )
                rows.append(_public_part_file_row(share, token, pf))
            except FileSecurityError:
                continue

    for ef in (
        PartExtraFile.objects(
            part_number__iexact=part.part_number,
            revision__iexact=current_rev,
        )
        .only(
            "part_number",
            "revision",
            "original_name",
            "rel_path",
            "size",
            "mime",
            "label",
            "uploaded_by",
            "uploaded_at",
            "source",
        )
        .order_by("revision", "-uploaded_at", "original_name")
    ):
        if _allowed_file_for_share(share, ef):
            try:
                public_associated_file_path(_resolved_scope(share), ef)
                rows.append(
                    _extra_file_overview_row_for_share(share, token, ef)
                )
            except FileSecurityError:
                continue

    grouped = _group_file_overview_rows(rows, current_rev)
    resp = jsonify(
        {
            "part_number": part.part_number,
            "current_revision": grouped["current_revision"],
            "other_revisions": grouped["other_revisions"],
        }
    )
    return public_response_headers(resp)


@bp.get("/api/share/part/<share_id>/<token>/part_images")
def public_share_part_images(share_id: str, token: str):
    share = _share_or_abort(share_id, token)
    pn = (request.args.get("pn") or "").strip()
    mode = (request.args.get("mode") or "preview").strip().lower()
    rev = normalize_share_revision(request.args.get("rev"))
    if not pn or not _share_allows_part_key(share, pn, rev):
        resp = jsonify([])
        return public_response_headers(resp)

    is_dwg = mode == "drawing"
    rows = list(
        PartFile.objects(
            part_number__iexact=pn,
            revision__iexact=rev,
            ext_group="png",
            is_dwg=is_dwg,
        )
        .only("id", "part_number", "revision", "thumb_rel_path", "rel_path", "path", "mtime_iso")
        .order_by("-mtime_iso")
    )

    payload = []
    for pf in rows:
        if not _allowed_file_for_share(share, pf):
            continue
        try:
            public_managed_file_path(_resolved_scope(share), pf)
        except FileSecurityError:
            continue
        urls: list[str] = []
        if not is_dwg and getattr(pf, "thumb_rel_path", None):
            try:
                public_managed_file_path(
                    _resolved_scope(share),
                    pf,
                    kind="thumb",
                )
                urls.append(
                    _shared_part_file_url(share, token, pf, kind="thumb")
                )
            except FileSecurityError:
                pass
        urls.append(_shared_part_file_url(share, token, pf))
        payload.append({"urls": _dedup_urls(urls), "revision": pf.revision})
    resp = jsonify(payload)
    return public_response_headers(resp)


@bp.get("/api/share/part/<share_id>/<token>/bom_tree")
def public_share_bom_tree(share_id: str, token: str):
    share = _share_or_abort(share_id, token)
    config = get_field_config()
    pn = (request.args.get("pn") or "").strip()
    rev = normalize_share_revision(request.args.get("rev"))
    parent = (request.args.get("parent") or "").strip()
    parent_rev = normalize_share_revision(request.args.get("parent_rev"))

    if pn:
        if not _share_allows_part_key(share, pn, rev):
            resp = jsonify([])
            return public_response_headers(resp)
        root_part = _part_or_404(pn, rev)
        root = _node(root_part.part_number, rev=rev, config=config)
        root["children"] = []
        root = _public_bom_node(share, token, root)
        root["children"] = []
        resp = jsonify([root])
        return public_response_headers(resp)

    if parent:
        if not _share_allows_children(share) or not _share_allows_part_key(
            share,
            parent,
            parent_rev,
        ):
            resp = jsonify([])
            return public_response_headers(resp)
        kids = []
        for link in _child_links(parent, parent_rev):
            child_pn = getattr(link, "child_pn", None)
            if not child_pn or child_pn == parent:
                continue
            child_rev = clean_rev(getattr(link, "child_rev", None)) if hasattr(link, "child_rev") else None
            if not _share_allows_part_key(share, child_pn, child_rev):
                continue
            node = _node(child_pn, link, rev=child_rev, config=config)
            kids.append(_public_bom_node(share, token, node))
        kids.sort(key=lambda item: 1 if _is_hardware_node(item) else 0)
        resp = jsonify(kids)
        return public_response_headers(resp)

    resp = jsonify([])
    return public_response_headers(resp)


@bp.get("/api/share/part/<share_id>/<token>/bom_flat")
def public_share_bom_flat(share_id: str, token: str):
    share = _share_or_abort(share_id, token)
    config = get_field_config()
    root_pn, root_rev = _requested_shared_part_key(share)
    root_part = _part_or_404(root_pn, root_rev)
    if not _share_allows_children(share):
        return public_response_headers(jsonify([]))

    rows_by_key: dict[tuple[str, str], dict] = {}
    part_cache: dict[tuple[str, str], tuple[Part | None, dict, str, list[str], set[str], dict]] = {}

    def row_for(child_pn: str, child_rev: str) -> dict:
        key = (child_pn, clean_rev(child_rev))
        existing = rows_by_key.get(key)
        if existing:
            return existing

        cached = part_cache.get(key)
        if cached is None:
            part_doc = Part.objects(part_number=child_pn, revision=key[1]).first()
            attrs = harvest_part_attrs(part_doc) if part_doc else {}
            effective_rev = clean_rev(attrs.get("revision") or (part_doc.revision if part_doc else "") or key[1])
            proc_label = _process_label(part_doc, attrs)
            thumbs = _share_preview_urls_for(share, token, child_pn, effective_rev, is_dwg=False)
            coverage = _bom_coverage_groups(child_pn, effective_rev)
            from app.services.field_config import context_field_ids, resolve_part_field_values

            values = resolve_part_field_values(
                part_doc,
                context_field_ids("bom_tree", config),
                attrs=attrs,
                config=config,
                extra={
                    "part_number": child_pn,
                    "revision": effective_rev,
                    "description": attrs.get("description", ""),
                    "qty": 0.0,
                    "uom": "",
                    "alt_group": "",
                    "thumbnail": thumbs[0] if thumbs else "",
                },
                coverage=coverage,
            )
            cached = (part_doc, attrs, proc_label, thumbs, coverage, values)
            part_cache[key] = cached

        _part_doc, attrs, proc_label, thumbs, _coverage, values = cached
        row = {
            "row_key": f"{child_pn}::{key[1]}",
            "part_number": child_pn,
            "revision": key[1],
            "description": attrs.get("description", ""),
            "qty": 0.0,
            "uom": "",
            "alt_group": "",
            "process": proc_label,
            "thumb_urls": thumbs,
            "attrs": (
                {
                    key: value
                    for key, value in attrs.items()
                    if key in _PUBLIC_ATTRIBUTE_KEYS
                }
                if _share_allows_attributes(share)
                else {}
            ),
            **{
                key: value
                for key, value in values.items()
                if key in _PUBLIC_FIELD_IDS
            },
        }
        if thumbs:
            row["thumbnail"] = thumbs[0]
        rows_by_key[key] = row
        return row

    root_key = (root_part.part_number, root_rev)
    stack: list[tuple[str, str, float, str, str, tuple[tuple[str, str], ...]]] = []
    for link in _child_links(root_part.part_number, root_rev):
        child_pn = getattr(link, "child_pn", None)
        if not child_pn:
            continue
        child_rev = clean_rev(getattr(link, "child_rev", "") or "")
        child_key = (child_pn, child_rev)
        if child_key == root_key:
            continue
        for occ_qty in _link_occurrence_qtys(link):
            stack.append(
                (
                    child_pn,
                    child_rev,
                    float(occ_qty or 0.0),
                    getattr(link, "uom", None) or "",
                    getattr(link, "alt_group", None) or "",
                    (root_key, child_key),
                )
            )

    while stack:
        child_pn, child_rev, qty, uom, alt_group, lineage = stack.pop()
        row = row_for(child_pn, child_rev)
        row["qty"] = float(row.get("qty") or 0.0) + float(qty or 0.0)
        row["total_qty"] = row["qty"]

        uom_set = row.setdefault("_uom_set", set())
        if uom:
            uom_set.add(str(uom))
        row["uom"] = ", ".join(sorted(uom_set)) if uom_set else ""

        alt_set = row.setdefault("_alt_group_set", set())
        if alt_group:
            alt_set.add(str(alt_group))
        row["alt_group"] = ", ".join(sorted(alt_set)) if alt_set else ""

        for link in _child_links(child_pn, child_rev):
            next_pn = getattr(link, "child_pn", None)
            if not next_pn:
                continue
            next_rev = clean_rev(getattr(link, "child_rev", "") or "")
            next_key = (next_pn, next_rev)
            if next_key in lineage:
                continue
            for occ_qty in _link_occurrence_qtys(link):
                stack.append(
                    (
                        next_pn,
                        next_rev,
                        float(qty or 0.0) * float(occ_qty or 0.0),
                        getattr(link, "uom", None) or "",
                        getattr(link, "alt_group", None) or "",
                        lineage + (next_key,),
                    )
                )

    rows = []
    for row in rows_by_key.values():
        row.pop("_uom_set", None)
        row.pop("_alt_group_set", None)
        rows.append(row)
    rows.sort(key=lambda item: (str(item.get("part_number") or ""), str(item.get("revision") or "")))
    resp = jsonify(rows)
    return public_response_headers(resp)


def _public_docpack_pairs(share, part_number: str, revision: str, depth: str):
    if not _share_allows_children(share):
        return {(part_number, normalize_share_revision(revision))}
    pairs = set(
        exact_bom_pairs(
            part_number,
            revision,
            full=depth != "top",
        )
    )
    if any(not _share_allows_part_key(share, pn, rev) for pn, rev in pairs):
        raise ValueError("share unavailable")
    return pairs


def _share_docpack_options_payload(
    share,
    part_number: str,
    revision: str,
    depth: str,
) -> dict:
    pairs = _public_docpack_pairs(share, part_number, revision, depth)

    groups = set()
    for pnr, rev in pairs:
        q = PartFile.objects(
            part_number__iexact=pnr,
            revision__iexact=rev,
        )
        for pf in q.only("part_number", "revision", "ext_group"):
            if (
                pf.ext_group
                and str(pf.ext_group).lower() in PUBLIC_MANAGED_FILE_GROUPS
                and _allowed_file_for_share(share, pf)
            ):
                groups.add(str(pf.ext_group).lower())

    meta = current_app.config.get("PROCESS_META", {}) or {}
    processes = [key for key in meta.keys() if not str(key).startswith("_")]
    return {
        "file_types": sorted(groups),
        "processes": sorted(processes),
    }


@bp.get("/api/share/part/<share_id>/<token>/docpacks/options")
def public_share_docpack_options(share_id: str, token: str):
    share = _share_or_abort(share_id, token)
    if not _share_allows_docpacks(share):
        return _public_json({"error": "forbidden"}, 403)
    part_number, revision = _requested_shared_part_key(share)
    depth = (request.args.get("depth") or "full").strip().lower()
    try:
        log_action(
            "part.share.docpack.options",
            resource_type="part_share",
            resource=f"{share.part_number}:{share.revision or ''}",
            meta={
                "share_id": str(share.id),
                "pn": part_number,
                "rev": revision,
                "depth": depth,
            },
        )
    except Exception:
        logger.exception("audit log failed for public share docpack options")
    try:
        payload = _share_docpack_options_payload(
            share,
            part_number,
            revision,
            depth,
        )
    except Exception:
        abort(404)
    return _public_json(payload)


@bp.post("/api/share/part/<share_id>/<token>/docpacks/build")
@csrf.exempt
def public_share_docpack_build(share_id: str, token: str):
    share = _share_or_abort(share_id, token)
    if not _share_allows_docpacks(share):
        return _public_json({"error": "forbidden"}, 403)

    from app.views.docpacks import _parse_docpack_request

    payload, data, args, gv, _list, _has_key, base_kwargs, _output_name, fab_enabled = _parse_docpack_request()
    fallback_pn, fallback_rev = _part_share_scope(share)
    requested_pn = gv("pn") or gv("part_number") or gv("partnumber") or gv("root_pn") or gv("root") or fallback_pn
    requested_rev = gv("rev") if gv("rev") is not None else (gv("revision") if gv("revision") is not None else fallback_rev)
    part_number = str(requested_pn or "").strip()
    revision = normalize_share_revision(requested_rev)
    if not _share_allows_part_key(share, part_number, revision):
        abort(404)

    opts = DocPackOptions(
        root_pn=part_number,
        root_rev=revision,
        **base_kwargs,
    )
    # Internal review markups are never exposed through public share docpacks.
    opts.want_markup_files = False
    opts.want_markup_report = False
    opts.binder_add_markups = False
    if fab_enabled:
        setattr(opts, "fabrication_pack", True)
    requested_groups = {
        str(group or "").strip().lower()
        for group in (opts.file_types or [])
        if str(group or "").strip()
    }
    if not requested_groups.issubset(PUBLIC_MANAGED_FILE_GROUPS):
        return _public_json({"error": "invalid_options"}, 400)
    if (
        opts.depth not in {"top", "full"}
        or opts.classified_filter != "show"
        or opts.process_mode not in {"all", "selected"}
        or bool(opts.want_whereused_report)
        or bool(opts.binder_add_whereused)
        or bool(opts.excel_all_fields)
    ):
        return _public_json({"error": "invalid_options"}, 400)
    process_names = {
        str(name).strip()
        for name in (current_app.config.get("PROCESS_META", {}) or {})
        if not str(name).startswith("_")
    }
    if any(process not in process_names for process in (opts.processes or [])):
        return _public_json({"error": "invalid_options"}, 400)
    if not _share_allows_attributes(share) and (
        bool(opts.want_excel_bom) or bool(fab_enabled)
    ):
        return _public_json({"error": "invalid_options"}, 400)
    if opts.want_excel_bom or fab_enabled:
        requested_fields = set(opts.excel_field_ids or [])
        if not requested_fields.issubset(_PUBLIC_DOCPACK_EXCEL_FIELDS):
            return _public_json({"error": "invalid_options"}, 400)
        opts.excel_field_ids = sorted(
            requested_fields or _PUBLIC_DOCPACK_EXCEL_FIELDS
        )
    try:
        planned_pairs = _public_docpack_pairs(
            share,
            part_number,
            revision,
            opts.depth,
        )
        groups_to_check = docpack_file_groups(opts)
        if groups_to_check is None:
            groups_to_check = set(PUBLIC_MANAGED_FILE_GROUPS)
        for planned_pn, planned_rev in planned_pairs:
            for pf in PartFile.objects(
                part_number__iexact=planned_pn,
                revision__iexact=planned_rev,
                ext_group__in=sorted(groups_to_check),
            ):
                public_managed_file_path(
                    _resolved_scope(share),
                    pf,
                    must_exist=False,
                )
    except (FileSecurityError, ValueError):
        abort(404)
    if not _share_allows_children(share):
        opts.flat_override = []

    try:
        name, blob, mime = build_docpack(opts)
    except RuntimeError:
        return _public_json({"error": "Unable to generate document pack"}, 400)

    record_part_share_access(share, kind="docpack_build")
    try:
        log_action(
            "part.share.docpack.build",
            resource_type="part_share",
            resource=f"{share.part_number}:{share.revision or ''}",
            meta={
                "share_id": str(share.id),
                "pn": opts.root_pn,
                "rev": opts.root_rev or "",
                "depth": opts.depth,
                "types": ",".join(opts.file_types or []),
                "process_mode": opts.process_mode,
                "excel": bool(opts.want_excel_bom),
                "binder": bool(opts.want_pdf_binder),
                "visual": bool(opts.want_visual_list),
            },
        )
    except Exception:
        logger.exception("audit log failed for public share docpack build")

    resp = send_file(BytesIO(blob), mimetype=mime, as_attachment=True, download_name=name)
    return public_response_headers(resp)


@bp.get("/api/parts/<path:pn>/shares")
@login_required
def list_part_shares(pn: str):
    if (
        uses_portal_presentation(
            current_user, "parts.read", resource_type="parts"
        )
        or not has_any_permission(
            current_user,
            ("shares.create", "shares.revoke"),
        )
    ):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    # A blank rev means "whichever revision this part actually has", not
    # "the revision literally equal to empty string". The detail page fetches
    # shares before its revision state has resolved, so it sends rev= empty and
    # every part with a real revision 404'd - which surfaced as a page that
    # only worked after F5.
    scoped = scope_queryset(Part.objects, current_user, "parts")
    requested_rev = request.args.get("rev")
    rev = normalize_share_revision(requested_rev)
    if rev:
        part = scoped.filter(part_number__iexact=pn, revision__iexact=rev).first()
    else:
        part = (
            scoped.filter(part_number__iexact=pn, revision__iexact="").first()
            or scoped.filter(part_number__iexact=pn).order_by("-updated_at").first()
        )
    if not part:
        return jsonify({"ok": False, "error": "not_found"}), 404
    rows = [
        share_dict(item)
        for item in PartShareLink.objects(
            part_number=part.part_number,
            revision=normalize_share_revision(part.revision),
        ).order_by("-created_at")
    ]
    return jsonify({"ok": True, "shares": rows})


@bp.post("/api/parts/<path:pn>/shares")
@login_required
@csrf.exempt
def create_part_share_api(pn: str):
    if (
        uses_portal_presentation(
            current_user, "parts.read", resource_type="parts"
        )
        or not has_permission(current_user, "shares.create")
        or not has_permission(current_user, "files.read")
    ):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    payload = request.get_json(force=True, silent=True) or {}
    rev = normalize_share_revision(payload.get("rev") if "rev" in payload else request.args.get("rev"))
    try:
        part = (
            scope_queryset(Part.objects, current_user, "parts")
            .filter(part_number__iexact=pn, revision__iexact=rev)
            .first()
        )
    except Exception:
        part = None
    if not part:
        return jsonify({"ok": False, "error": "not_found"}), 404
    try:
        expires_in_days = int(payload.get("expires_in_days") or 30)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_expiry"}), 400
    if expires_in_days < 1 or expires_in_days > 365:
        return jsonify({"ok": False, "error": "invalid_expiry"}), 400
    allow_children = _flag_enabled(payload.get("allow_children"))
    allow_docpacks = _flag_enabled(payload.get("allow_docpacks"))
    allow_attributes = _flag_enabled(payload.get("allow_attributes"))
    try:
        shared_pairs = (
            exact_bom_pairs(
                part.part_number,
                part.revision,
                full=True,
            )
            if allow_children
            else {(part.part_number, normalize_share_revision(part.revision))}
        )
        required_pairs = frozenset(
            (pair_pn.casefold(), pair_rev.casefold())
            for pair_pn, pair_rev in shared_pairs
        )
        if allow_children:
            if not has_permission(current_user, "bom.read"):
                raise ExportSecurityError("share unavailable")
            if authorised_part_pairs(current_user, shared_pairs) != required_pairs:
                raise ExportSecurityError("share unavailable")
        if allow_docpacks:
            preflight_export_plan(
                current_user,
                shared_pairs,
                require_bom=True,
                include_files=True,
                file_groups=None,
            )
    except Exception:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    share, raw_token = create_part_share(
        part.part_number,
        part.revision or "",
        created_by=current_user,
        expires_in_days=expires_in_days,
        allow_children=allow_children,
        allow_docpacks=allow_docpacks,
        allow_attributes=allow_attributes,
        allow_unreleased=has_permission(
            current_user,
            "parts.read_unreleased",
        ),
    )
    try:
        log_action(
            "part.share.create",
            resource_type="part_share",
            resource=f"{part.part_number}:{normalize_share_revision(part.revision)}",
            meta={
                "share_id": str(share.id),
                "expires_in_days": expires_in_days,
                "allow_children": allow_children,
                "allow_docpacks": allow_docpacks,
                "allow_attributes": allow_attributes,
                "allow_unreleased": has_permission(
                    current_user,
                    "parts.read_unreleased",
                ),
            },
        )
    except Exception:
        # Losing the record that a PUBLIC share was created is the
        # security-relevant one: the share works, but nothing says who made it.
        logger.exception("audit log failed for part share creation")
    return jsonify(
        {
            "ok": True,
            "share": share_dict(share),
            "share_id": str(share.id),
            "share_token": raw_token,
            "url": public_part_share_url(share, raw_token),
        }
    )


@bp.delete("/api/parts/<path:pn>/shares/<share_id>")
@login_required
@csrf.exempt
def revoke_part_share_api(pn: str, share_id: str):
    if (
        uses_portal_presentation(
            current_user, "parts.read", resource_type="parts"
        )
        or not has_permission(current_user, "shares.revoke")
    ):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    try:
        share = PartShareLink.objects(id=share_id).first()
    except Exception:
        share = None
    if not share:
        return jsonify({"ok": False, "error": "not_found"}), 404
    if str(share.part_number or "").strip().lower() != str(pn or "").strip().lower():
        return jsonify({"ok": False, "error": "not_found"}), 404
    try:
        root = (
            scope_queryset(Part.objects, current_user, "parts")
            .filter(
                part_number__iexact=share.part_number,
                revision__iexact=normalize_share_revision(share.revision),
            )
            .first()
        )
    except Exception:
        root = None
    if not root:
        return jsonify({"ok": False, "error": "not_found"}), 404
    now = utc_now()
    share.update(
        set__revoked_at=now,
        set__revoked_by_user_id=str(getattr(current_user, "id", "") or ""),
        set__revoked_by_email=str(getattr(current_user, "email", "") or ""),
    )
    try:
        log_action(
            "part.share.revoke",
            resource_type="part_share",
            resource=f"{share.part_number}:{share.revision or ''}",
            meta={"share_id": str(share.id)},
        )
    except Exception:
        logger.exception("audit log failed for part share revocation")
    return jsonify({"ok": True})

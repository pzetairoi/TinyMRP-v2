from __future__ import annotations

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
from app.services.attrs import approval_field_values, approved_value, harvest_part_attrs
from app.services.part_annotations import filtered_part_attrs
from app.services.audit import log_action
from app.services.extra_files import extra_abs_path, extra_file_token_for, extra_root, resolve_extra_file_token
from app.services.field_config import get_field_config
from app.services.files_access import file_token_for, resolve_file_token
from app.services.docpacks import DocPackOptions, _flatten_bom, build_docpack
from app.services.part_shares import (
    create_part_share,
    normalize_share_revision,
    public_part_share_url,
    public_response_headers,
    record_part_share_access,
    resolve_part_share,
    share_dict,
)
from app.services.timezone_utils import format_display_ts, local_input_value, utc_iso, utc_now
from app.services.thumbs import _dedup_urls
from app.views.bom_tree import (
    _child_links,
    _clean_rev as _bom_clean_rev,
    _coverage_groups as _bom_coverage_groups,
    _has_children,
    _is_hardware_node,
    _link_occurrence_qtys,
    _node,
    _process_label,
)
from app.views.parts import (
    _attr_identity,
    _context_field_values,
    _extra_file_overview_row,
    _find_part_doc,
    _group_file_overview_rows,
    _normalized_revision,
    _part_file_overview_row,
)
from app.views.ui import vite_assets
from app.services.user_profile import resolve_identity_profile, resolve_identity_profiles
from app.services.acl import user_has_permission


bp = Blueprint("part_shares", __name__)


def _role_names(user) -> set[str]:
    names = set()
    for role in (getattr(user, "roles", []) or []):
        if getattr(role, "name", None):
            names.add(str(role.name))
    return names


def _is_admin(user) -> bool:
    if not user:
        return False
    if "admin" in _role_names(user):
        return True
    return user_has_permission(user, "admin")


def _part_share_scope(share) -> tuple[str, str]:
    return (str(share.part_number or "").strip(), normalize_share_revision(share.revision))


def _share_allows_children(share) -> bool:
    return bool(getattr(share, "allow_children", False))


def _share_allows_docpacks(share) -> bool:
    return bool(getattr(share, "allow_docpacks", False))


def _share_allows_attributes(share) -> bool:
    return bool(getattr(share, "allow_attributes", False))


def _share_or_abort(share_id: str, token: str):
    share, status = resolve_part_share(share_id, token)
    if share and status == "ok":
        return share
    if status in {"expired", "revoked"}:
        abort(410)
    abort(404)


def _part_or_404(part_number: str, revision: str) -> Part:
    part = _find_part_doc(part_number, revision)
    if not part:
        abort(404)
    return part


def _public_json(payload, status: int = 200):
    resp = jsonify(payload)
    resp.status_code = status
    return public_response_headers(resp)


def _flag_enabled(value) -> bool:
    return value in (True, 1, "1", "true", "True", "on", "yes", "Yes")


def _same_shared_part_number(share, pn: str) -> bool:
    share_pn, _share_rev = _part_share_scope(share)
    return str(pn or "").strip().lower() == share_pn.lower()


def _share_allows_part_key(share, pn: str, rev: str | None) -> bool:
    key = (str(pn or "").strip(), normalize_share_revision(rev))
    if not key[0]:
        return False
    if key == _part_share_scope(share):
        return True
    return _share_allows_children(share) and key in _share_descendant_keys(share)


def _allowed_part_number_for_share(share, pn: str) -> bool:
    share_pn, _share_rev = _part_share_scope(share)
    target = str(pn or "").strip().lower()
    if not target:
        return False
    if target == share_pn.lower():
        return True
    if not _share_allows_children(share):
        return False
    return any(str(child_pn or "").strip().lower() == target for child_pn, _child_rev in _share_descendant_keys(share))


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
    urls: list[str] = []
    if not is_dwg and getattr(pf, "thumb_rel_path", None):
        urls.append(_shared_part_file_url(share, raw_token, pf, kind="thumb"))
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


def _share_descendant_keys(share) -> set[tuple[str, str]]:
    root = _part_share_scope(share)
    seen = {root}
    queue = [root]
    while queue:
        parent_pn, parent_rev = queue.pop(0)
        for link in _child_links(parent_pn, parent_rev):
            child_pn = getattr(link, "child_pn", None)
            if not child_pn:
                continue
            child_rev = _bom_clean_rev(getattr(link, "child_rev", "") or "")
            key = (child_pn, child_rev)
            if key in seen:
                continue
            seen.add(key)
            queue.append(key)
    return seen


def _allowed_file_for_share(share, part_number: str) -> bool:
    return _allowed_part_number_for_share(share, part_number)


def _allowed_path(abs_path: str, base_root: str) -> bool:
    try:
        ap = os.path.abspath(abs_path)
        base = os.path.abspath(base_root)
        ap_norm, base_norm = os.path.normcase(ap), os.path.normcase(base)
        try:
            return os.path.commonpath([ap_norm, base_norm]) == base_norm
        except Exception:
            return ap_norm.startswith(base_norm)
    except Exception:
        return False


def _part_file_overview_row_for_share(share, raw_token: str, pf: PartFile) -> dict:
    row = _part_file_overview_row(pf)
    row["url"] = _shared_part_file_url(share, raw_token, pf)
    return row


def _extra_file_overview_row_for_share(share, raw_token: str, ef: PartExtraFile) -> dict:
    row = _extra_file_overview_row(ef)
    row["url"] = _shared_extra_file_url(share, raw_token, ef)
    return row


def _part_detail_payload_for_share(share, raw_token: str, part: Part) -> dict:
    attrs = harvest_part_attrs(part)
    public_attrs = filtered_part_attrs(part, attrs)
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
        name = os.path.basename(pf.rel_path or pf.path or "") or "file"
        files[ext_group].append({"url": _shared_part_file_url(share, raw_token, pf), "rel": pf.rel_path or "", "name": name})
    datasheet_summary_url = files["datasheet"][0]["url"] if files["datasheet"] else ""
    _config, _attrs, summary_field_values = _context_field_values(
        part,
        "part_detail_summary",
        extra={"part_number": part.part_number, "revision": norm_rev, "datasheet": datasheet_summary_url},
    )
    summary_field_values.update(approval_field_values(attrs))
    summary_field_values["notes"] = ""
    summary_field_values["comments"] = ""

    uploader_identity = _attr_identity(attrs, "uploader", "uploaded_by", "uploadedby", "author", "drawnby")
    approver_identity = str(approval_field_values(attrs).get("approved_by") or "").strip()
    raw_comments = attrs.get("comments")
    if not isinstance(raw_comments, list):
        raw_comments = []
    identity_keys = [uploader_identity, approver_identity]
    identity_keys.extend(str((comment or {}).get("author") or "").strip() for comment in raw_comments)
    resolved_profiles = resolve_identity_profiles(identity_keys)
    uploader_profile = resolved_profiles.get(uploader_identity.lower()) if uploader_identity else None
    if not uploader_profile and uploader_identity:
        uploader_profile = resolve_identity_profile(uploader_identity)
    approver_profile = resolved_profiles.get(approver_identity.lower()) if approver_identity else None
    if not approver_profile and approver_identity:
        approver_profile = resolve_identity_profile(approver_identity)

    return {
        "part": {
            "part_number": part.part_number,
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
        "uploader_profile": uploader_profile,
        "approver_profile": approver_profile,
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
    resolved = resolve_file_token(file_token)
    if not resolved:
        abort(404)
    pf, kind = resolved
    if not _allowed_file_for_share(share, pf.part_number):
        abort(404)
    from app.views.fileserve import _allowed_path as files_allowed_path, _path_for_pf

    path, _rel = _path_for_pf(pf, kind)
    if not path or not os.path.isfile(path) or not files_allowed_path(path):
        abort(404)
    ct, _encoding = mimetypes.guess_type(path)
    resp = send_file(path, mimetype=ct or "application/octet-stream", conditional=True, max_age=0)
    return public_response_headers(resp)


@bp.get("/share/part/<share_id>/<token>/extra/<extra_token>")
def public_part_share_extra_file(share_id: str, token: str, extra_token: str):
    share = _share_or_abort(share_id, token)
    resolved = resolve_extra_file_token(extra_token)
    if not resolved:
        abort(404)
    ef, _kind = resolved
    if not _allowed_file_for_share(share, ef.part_number):
        abort(404)
    base_root = extra_root()
    if not base_root:
        abort(404)
    abs_path = extra_abs_path(ef.rel_path or "")
    if not abs_path or not _allowed_path(abs_path, base_root) or not os.path.isfile(abs_path):
        abort(404)
    ct = ef.mime or mimetypes.guess_type(abs_path)[0] or "application/octet-stream"
    resp = send_file(abs_path, mimetype=ct, conditional=True, max_age=0)
    return public_response_headers(resp)


@bp.get("/api/share/part/<share_id>/<token>/field-config")
def public_share_field_config(share_id: str, token: str):
    _share_or_abort(share_id, token)
    resp = jsonify(
        {
            "ok": True,
            "config": get_field_config(),
            "user_preferences": {"contexts": {}},
            "permissions": {"can_admin": False},
        }
    )
    return public_response_headers(resp)


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
        PartFile.objects(part_number__iexact=part.part_number)
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
        rows.append(_part_file_overview_row_for_share(share, token, pf))

    for ef in (
        PartExtraFile.objects(part_number__iexact=part.part_number)
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
        rows.append(_extra_file_overview_row_for_share(share, token, ef))

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
        urls: list[str] = []
        if not is_dwg and getattr(pf, "thumb_rel_path", None):
            urls.append(_shared_part_file_url(share, token, pf, kind="thumb"))
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
        root["data"] = _rewrite_share_thumbs(share, token, root.get("data") or {})
        resp = jsonify([root])
        return public_response_headers(resp)

    if parent:
        if (parent, parent_rev) not in _share_descendant_keys(share):
            resp = jsonify([])
            return public_response_headers(resp)
        kids = []
        for link in _child_links(parent, parent_rev):
            child_pn = getattr(link, "child_pn", None)
            if not child_pn or child_pn == parent:
                continue
            child_rev = _bom_clean_rev(getattr(link, "child_rev", None)) if hasattr(link, "child_rev") else None
            node = _node(child_pn, link, rev=child_rev, config=config)
            node["data"] = _rewrite_share_thumbs(share, token, node.get("data") or {})
            kids.append(node)
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

    rows_by_key: dict[tuple[str, str], dict] = {}
    part_cache: dict[tuple[str, str], tuple[Part | None, dict, str, list[str], set[str], dict]] = {}

    def row_for(child_pn: str, child_rev: str) -> dict:
        key = (child_pn, _bom_clean_rev(child_rev))
        existing = rows_by_key.get(key)
        if existing:
            return existing

        cached = part_cache.get(key)
        if cached is None:
            part_doc = Part.objects(part_number=child_pn, revision=key[1]).first()
            attrs = harvest_part_attrs(part_doc) if part_doc else {}
            effective_rev = _bom_clean_rev(attrs.get("revision") or (part_doc.revision if part_doc else "") or key[1])
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
            "attrs": attrs,
            **values,
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
        child_rev = _bom_clean_rev(getattr(link, "child_rev", "") or "")
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
            next_rev = _bom_clean_rev(getattr(link, "child_rev", "") or "")
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


def _share_docpack_options_payload(part_number: str, revision: str, depth: str) -> dict:
    flat = _flatten_bom(part_number, revision, full=(depth != "top"))
    flat.append((part_number, revision or "", 1.0))

    groups = set()
    for pnr, rev, _qty in flat:
        q = PartFile.objects(part_number__iexact=pnr)
        if rev is not None:
            q = q.filter(revision__iexact=(rev or ""))
        for pf in q.only("ext_group"):
            if pf.ext_group:
                groups.add(str(pf.ext_group))

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
                "token_prefix": share.token_prefix or "",
                "pn": part_number,
                "rev": revision,
                "depth": depth,
            },
        )
    except Exception:
        pass
    return _public_json(_share_docpack_options_payload(part_number, revision, depth))


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

    try:
        name, blob, mime = build_docpack(opts)
    except RuntimeError as exc:
        return _public_json({"error": str(exc)}, 400)

    record_part_share_access(share, kind="docpack_build")
    try:
        log_action(
            "part.share.docpack.build",
            resource_type="part_share",
            resource=f"{share.part_number}:{share.revision or ''}",
            meta={
                "share_id": str(share.id),
                "token_prefix": share.token_prefix or "",
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
        pass

    resp = send_file(BytesIO(blob), mimetype=mime, as_attachment=True, download_name=name)
    return public_response_headers(resp)


@bp.get("/api/parts/<path:pn>/shares")
@login_required
def list_part_shares(pn: str):
    if not _is_admin(current_user):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    rev = normalize_share_revision(request.args.get("rev"))
    part = _find_part_doc(pn, rev)
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
    if not _is_admin(current_user):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    payload = request.get_json(force=True, silent=True) or {}
    rev = normalize_share_revision(payload.get("rev") if "rev" in payload else request.args.get("rev"))
    part = _find_part_doc(pn, rev)
    if not part:
        return jsonify({"ok": False, "error": "not_found"}), 404
    expires_in_days = int(payload.get("expires_in_days") or 30)
    if expires_in_days < 1 or expires_in_days > 365:
        return jsonify({"ok": False, "error": "invalid_expiry"}), 400
    allow_children = _flag_enabled(payload.get("allow_children"))
    allow_docpacks = _flag_enabled(payload.get("allow_docpacks"))
    allow_attributes = _flag_enabled(payload.get("allow_attributes"))
    share, raw_token = create_part_share(
        part.part_number,
        part.revision or "",
        created_by=current_user,
        expires_in_days=expires_in_days,
        allow_children=allow_children,
        allow_docpacks=allow_docpacks,
        allow_attributes=allow_attributes,
    )
    try:
        log_action(
            "part.share.create",
            resource_type="part_share",
            resource=f"{part.part_number}:{normalize_share_revision(part.revision)}",
            meta={
                "share_id": str(share.id),
                "expires_in_days": expires_in_days,
                "token_prefix": share.token_prefix,
                "allow_children": allow_children,
                "allow_docpacks": allow_docpacks,
                "allow_attributes": allow_attributes,
            },
        )
    except Exception:
        pass
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
    if not _is_admin(current_user):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    share = PartShareLink.objects(id=share_id).first()
    if not share:
        return jsonify({"ok": False, "error": "not_found"}), 404
    if str(share.part_number or "").strip().lower() != str(pn or "").strip().lower():
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
            meta={"share_id": str(share.id), "token_prefix": share.token_prefix},
        )
    except Exception:
        pass
    return jsonify({"ok": True})

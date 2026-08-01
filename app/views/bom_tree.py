# app/views/bom_tree.py
from flask import Blueprint, request, jsonify, current_app, g, has_request_context
from flask_login import login_required
from app.models.artifact import PartFile
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.thumbs import preview_png_urls_for
from app.services.attrs import harvest_part_attrs
from app.services.canonical_fields import canonical_process_label_for_part
from app.services.processmeta import normalize_processes
from flask_login import current_user
from app.services.authorization import (
    authorised_part_pairs,
    has_permission,
    require_permission,
    scope_queryset,
)
from app.services.field_policies import (
    filter_part_custom_fields,
    filter_response_fields,
    response_context,
)
from app.services.file_security import managed_file_group_allowed
from app.services.audit import log_action
from app.services.field_config import context_field_ids, get_field_config, resolve_part_field_values
from app.services.part_norm import clean_rev
from app.services.part_review_status import part_review_status_map

bp = Blueprint("bom_tree_api", __name__, url_prefix="/api")

def _resolve_scoped_revision(pn: str, revision: object, user=None) -> str:
    revision_clean = clean_rev(revision)
    if revision_clean:
        return revision_clean
    # Blank child revisions are common, and the authorisation walk plus the
    # render walk both resolve the same part numbers. The lookup depends only
    # on (pn, user), so memoise it for the request instead of re-querying and
    # re-hydrating the same Part for every link that references it.
    # The lookup is scope-filtered, so the identity is part of the cache key:
    # two users in one request must never share a resolved revision.
    key = (str(pn or "").strip().casefold(), str(getattr(user, "id", user) or ""))
    cache = None
    if has_request_context():
        cache = getattr(g, "_bom_scoped_revision_cache", None)
        if cache is None:
            cache = {}
            g._bom_scoped_revision_cache = cache
        if key in cache:
            return cache[key]
    query = Part.objects(part_number__iexact=str(pn or "").strip())
    if user is not None:
        query = scope_queryset(query, user, "parts")
    part = query.order_by("-updated_at").only("revision", "attrs").first()
    if not part:
        resolved = ""
    else:
        attrs = harvest_part_attrs(part)
        resolved = clean_rev(attrs.get("revision") or part.revision or "")
    if cache is not None:
        cache[key] = resolved
    return resolved


def _has_children(pn: str, rev: str | None = None) -> bool:
    if "parent_pn" in BOMLink._fields:
        return bool(_child_links(pn, rev, current_user))
    p = Part.objects(part_number=pn).only("id").first()
    if not p:
        return False
    return BOMLink.objects(parent=p).limit(1).count() > 0


def _coverage_groups(pn: str, rev: str) -> set[str]:
    if not has_permission(current_user, "files.read"):
        return set()
    groups: set[str] = set()
    for row in PartFile.objects(part_number__iexact=pn, revision__iexact=clean_rev(rev)).only("ext_group"):
        if row.ext_group and managed_file_group_allowed(current_user, row.ext_group):
            groups.add(str(row.ext_group).lower())
    return groups


def _child_links(parent_pn: str, parent_rev: str | None, user=None):
    if "parent_pn" not in BOMLink._fields:
        p = Part.objects(part_number=parent_pn).only("id").first()
        if not p:
            return []
        return list(BOMLink.objects(parent=p).only("child", "qty", "uom", "alt_group"))
    links = list(
        BOMLink.objects(parent_pn=parent_pn).only(
            "parent_rev",
            "child_pn",
            "qty",
            "uom",
            "alt_group",
            "child_rev",
            "occurrences",
        )
    )
    if parent_rev is None:
        return links
    expected_rev = _resolve_scoped_revision(parent_pn, parent_rev, user)
    return [
        link
        for link in links
        if _resolve_scoped_revision(
            parent_pn,
            getattr(link, "parent_rev", ""),
            user,
        ).casefold()
        == expected_rev.casefold()
    ]


def _resolved_child_pair(link, user=None) -> tuple[str, str]:
    child_pn = str(getattr(link, "child_pn", "") or "").strip()
    return (
        child_pn,
        _resolve_scoped_revision(
            child_pn,
            getattr(link, "child_rev", ""),
            user,
        )
        if child_pn
        else "",
    )


def _bom_is_fully_authorised(user, parent_pn: str, parent_rev: str) -> bool:
    """Deny a BOM response when any exact descendant is inaccessible."""

    queue = [(str(parent_pn or "").strip(), clean_rev(parent_rev))]
    visited: set[tuple[str, str]] = set()
    while queue:
        current = queue.pop()
        normalized = (current[0].casefold(), current[1].casefold())
        if normalized in visited:
            continue
        visited.add(normalized)
        links = _child_links(*current, user)
        pairs = [
            _resolved_child_pair(link, user)
            for link in links
            if str(getattr(link, "child_pn", "") or "").strip()
        ]
        allowed = authorised_part_pairs(user, pairs)
        expected = frozenset(
            (child_pn.casefold(), child_rev.casefold())
            for child_pn, child_rev in pairs
        )
        if allowed != expected:
            return False
        queue.extend(pairs)
    return True


def _link_occurrence_qtys(link: BOMLink) -> list[float]:
    occs = getattr(link, "occurrences", None) or []
    if occs:
        out: list[float] = []
        for occ in occs:
            qty_val = occ.get("qty")
            if qty_val is None:
                qty_val = getattr(link, "qty", 1.0)
            out.append(float(qty_val or 0.0))
        return out
    qty = getattr(link, "qty", None)
    if qty is None:
        qty = 1.0
    return [float(qty or 0.0)]

def _node(
    pn: str,
    link=None,
    rev: str | None = None,
    config: dict | None = None,
    review_statuses: dict | None = None,
):
    # Prefer specific revision when provided, else pick latest by updated_at
    rev_clean = clean_rev(rev) if rev is not None else None
    if rev is not None:
        p = Part.objects(part_number=pn, revision=rev_clean).first()
    else:
        p = Part.objects(part_number=pn).order_by("-updated_at").first()
    attrs = harvest_part_attrs(p) if p else {}
    effective_rev = clean_rev(attrs.get("revision") or (p.revision if p else "") or (rev_clean or ""))
    proc_label = _process_label(p, attrs)
    config = config or get_field_config()
    boundary = response_context("parts", current_user)
    thumbs = (
        preview_png_urls_for(pn, effective_rev, user=current_user)
        if has_permission(current_user, "files.read")
        else []
    )
    coverage = _coverage_groups(pn, effective_rev)
    review = (review_statuses or {}).get(
        (str(pn or "").strip(), clean_rev(effective_rev)),
        {"count": 0, "severity": "", "pending": False},
    )
    values = resolve_part_field_values(
        p,
        context_field_ids("bom_tree", config),
        attrs=attrs,
        config=config,
        extra={
            "part_number": pn,
            "revision": effective_rev,
            "description": attrs.get("description", ""),
            "process": proc_label,
            "qty": getattr(link, "qty", None),
            "uom": getattr(link, "uom", None),
            "alt_group": getattr(link, "alt_group", "") or "",
            "thumbnail": thumbs[0] if thumbs else "",
        },
        coverage=coverage,
    )
    custom_field_ids = {
        str(field.get("id") or "").strip()
        for field in config.get("fields") or []
        if isinstance(field, dict)
        and field.get("kind") == "custom"
        and str(field.get("id") or "").strip()
    }
    data = filter_response_fields(
        "bom_line",
        current_user,
        {
            "pn": pn,
            "desc": attrs.get("description", ""),
            "rev": effective_rev,
            "qty": getattr(link, "qty", None),
            "uom": getattr(link, "uom", None),
            "alt_group": getattr(link, "alt_group", "") or "",
            "material": attrs.get("material", ""),
            "finish": attrs.get("finish", ""),
            "process": proc_label,
            "thumb_urls": thumbs,
            "attrs": filter_part_custom_fields(
                current_user,
                attrs,
                context={"policy_context": boundary},
            ),
            "pending_review_count": int(review.get("count") or 0),
            "pending_review_severity": str(review.get("severity") or ""),
            "has_pending_reviews": bool(review.get("pending")),
            **values,
        },
        context={
            "policy_context": boundary,
            "surface": "embedded",
            "configured_fields": custom_field_ids,
        },
    )
    return {
        "key": f"{pn}::{effective_rev}",
        "leaf": not _has_children(pn, effective_rev),
        "data": data,
    }


def _process_label(part: Part | None, attrs: dict | None = None) -> str:
    meta = current_app.config.get("PROCESS_META", {}) or {}
    return canonical_process_label_for_part(part, raw_attrs=attrs or {}, process_meta=meta)

def _is_hardware_node(node: dict) -> bool:
    try:
        data = node.get("data") or {}
        attrs = data.get("attrs") or {}
        meta = current_app.config.get("PROCESS_META", {}) or {}
        procs = normalize_processes({"processes": data.get("processes") or data.get("process") or attrs.get("processes") or []}, meta)
        return "hardware" in procs
    except Exception:
        return False

@bp.get("/bom_tree")
@login_required
@require_permission("bom.read")
def bom_tree():
    config = get_field_config()
    review_statuses = part_review_status_map()
    pn = (request.args.get("pn") or "").strip()
    rev = request.args.get("rev")  # keep None vs ""
    parent = (request.args.get("parent") or "").strip()
    parent_rev = request.args.get("parent_rev")
    scoped_parts = scope_queryset(Part.objects, current_user, "parts")

    if pn:
        # Build root node for specific revision if provided; else latest
        if rev is not None:
            p = scoped_parts.filter(
                part_number__iexact=pn,
                revision__iexact=clean_rev(rev),
            ).first()
        else:
            p = scoped_parts.filter(part_number__iexact=pn).order_by("-updated_at").first()
        if not p:
            return jsonify([])
        root_rev = clean_rev(rev) if rev is not None else clean_rev(p.revision or "")
        if not _bom_is_fully_authorised(current_user, p.part_number, root_rev):
            return jsonify([]), 403
        root = _node(
            p.part_number,
            rev=(root_rev if rev is not None else root_rev),
            config=config,
            review_statuses=review_statuses,
        )
        root["children"] = []   # lazy
        try:
            log_action("bom.view", resource_type="bom", resource=f"root:{p.part_number}:{p.revision or ''}")
        except Exception:
            pass
        return jsonify([root])
 
    if parent:
        parent_part_query = scoped_parts.filter(part_number__iexact=parent)
        if parent_rev is not None:
            parent_part_query = parent_part_query.filter(
                revision__iexact=clean_rev(parent_rev)
            )
        else:
            parent_part_query = parent_part_query.order_by("-updated_at")
        parent_part = parent_part_query.first()
        if not parent_part:
            return jsonify([]), 403
        exact_parent_rev = clean_rev(parent_part.revision or "")
        if not _bom_is_fully_authorised(
            current_user,
            parent_part.part_number,
            exact_parent_rev,
        ):
            return jsonify([]), 403
        # children
        if "parent_pn" in BOMLink._fields:
            links = _child_links(
                parent_part.part_number,
                exact_parent_rev,
                current_user,
            )
            child_pairs = [
                _resolved_child_pair(link, current_user)
                for link in links
                if getattr(link, "child_pn", None)
            ]
            allowed_children = authorised_part_pairs(current_user, child_pairs)
            if len(allowed_children) != len(
                {
                    (
                        str(child_pn or "").strip().casefold(),
                        str(child_rev or "").strip().casefold(),
                    )
                    for child_pn, child_rev in child_pairs
                    if str(child_pn or "").strip()
                }
            ):
                return jsonify([]), 403
            kids = []
            for l in links:
                child_pn = getattr(l, "child_pn", None)
                if child_pn and child_pn != parent:
                    _, c_rev = _resolved_child_pair(l, current_user)
                    kids.append(_node(child_pn, l, rev=c_rev, config=config, review_statuses=review_statuses))
            try:
                log_action("bom.view", resource_type="bom", resource=f"children:{parent}:{(parent_rev or '')}")
            except Exception:
                pass
            kids.sort(key=lambda n: 1 if _is_hardware_node(n) else 0)
            return jsonify(kids)
        else:
            pp = parent_part
            if not pp:
                return jsonify([])
            links = BOMLink.objects(parent=pp).only("child","qty","uom","alt_group")
            kids = []
            for l in links:
                c = getattr(l, "child", None)
                child_pn = getattr(c, "part_number", None) if c else None
                if child_pn and child_pn != parent:
                    if not authorised_part_pairs(
                        current_user,
                        [(child_pn, getattr(c, "revision", "") or "")],
                    ):
                        return jsonify([]), 403
                    kids.append(_node(child_pn, l, config=config, review_statuses=review_statuses))
            try:
                log_action("bom.view", resource_type="bom", resource=f"children:{parent}")
            except Exception:
                pass
            kids.sort(key=lambda n: 1 if _is_hardware_node(n) else 0)
            return jsonify(kids)

    return jsonify([])


@bp.get("/bom_flat")
@login_required
@require_permission("bom.read")
def bom_flat():
    config = get_field_config()
    review_statuses = part_review_status_map()
    pn = (request.args.get("pn") or "").strip()
    rev = request.args.get("rev")
    if not pn:
        return jsonify([])

    scoped_parts = scope_queryset(Part.objects, current_user, "parts")
    if rev is not None:
        root_part = scoped_parts.filter(
            part_number__iexact=pn,
            revision__iexact=clean_rev(rev),
        ).first()
    else:
        root_part = scoped_parts.filter(part_number__iexact=pn).order_by("-updated_at").first()
    if not root_part:
        return jsonify([])

    root_rev = clean_rev(rev) if rev is not None else clean_rev(root_part.revision or "")
    if not _bom_is_fully_authorised(
        current_user,
        root_part.part_number,
        root_rev,
    ):
        return jsonify([]), 403
    rows_by_key: dict[tuple[str, str], dict] = {}
    part_cache: dict[tuple[str, str], tuple[Part | None, dict, str, list[str], set[str], dict]] = {}

    def row_for(child_pn: str, child_rev: str) -> dict:
        key = (child_pn, clean_rev(child_rev))
        existing = rows_by_key.get(key)
        if existing:
            return existing

        cached = part_cache.get(key)
        if cached is None:
            part_doc = scoped_parts.filter(
                part_number__iexact=child_pn,
                revision__iexact=key[1],
            ).first()
            attrs = harvest_part_attrs(part_doc) if part_doc else {}
            effective_rev = clean_rev(attrs.get("revision") or (part_doc.revision if part_doc else "") or key[1])
            proc_label = _process_label(part_doc, attrs)
            thumbs = (
                preview_png_urls_for(
                    child_pn,
                    effective_rev,
                    user=current_user,
                )
                if has_permission(current_user, "files.read")
                else []
            )
            coverage = _coverage_groups(child_pn, effective_rev)
            values = resolve_part_field_values(
                part_doc,
                context_field_ids("bom_tree", config),
                attrs=attrs,
                config=config,
                extra={
                    "part_number": child_pn,
                    "revision": effective_rev,
                    "description": attrs.get("description", ""),
                    "process": proc_label,
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
        review = review_statuses.get(
            (str(child_pn or "").strip(), clean_rev(key[1])),
            {"count": 0, "severity": "", "pending": False},
        )
        boundary = response_context("parts", current_user)
        custom_field_ids = {
            str(field.get("id") or "").strip()
            for field in config.get("fields") or []
            if isinstance(field, dict)
            and field.get("kind") == "custom"
            and str(field.get("id") or "").strip()
        }
        row = filter_response_fields(
            "bom_line",
            current_user,
            {
            "row_key": f"{child_pn}::{key[1]}",
            "part_number": child_pn,
            "revision": key[1],
            "description": attrs.get("description", ""),
            "qty": 0.0,
            "uom": "",
            "alt_group": "",
            "process": proc_label,
            "thumb_urls": thumbs,
            "attrs": filter_part_custom_fields(
                current_user,
                attrs,
                context={"policy_context": boundary},
            ),
            "pending_review_count": int(review.get("count") or 0),
            "pending_review_severity": str(review.get("severity") or ""),
            "has_pending_reviews": bool(review.get("pending")),
            **values,
            },
            context={
                "policy_context": boundary,
                "surface": "embedded",
                "configured_fields": custom_field_ids,
            },
        )
        rows_by_key[key] = row
        return row

    root_key = (root_part.part_number, root_rev)
    stack: list[tuple[str, str, float, str, str, tuple[tuple[str, str], ...]]] = []
    root_links = _child_links(root_part.part_number, root_rev, current_user)
    root_child_pairs = [
        _resolved_child_pair(link, current_user)
        for link in root_links
        if getattr(link, "child_pn", None)
    ]
    allowed_root_children = authorised_part_pairs(current_user, root_child_pairs)
    if len(allowed_root_children) != len(
        {
            (
                str(child_pn or "").strip().casefold(),
                str(child_rev or "").strip().casefold(),
            )
            for child_pn, child_rev in root_child_pairs
            if str(child_pn or "").strip()
        }
    ):
        return jsonify([]), 403
    for link in root_links:
        child_pn = getattr(link, "child_pn", None)
        if not child_pn:
            continue
        _, child_rev = _resolved_child_pair(link, current_user)
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

        child_links = _child_links(child_pn, child_rev, current_user)
        descendant_pairs = [
            _resolved_child_pair(link, current_user)
            for link in child_links
            if getattr(link, "child_pn", None)
        ]
        allowed_descendants = authorised_part_pairs(current_user, descendant_pairs)
        if len(allowed_descendants) != len(
            {
                (
                    str(next_pn or "").strip().casefold(),
                    str(next_rev or "").strip().casefold(),
                )
                for next_pn, next_rev in descendant_pairs
                if str(next_pn or "").strip()
            }
        ):
            return jsonify([]), 403
        for link in child_links:
            next_pn = getattr(link, "child_pn", None)
            if not next_pn:
                continue
            _, next_rev = _resolved_child_pair(link, current_user)
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

    try:
        log_action("bom.view", resource_type="bom", resource=f"flat:{root_part.part_number}:{root_rev}")
    except Exception:
        pass
    return jsonify(rows)

# app/views/bom_tree.py
from flask import Blueprint, request, jsonify, current_app, g, has_request_context
from flask_login import login_required
from app.models.artifact import PartFile
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.thumbs import preview_png_urls_for, preview_png_urls_map
from app.services.attrs import harvest_part_attrs
from app.services.canonical_fields import canonical_process_label_for_part
from flask_login import current_user
from app.services.authorization import (
    authorised_part_pairs,
    parts_scope_is_unrestricted,
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


def _has_children_map(pairs) -> dict[tuple[str, str], bool]:
    """Which of these parts have children, in ONE query instead of N.

    _has_children measured ~25 ms per call against a real database, so asking
    it per sibling cost well over a second on a wide assembly. The parent side
    of a BOM link is matched case-insensitively here to mirror _child_links.
    """
    names = {str(pn or "").strip() for pn, _rev in pairs if str(pn or "").strip()}
    if not names:
        return {}
    try:
        parents = {
            str(value or "").strip().casefold()
            for value in BOMLink.objects(parent_pn__in=list(names)).distinct("parent_pn")
        }
    except Exception:
        # Never let this optimisation break the tree: fall back to per-node.
        return {}
    return {
        (str(pn or "").strip(), clean_rev(rev)): str(pn or "").strip().casefold() in parents
        for pn, rev in pairs
    }


def _coverage_from_part(part) -> set[str]:
    """File-group coverage read from the part document, with no query at all.

    part.file_groups is materialised at IMPORT by sync_part_materialized_fields
    and refreshed by the rebuild commands. It holds exactly what this function
    used to recompute: the lowercase set of file groups present for the part.

    Recomputing it from PartFile cost one query per node - measured at 3852
    part_files queries in a single flat-BOM request. The answer was already
    denormalised onto the part; the query path simply was not reading it.

    Permission filtering stays, because coverage is shown to the user and not
    every role may see every group. That part is in memory and free.
    """
    if part is None or not has_permission(current_user, "files.read"):
        return set()
    return {
        group
        for group in (
            str(g or "").strip().lower() for g in (getattr(part, "file_groups", None) or [])
        )
        if group and managed_file_group_allowed(current_user, group)
    }


def _coverage_groups(pn: str, rev: str) -> set[str]:
    """Recompute coverage from PartFile. Fallback only.

    Kept for parts whose materialised fields have never been built - an
    instance predating them, or a part imported before the rebuild was run.
    Prefer _coverage_from_part, which needs no query.
    """
    if not has_permission(current_user, "files.read"):
        return set()
    groups: set[str] = set()
    for row in PartFile.objects(part_number__iexact=pn, revision__iexact=clean_rev(rev)).only("ext_group"):
        if row.ext_group and managed_file_group_allowed(current_user, row.ext_group):
            groups.add(str(row.ext_group).lower())
    return groups


def _coverage_map_for(pairs) -> dict:
    """File-group coverage for many parts in ONE query.

    _coverage_groups asks PartFile for a single part at a time, and it is
    called for every node of a tree. Measured on a real assembly: part_files
    was queried 3852 times in one flat-BOM request. The parts are all known up
    front, so this reads them together and groups in memory.

    Keyed case-insensitively, because part numbers are matched that way
    throughout this codebase.
    """
    if not has_permission(current_user, "files.read"):
        return {}
    names = sorted({str(pn or "").strip() for pn, _rev in pairs if str(pn or "").strip()})
    if not names:
        return {}
    coverage: dict = {}
    for row in PartFile.objects(part_number__in=names).only(
        "part_number", "revision", "ext_group"
    ):
        group = str(getattr(row, "ext_group", "") or "").strip()
        if not group or not managed_file_group_allowed(current_user, group):
            continue
        key = (
            str(row.part_number or "").strip().casefold(),
            clean_rev(row.revision or "").casefold(),
        )
        coverage.setdefault(key, set()).add(group.lower())
    return coverage


def _coverage_from_map(coverage_map: dict | None, pn: str, rev: str) -> set[str] | None:
    """Read a batched coverage entry, or None when there is no batch."""
    if coverage_map is None:
        return None
    key = (str(pn or "").strip().casefold(), clean_rev(rev).casefold())
    return coverage_map.get(key, set())


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


def _authorised_child_pairs(user, parent_pn: str, parent_rev: str) -> set[tuple[str, str]]:
    """The DIRECT children of one part that this user may see.

    Lazy, per-level authorisation. The previous whole-tree check walked every
    descendant to answer a question about one level: 1342 parts and ~6 seconds
    for a 2034-node assembly, paid again on every expansion.

    SECURITY CHANGE, made deliberately (see docs/planning/hardeningplan.txt, 2026-08-06):
    an unauthorised child is now HIDDEN rather than causing the entire tree to
    be refused. A user with partial access sees their own branches instead of
    an empty tree. What must still hold - and what the tests pin - is that no
    unauthorised part is ever returned; only the blast radius of a denial
    changed, never what a user can read.
    """
    pairs = [
        _resolved_child_pair(link, user)
        for link in _child_links(parent_pn, parent_rev, user)
        if str(getattr(link, "child_pn", "") or "").strip()
    ]
    if not pairs:
        return set()
    allowed = authorised_part_pairs(user, pairs)
    return {(pn, rev) for pn, rev in pairs if (pn.casefold(), rev.casefold()) in allowed}


def _bom_is_fully_authorised(user, parent_pn: str, parent_rev: str) -> bool:
    """Whole-subtree check, kept for the flat/export paths that need it.

    Breadth-first: one query per level rather than per node.
    """
    # A user whose parts scope filters nothing cannot fail this check, so the
    # walk below is pure cost. Measured on a real assembly: 1801 ms to visit
    # 1347 parts across 10 levels, on EVERY flat-BOM request, to reach a
    # conclusion that was never in doubt. With only 8 concurrent request slots
    # that is what made the server appear to hang while browsing a large tree.
    if parts_scope_is_unrestricted(user):
        return True

    frontier = [(str(parent_pn or "").strip(), clean_rev(parent_rev))]
    visited: set[tuple[str, str]] = set()

    while frontier:
        level = []
        for pair in frontier:
            normalized = (pair[0].casefold(), pair[1].casefold())
            if normalized in visited:
                continue
            visited.add(normalized)
            level.append(pair)
        if not level:
            return True

        parent_names = [pn for pn, _rev in level]
        try:
            level_links = list(
                BOMLink.objects(parent_pn__in=parent_names).only(
                    "parent_pn", "parent_rev", "child_pn", "child_rev"
                )
            )
        except Exception:
            level_links = None

        pairs: list[tuple[str, str]] = []
        if level_links is None:
            for pn, rev in level:
                pairs.extend(
                    _resolved_child_pair(link, user)
                    for link in _child_links(pn, rev, user)
                    if str(getattr(link, "child_pn", "") or "").strip()
                )
        else:
            by_parent: dict[str, list] = {}
            for link in level_links:
                key = str(getattr(link, "parent_pn", "") or "").strip().casefold()
                by_parent.setdefault(key, []).append(link)
            for pn, rev in level:
                expected = _resolve_scoped_revision(pn, rev, user).casefold()
                for link in by_parent.get(pn.casefold(), []):
                    if not str(getattr(link, "child_pn", "") or "").strip():
                        continue
                    if rev is not None and _resolve_scoped_revision(
                        pn, getattr(link, "parent_rev", ""), user
                    ).casefold() != expected:
                        continue
                    pairs.append(_resolved_child_pair(link, user))
        if not pairs:
            return True

        allowed = authorised_part_pairs(user, pairs)
        expected_set = frozenset(
            (child_pn.casefold(), child_rev.casefold()) for child_pn, child_rev in pairs
        )
        if allowed != expected_set:
            return False
        frontier = pairs

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

def _from_parts_map(parts_map: dict | None, pn: str, rev: str | None):
    """Look a child up in the batch the caller already fetched.

    _node used to issue one Part query per child, so expanding a single level
    of twenty children cost twenty round trips - measured as parts=23 inside a
    64-query, one-second request. The children of a level are known before any
    of them is rendered, so they can all be fetched at once.

    Returns None when there is no map, which keeps the per-node query as the
    fallback for callers that have not been converted.
    """
    if parts_map is None:
        return None
    name = str(pn or "").strip()
    if rev is not None:
        return parts_map.get((name.casefold(), clean_rev(rev).casefold()))
    # No revision asked for: the caller batched the newest per part number.
    return parts_map.get((name.casefold(), None))


def _parts_map_for(pairs, scoped_parts) -> dict:
    """One query for every part on a level, keyed case-insensitively."""
    names = sorted({str(pn or "").strip() for pn, _rev in pairs if str(pn or "").strip()})
    if not names:
        return {}
    found: dict = {}
    for doc in scoped_parts.filter(part_number__in=names):
        key = (str(doc.part_number).casefold(), clean_rev(doc.revision or "").casefold())
        found[key] = doc
        # Newest wins for the "no revision requested" lookup.
        latest_key = (str(doc.part_number).casefold(), None)
        current = found.get(latest_key)
        if current is None or (getattr(doc, "updated_at", None) or 0) > (
            getattr(current, "updated_at", None) or 0
        ):
            found[latest_key] = doc
    return found


def _node(
    pn: str,
    link=None,
    rev: str | None = None,
    config: dict | None = None,
    review_statuses: dict | None = None,
    thumbs_map: dict | None = None,
    parts_map: dict | None = None,
    coverage_map: dict | None = None,
    children_map: dict | None = None,
):
    # thumbs_map / children_map let the caller resolve a whole sibling set in
    # one pass. Both were previously computed PER NODE, which is where the
    # expansion time went: preview_png_urls_for measured ~65 ms and
    # _has_children ~25 ms per child, so a 58-child assembly spent over five
    # seconds doing work that batches into a fraction of it. Both stay optional
    # so single-node callers are unaffected.
    # Prefer specific revision when provided, else pick latest by updated_at
    rev_clean = clean_rev(rev) if rev is not None else None
    if rev is not None:
        p = _from_parts_map(parts_map, pn, rev_clean)
        if p is None and parts_map is None:
            p = Part.objects(part_number=pn, revision=rev_clean).first()
    else:
        p = _from_parts_map(parts_map, pn, None)
        if p is None and parts_map is None:
            p = Part.objects(part_number=pn).order_by("-updated_at").first()
    attrs = harvest_part_attrs(p) if p else {}
    effective_rev = clean_rev(attrs.get("revision") or (p.revision if p else "") or (rev_clean or ""))
    proc_label = _process_label(p, attrs)
    config = config or get_field_config()
    boundary = response_context("parts", current_user)
    if thumbs_map is not None:
        thumbs = thumbs_map.get((str(pn or "").strip(), clean_rev(effective_rev)), [])
    else:
        thumbs = (
            preview_png_urls_for(pn, effective_rev, user=current_user)
            if has_permission(current_user, "files.read")
            else []
        )
    # The part document already carries this, written at import time.
    if p is not None and getattr(p, "file_groups", None) is not None:
        coverage = _coverage_from_part(p)
    else:
        coverage = _coverage_from_map(coverage_map, pn, effective_rev)
        if coverage is None:
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
        "leaf": (
            not children_map.get((str(pn or "").strip(), clean_rev(effective_rev)), False)
            if children_map is not None
            else not _has_children(pn, effective_rev)
        ),
        "data": data,
    }


def _process_label(part: Part | None, attrs: dict | None = None) -> str:
    meta = current_app.config.get("PROCESS_META", {}) or {}
    return canonical_process_label_for_part(part, raw_attrs=attrs or {}, process_meta=meta)

def _is_hardware_node(node: dict) -> bool:
    # "process" is the canonical, comma-joined label built by
    # canonical_process_label_for_part, so matching a token is enough.
    label = str((node.get("data") or {}).get("process") or "")
    return "hardware" in [token.strip() for token in label.split(",")]

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
        # The root itself came from a scoped query, so it is already authorised.
        # Its descendants are checked when they are actually expanded - see
        # _authorised_child_pairs.
        root = _node(
            p.part_number,
            rev=(root_rev if rev is not None else root_rev),
            config=config,
            review_statuses=review_statuses,
        )
        root["children"] = []   # lazy
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
            # Hide unauthorised children instead of refusing the whole level.
            allowed_children = authorised_part_pairs(current_user, child_pairs)
            # Resolve the whole sibling set at once instead of per child.
            visible = [
                (l, c_pn, c_rev)
                for l, c_pn, c_rev in (
                    (l, *_resolved_child_pair(l, current_user))
                    for l in links
                    if getattr(l, "child_pn", None) and getattr(l, "child_pn", None) != parent
                )
                if (c_pn.casefold(), c_rev.casefold()) in allowed_children
            ]
            sibling_pairs = [(c_pn, c_rev) for _l, c_pn, c_rev in visible]

            thumbs_map = (
                preview_png_urls_map(sibling_pairs, user=current_user)
                if sibling_pairs and has_permission(current_user, "files.read")
                else {}
            )
            children_map = _has_children_map(sibling_pairs)
            # One query for the whole level instead of one per child.
            parts_map = _parts_map_for(sibling_pairs, scoped_parts)
            coverage_map = _coverage_map_for(sibling_pairs)

            kids = [
                _node(
                    c_pn,
                    l,
                    rev=c_rev,
                    config=config,
                    review_statuses=review_statuses,
                    thumbs_map=thumbs_map,
                    children_map=children_map,
                    parts_map=parts_map,
                    coverage_map=coverage_map,
                )
                for l, c_pn, c_rev in visible
            ]
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
            kids.sort(key=lambda n: 1 if _is_hardware_node(n) else 0)
            return jsonify(kids)

    return jsonify([])


def _flat_subtree_pairs(root_pn: str, root_rev: str, user) -> list[tuple[str, str]]:
    """Every distinct part in a flattened BOM, walking LINKS ONLY.

    Exists so the thumbnails can be resolved in ONE batch. bom_flat used to
    call preview_png_urls_for per unique part, and that measured ~65 ms each -
    on an assembly with a few hundred distinct parts it is the whole response
    time. The link walk here is indexed and cheap by comparison; paying for it
    twice is far less than paying for hundreds of storage scans.

    Same cycle rule as the main traversal: a pair already on the current
    lineage is not followed again.
    """
    pairs: dict[tuple[str, str], None] = {}
    root_key = (str(root_pn or "").strip(), clean_rev(root_rev))
    stack: list[tuple[str, str, tuple[tuple[str, str], ...]]] = [
        (root_key[0], root_key[1], (root_key,))
    ]
    while stack:
        pn, rev, lineage = stack.pop()
        for link in _child_links(pn, rev, user):
            if not getattr(link, "child_pn", None):
                continue
            child_pn, child_rev = _resolved_child_pair(link, user)
            key = (child_pn, clean_rev(child_rev))
            if key in lineage:
                continue
            pairs.setdefault(key, None)
            stack.append((key[0], key[1], lineage + (key,)))
    return list(pairs)


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

    # One storage scan for the whole subtree instead of one per part. This is
    # the difference between a large assembly answering in under a second and
    # the browser giving up on it.
    # Resolve the whole subtree UP FRONT: thumbnails in one batch, and every
    # part document in a single query. row_for used to issue one part query per
    # distinct part, which on a 163-part assembly meant hundreds of round trips.
    subtree_pairs = _flat_subtree_pairs(root_part.part_number, root_rev, current_user)

    flat_thumbs: dict[tuple[str, str], list[str]] = {}
    if subtree_pairs and has_permission(current_user, "files.read"):
        flat_thumbs = preview_png_urls_map(subtree_pairs, user=current_user)

    flat_coverage = _coverage_map_for(subtree_pairs) if subtree_pairs else {}

    flat_parts: dict[tuple[str, str], Part] = {}
    if subtree_pairs:
        names = sorted({pn for pn, _rev in subtree_pairs})
        for doc in scoped_parts.filter(part_number__in=names):
            flat_parts[(doc.part_number, clean_rev(doc.revision or ""))] = doc

    def row_for(child_pn: str, child_rev: str) -> dict:
        key = (child_pn, clean_rev(child_rev))
        existing = rows_by_key.get(key)
        if existing:
            return existing

        cached = part_cache.get(key)
        if cached is None:
            # Batched above. Part numbers are matched case-insensitively
            # everywhere, so try the exact pair, then a folded match, and only
            # query when the pair was not in the subtree walk at all.
            part_doc = flat_parts.get(key)
            if part_doc is None:
                folded = (key[0].casefold(), key[1].casefold())
                part_doc = next(
                    (
                        doc
                        for (pn_k, rev_k), doc in flat_parts.items()
                        if (pn_k.casefold(), rev_k.casefold()) == folded
                    ),
                    None,
                )
            if part_doc is None:
                part_doc = scoped_parts.filter(
                    part_number__iexact=child_pn,
                    revision__iexact=key[1],
                ).first()
            attrs = harvest_part_attrs(part_doc) if part_doc else {}
            effective_rev = clean_rev(attrs.get("revision") or (part_doc.revision if part_doc else "") or key[1])
            proc_label = _process_label(part_doc, attrs)
            # Batched above. The map is keyed by the LINK-resolved revision,
            # while effective_rev can differ when a part's attrs carry another
            # one, so try both before falling back to a single scan - a miss
            # must cost one lookup, not a wrong thumbnail.
            if not has_permission(current_user, "files.read"):
                thumbs = []
            else:
                thumbs = flat_thumbs.get((child_pn, clean_rev(effective_rev)))
                if thumbs is None:
                    thumbs = flat_thumbs.get(key)
                if thumbs is None:
                    thumbs = preview_png_urls_for(child_pn, effective_rev, user=current_user)
            if part_doc is not None and getattr(part_doc, "file_groups", None) is not None:
                coverage = _coverage_from_part(part_doc)
            else:
                coverage = _coverage_from_map(flat_coverage, child_pn, effective_rev)
                if coverage is None:
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
        # No per-node authorisation here. _bom_is_fully_authorised proved the
        # ENTIRE subtree before the descent started, so re-proving every node
        # was one authorisation query per part - hundreds on a real assembly,
        # and the difference between a slow page and a 502.
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

    return jsonify(rows)

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import current_user
from datetime import timedelta
from typing import Dict, List, Tuple
from app.services.acl import (
    permissions_required,
    customer_scope_ids,
    supplier_scope_ids,
    user_has_permission,
)
from app.services.authorization import (
    authorised_get,
    authorised_part_pairs,
    enforce_permission as _require,
    authorise_part_access,
    relationship_job_part_pairs,
    scope_queryset,
    uses_portal_presentation,
)
from app.services.field_policies import (
    filter_response_fields,
    response_context,
)
from mongoengine.queryset.visitor import Q

from app.models.job import Job, JobBOMLine
from app.models.supplier import Supplier
from app.models.customer import Customer
from app.models.auth import User
from app.models.order import Order
from app.models.part import Part
from app.models.bom import BOMLink
from app.services.attrs import harvest_part_attrs
from app.services.thumbs import thumb_urls_for
from app.services.biz_utils import generate_job_number, supplies_job_requirement
from app.services.part_norm import clean_rev
from app.services.timezone_utils import parse_user_datetime, utc_now

bp = Blueprint("admin_jobs", __name__, url_prefix="/admin/jobs")

_JOB_FORM_FIELDS = {
    "csrf_token",
    "job_number",
    "title",
    "description",
    "status",
    "priority",
    "scheduled_start",
    "scheduled_end",
    "participants",
    "vendors",
    "customer",
    "bom_text",
}


def _scoped_job(job_id, permission):
    return authorised_get(
        Job.objects,
        current_user,
        job_id,
        resource_type="jobs",
        permission=permission,
    )


def _job_form_destinations():
    suppliers = scope_queryset(
        Supplier.objects,
        current_user,
        "suppliers",
        permission="jobs.assign",
    ).order_by("name")
    customers = scope_queryset(
        Customer.objects,
        current_user,
        "customers",
        permission="jobs.assign",
    ).order_by("name")
    return suppliers, customers


def _require_job_form_permissions():
    if set(request.form) - _JOB_FORM_FIELDS:
        abort(400)
    if set(request.form) & {"customer", "participants", "vendors"}:
        _require("jobs.assign")
    if "bom_text" in request.form:
        _require("jobs.bom.update")


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")

def _is_portal_only_user(user) -> bool:
    return (
        not user_has_permission(user, "jobs.read")
        or uses_portal_presentation(
            user,
            "jobs.read",
            resource_type="jobs",
        )
    )


def _eligible_job_users():
    out = []
    for u in User.objects().order_by("email"):
        if _is_portal_only_user(u):
            continue
        out.append(u)
    return out

def _filter_job_participants(user_ids):
    if not user_ids:
        return []
    users = list(User.objects(id__in=user_ids))
    out = []
    for u in users:
        if _is_portal_only_user(u):
            continue
        out.append(u)
    return out


_MAX_BOM_DEPTH = 40


def _part_key(pn: str, rev: str | None) -> Tuple[str, str]:
    return ((pn or "").strip().lower(), clean_rev(rev).lower())


def _effective_rev_for_bom(pn: str, rev: str | None) -> str:
    rev_clean = clean_rev(rev)
    if rev_clean:
        return rev_clean
    p = Part.objects(part_number__iexact=(pn or "").strip()).only("revision", "updated_at").order_by("-updated_at").first()
    return clean_rev(getattr(p, "revision", "") if p else "")


def _bom_children_links(parent_pn: str, parent_rev: str | None) -> List[BOMLink]:
    parent_pn = (parent_pn or "").strip()
    if not parent_pn:
        return []
    rev_clean = clean_rev(parent_rev)
    if "parent_rev" in BOMLink._fields:
        scoped = list(BOMLink.objects(parent_pn=parent_pn, parent_rev=rev_clean))
        if scoped:
            return scoped
    return list(BOMLink.objects(parent_pn=parent_pn))


def _link_occurrence_qtys(link: BOMLink) -> List[float]:
    occs = getattr(link, "occurrences", None) or []
    out: List[float] = []
    if occs:
        for occ in occs:
            try:
                q = float(occ.get("qty", getattr(link, "qty", 1.0)) or 0.0)
            except Exception:
                q = 0.0
            if q > 0.0:
                out.append(q)
        if out:
            return out
    try:
        q = float(getattr(link, "qty", 1.0) or 0.0)
    except Exception:
        q = 0.0
    return [q] if q > 0.0 else []


def _expand_part_totals(pn: str, rev: str | None, qty: float) -> Tuple[Dict[Tuple[str, str], float], Dict[Tuple[str, str], Tuple[str, str]]]:
    totals: Dict[Tuple[str, str], float] = {}
    display: Dict[Tuple[str, str], Tuple[str, str]] = {}
    root_pn = (pn or "").strip()
    try:
        root_qty = float(qty or 0.0)
    except Exception:
        root_qty = 0.0
    if not root_pn or root_qty <= 0.0:
        return totals, display

    root_rev = _effective_rev_for_bom(root_pn, rev)
    root_key = _part_key(root_pn, root_rev)
    stack: List[Tuple[str, str, float, int, set[Tuple[str, str]], bool]] = [
        (root_pn, root_rev, root_qty, 0, {root_key}, False)
    ]

    while stack:
        cur_pn, cur_rev, cur_qty, depth, trail, is_cycle = stack.pop()
        key = _part_key(cur_pn, cur_rev)
        totals[key] = totals.get(key, 0.0) + cur_qty
        if key not in display:
            display[key] = (cur_pn, clean_rev(cur_rev))
        if is_cycle or depth >= _MAX_BOM_DEPTH:
            continue

        children: List[Tuple[str, str, float, int, set[Tuple[str, str]], bool]] = []
        for link in _bom_children_links(cur_pn, cur_rev):
            child_pn = (getattr(link, "child_pn", "") or "").strip()
            if not child_pn:
                continue
            child_rev = _effective_rev_for_bom(child_pn, getattr(link, "child_rev", ""))
            child_key = _part_key(child_pn, child_rev)
            child_cycle = child_key in trail
            for occ_qty in _link_occurrence_qtys(link):
                child_total = cur_qty * occ_qty
                if child_total <= 0.0:
                    continue
                next_trail = set(trail)
                next_trail.add(child_key)
                children.append((child_pn, child_rev, child_total, depth + 1, next_trail, child_cycle))

        for item in reversed(children):
            stack.append(item)

    return totals, display


def _expand_part_occurrences(pn: str, rev: str | None, qty: float, root_index: int) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    root_pn = (pn or "").strip()
    try:
        root_qty = float(qty or 0.0)
    except Exception:
        root_qty = 0.0
    if not root_pn or root_qty <= 0.0:
        return rows

    root_rev = _effective_rev_for_bom(root_pn, rev)
    root_level = f"+.{root_index:02d}"
    root_key = _part_key(root_pn, root_rev)
    stack: List[Tuple[str, str, float, int, str, set[Tuple[str, str]], bool]] = [
        (root_pn, root_rev, root_qty, 0, root_level, {root_key}, False)
    ]

    while stack:
        cur_pn, cur_rev, cur_qty, depth, level, trail, is_cycle = stack.pop()
        key = _part_key(cur_pn, cur_rev)
        rows.append(
            {
                "key": key,
                "pn": cur_pn,
                "rev": clean_rev(cur_rev),
                "required": float(cur_qty),
                "depth": depth,
                "level": level,
            }
        )
        if is_cycle or depth >= _MAX_BOM_DEPTH:
            continue

        children: List[Tuple[str, str, float, int, str, set[Tuple[str, str]], bool]] = []
        seq = 0
        for link in _bom_children_links(cur_pn, cur_rev):
            child_pn = (getattr(link, "child_pn", "") or "").strip()
            if not child_pn:
                continue
            child_rev = _effective_rev_for_bom(child_pn, getattr(link, "child_rev", ""))
            child_key = _part_key(child_pn, child_rev)
            child_cycle = child_key in trail
            for occ_qty in _link_occurrence_qtys(link):
                child_total = cur_qty * occ_qty
                if child_total <= 0.0:
                    continue
                seq += 1
                child_level = f"{level}.{seq:02d}"
                next_trail = set(trail)
                next_trail.add(child_key)
                children.append((child_pn, child_rev, child_total, depth + 1, child_level, next_trail, child_cycle))

        for item in reversed(children):
            stack.append(item)

    return rows


def _level_sort_key(level: str) -> List[Tuple[int, object]]:
    out: List[Tuple[int, object]] = []
    for seg in [s for s in str(level or "").split(".") if s and s != "+"]:
        if seg.isdigit():
            out.append((0, int(seg)))
        else:
            out.append((1, seg))
    return out


def _merge_order_link(
    order_links: Dict[Tuple[str, str], Dict[str, Dict[str, str]]],
    key: Tuple[str, str],
    order: Order,
    href: str,
) -> None:
    bucket = order_links.setdefault(key, {})
    order_id = str(order.id)
    if order_id in bucket:
        return
    bucket[order_id] = {
        "order_number": order.order_number,
        "href": href,
        "supplier": getattr(order.supplier, "name", ""),
    }


def _job_required_structure(job: Job, bom_lines=None):
    required_map: Dict[Tuple[str, str], float] = {}
    display_map: Dict[Tuple[str, str], Tuple[str, str]] = {}
    occurrences: List[Dict[str, object]] = []
    root_idx = 0
    for line in (job.bom or []) if bom_lines is None else bom_lines:
        pn = (line.pn or "").strip()
        if not pn:
            continue
        try:
            line_qty = float(line.qty or 0.0)
        except Exception:
            line_qty = 0.0
        if line_qty <= 0.0:
            continue
        root_idx += 1
        rows = _expand_part_occurrences(pn, line.rev or "", line_qty, root_idx)
        for row in rows:
            key = row["key"]
            required_map[key] = required_map.get(key, 0.0) + float(row.get("required") or 0.0)
            display_map.setdefault(key, (row.get("pn") or "", row.get("rev") or ""))
            occurrences.append(row)
    return required_map, display_map, occurrences


def _job_order_coverage(
    job: Job,
    *,
    required_keys: set[Tuple[str, str]] | None = None,
    can_manage_orders: bool = False,
    include_links: bool = False,
    use_received: bool = False,
):
    ordered_map: Dict[Tuple[str, str], float] = {}
    display_map: Dict[Tuple[str, str], Tuple[str, str]] = {}
    order_links: Dict[Tuple[str, str], Dict[str, Dict[str, str]]] = {}

    for o in _orders_for_job(job):
        status = (o.status or "").strip().lower()
        if status in ("draft", "cancelled") or not supplies_job_requirement(o):
            continue
        href = ""
        if include_links:
            href = (
                url_for("admin_orders.orders_edit", order_id=str(o.id))
                if can_manage_orders
                else url_for("admin_orders.orders_view", order_id=str(o.id))
            )
        for line in (o.lines or []):
            pn = (line.pn or "").strip()
            if not pn:
                continue
            try:
                base_qty = float(line.qty or 0.0)
            except Exception:
                base_qty = 0.0
            if use_received:
                try:
                    base_qty = float(line.qty_received or 0.0)
                except Exception:
                    base_qty = 0.0
                if base_qty <= 0.0 and status in ("confirmed", "delivered"):
                    try:
                        base_qty = float(line.qty or 0.0)
                    except Exception:
                        base_qty = 0.0
            if base_qty <= 0.0:
                continue

            expanded_totals, expanded_display = _expand_part_totals(pn, line.rev or "", base_qty)
            for key, qty in expanded_totals.items():
                if required_keys is not None and key not in required_keys:
                    continue
                ordered_map[key] = ordered_map.get(key, 0.0) + float(qty or 0.0)
                if key not in display_map:
                    display_map[key] = expanded_display.get(key, (pn, clean_rev(line.rev)))
                if include_links:
                    _merge_order_link(order_links, key, o, href)

    return ordered_map, display_map, order_links


def _authorised_requirement_keys(required_map, display_map, user, allowed_pairs=None):
    """Which exploded requirement keys this user may see and order.

    ``allowed_pairs`` may only be supplied when it already covers descendants,
    as the relationship scope does. The global-scope fallback authorises the
    job's own BOM lines only, so it must be left to this function to authorise
    the whole explosion instead.
    """

    allowed = allowed_pairs
    if allowed is None:
        allowed = authorised_part_pairs(
            user,
            [display_map.get(key, key) for key in required_map],
        )
    return {
        key
        for key in required_map
        if (
            str(display_map.get(key, key)[0] or "").strip().casefold(),
            str(display_map.get(key, key)[1] or "").strip().casefold(),
        )
        in allowed
    }


def job_orderable_keys(job: Job, user) -> set[Tuple[str, str]]:
    """Every part key the job page offers this user, at any BOM level.

    The order endpoint authorises against this, so a posted selection is
    accepted exactly when the remaining tables could have offered it.
    """

    required_map, display_map, _ = _job_required_structure(job)
    if not required_map:
        return set()
    allowed_pairs = relationship_job_part_pairs(user, job)
    if allowed_pairs is not None:
        allowed_pairs = {
            (str(pn or "").strip().casefold(), str(rev or "").strip().casefold())
            for pn, rev in allowed_pairs
        }
    return _authorised_requirement_keys(required_map, display_map, user, allowed_pairs)


def _build_job_bom_rollup(
    job: Job,
    can_manage_orders: bool,
    bom_lines=None,
    user=None,
    allowed_pairs=None,
):
    required_map, display_map, occurrences = _job_required_structure(job, bom_lines)
    if user is not None:
        visible = _authorised_requirement_keys(
            required_map, display_map, user, allowed_pairs
        )
        required_map = {
            key: value for key, value in required_map.items() if key in visible
        }
        occurrences = [
            occurrence
            for occurrence in occurrences
            if occurrence.get("key") in required_map
        ]
    required_keys = set(required_map.keys()) if required_map else None
    ordered_map, ordered_display, order_links_raw = _job_order_coverage(
        job,
        required_keys=required_keys,
        can_manage_orders=can_manage_orders,
        include_links=True,
        use_received=False,
    )
    for key, val in ordered_display.items():
        display_map.setdefault(key, val)

    flat_rows = []
    rows_by_key = {}
    for key in sorted(
        required_map.keys(),
        key=lambda k: (
            (display_map.get(k, (k[0], k[1]))[0] or "").lower(),
            (display_map.get(k, (k[0], k[1]))[1] or "").lower(),
        ),
    ):
        pn_disp, rev_disp = display_map.get(key, (key[0], key[1]))
        req = float(required_map.get(key, 0.0) or 0.0)
        ordered = float(ordered_map.get(key, 0.0) or 0.0)
        rem = max(req - ordered, 0.0)
        over = max(ordered - req, 0.0)
        meta = _part_meta(pn_disp, rev_disp, user=user)
        links = sorted(
            list((order_links_raw.get(key) or {}).values()),
            key=lambda item: (item.get("order_number") or ""),
        )
        row = {
            "pn": pn_disp,
            "rev": meta.get("rev") or rev_disp or "",
            "required": req,
            "ordered": ordered,
            "remaining": rem,
            "over": over,
            "desc": meta.get("desc") or "",
            "thumb": meta.get("thumb") or "",
            "orders": links,
        }
        rows_by_key[key] = row
        flat_rows.append(row)

    ordered_parts = [r for r in flat_rows if float(r.get("ordered") or 0.0) > 0.0]
    remaining_parts_flat = [r for r in flat_rows if float(r.get("remaining") or 0.0) > 0.0]
    oversupplied_parts = [r for r in flat_rows if float(r.get("over") or 0.0) > 0.0]

    remaining_budget = {
        k: max(float(required_map.get(k, 0.0) or 0.0) - float(ordered_map.get(k, 0.0) or 0.0), 0.0)
        for k in required_map.keys()
    }
    covered_budget = {
        k: max(min(float(ordered_map.get(k, 0.0) or 0.0), float(required_map.get(k, 0.0) or 0.0)), 0.0)
        for k in required_map.keys()
    }
    remaining_parts_tree = []
    for occ in sorted(occurrences, key=lambda item: _level_sort_key(item.get("level") or "")):
        key = occ.get("key")
        if key not in required_map:
            continue
        req_occ = float(occ.get("required") or 0.0)
        if req_occ <= 0.0:
            continue
        used = min(req_occ, covered_budget.get(key, 0.0))
        covered_budget[key] = max(covered_budget.get(key, 0.0) - used, 0.0)
        rem_occ = min(max(req_occ - used, 0.0), remaining_budget.get(key, 0.0))
        remaining_budget[key] = max(remaining_budget.get(key, 0.0) - rem_occ, 0.0)
        if rem_occ <= 0.0:
            continue
        base = rows_by_key.get(key)
        remaining_parts_tree.append(
            {
                "pn": occ.get("pn") or "",
                "rev": occ.get("rev") or "",
                "required": req_occ,
                "ordered": used,
                "remaining": rem_occ,
                "over": float(base.get("over") or 0.0) if base else 0.0,
                "desc": (base or {}).get("desc") or "",
                "thumb": (base or {}).get("thumb") or "",
                "orders": (base or {}).get("orders") or [],
                "level": occ.get("level") or "",
                "depth": int(occ.get("depth") or 0),
            }
        )

    return {
        "required_map": required_map,
        "ordered_map": ordered_map,
        "flat_rows": flat_rows,
        "ordered_parts": ordered_parts,
        "remaining_parts_flat": remaining_parts_flat,
        "remaining_parts_tree": remaining_parts_tree,
        "oversupplied_parts": oversupplied_parts,
    }


@bp.get("/")
@permissions_required("jobs.read")
def jobs_list():
    show_deleted = _parse_bool(request.args.get("show_deleted"))
    q = Job.objects() if show_deleted else Job.objects(is_deleted=False)
    q = scope_queryset(q, current_user, "jobs")
    status = (request.args.get("status") or "").strip()
    if status:
        q = q.filter(status=status)
    priority = (request.args.get("priority") or "").strip()
    if priority:
        q = q.filter(priority=priority)
    job_q = (request.args.get("job_q") or "").strip()
    title_q = (request.args.get("title_q") or "").strip()
    customer_q = (request.args.get("customer_q") or "").strip()
    legacy_q = (request.args.get("q") or "").strip()
    if legacy_q and not (job_q or title_q or customer_q):
        job_q = legacy_q
        title_q = legacy_q
        customer_q = legacy_q
    if job_q:
        q = q.filter(job_number__icontains=job_q)
    if title_q:
        q = q.filter(Q(title__icontains=title_q) | Q(description__icontains=title_q))
    if customer_q and not user_has_permission(current_user, "customers.read"):
        abort(403)
    if customer_q:
        custs = Customer.objects(Q(name__icontains=customer_q) | Q(code__icontains=customer_q))
        if custs:
            q = q.filter(customer__in=list(custs))
    date_from = _parse_date(request.args.get("from"))
    date_to = _parse_date(request.args.get("to"), end_of_day=True)
    if date_from:
        q = q.filter(scheduled_start__gte=date_from)
    if date_to:
        q = q.filter(scheduled_end__lte=date_to)

    is_external = uses_portal_presentation(
        current_user,
        "jobs.read",
        resource_type="jobs",
    )
    cust_ids = customer_scope_ids(current_user)
    supp_ids = supplier_scope_ids(current_user)
    mask_vendors = bool(is_external)
    mask_customer = bool(is_external and supp_ids and not cust_ids)
    mask_participants = bool(is_external)
    jobs = q.order_by("job_number")
    safe_jobs = []
    for j in jobs:
        cust_name = "Hidden" if mask_customer else "-"
        cust_id = ""
        if not mask_customer:
            try:
                cust_name = j.customer.name if j.customer else "-"
                cust_id = str(j.customer.id) if j.customer else ""
            except Exception:
                pass
        vendors = "Hidden" if mask_vendors else "-"
        if not mask_vendors:
            try:
                vendors = ", ".join([v.name for v in (j.vendors or [])])
            except Exception:
                pass
        parts = "Hidden" if mask_participants else "-"
        if not mask_participants:
            try:
                parts = ", ".join([u.email for u in (j.participants or [])])
            except Exception:
                pass
        required_total, ordered_total, received_total = (
            (0.0, 0.0, 0.0) if is_external else _job_order_totals(j)
        )
        ordered_pct = (ordered_total / required_total * 100.0) if required_total else 0.0
        received_pct = (received_total / ordered_total * 100.0) if ordered_total else 0.0
        safe_jobs.append(
            {
                "id": j.id,
                "job_number": j.job_number,
                "title": j.title,
                "description": j.description,
                "status": j.status,
                "is_deleted": bool(getattr(j, "is_deleted", False)),
                "priority": j.priority,
                "scheduled_start": j.scheduled_start,
                "scheduled_end": j.scheduled_end,
                "customer_name": cust_name or "-",
                "customer_id": cust_id,
                "participants": parts or "-",
                "vendors": vendors or "-",
                # Deletion consequences surfaced in the confirm prompt: orders
                # get unlinked, and portal users lose the part access this job
                # grants them.
                "order_count": 0 if is_external else Order.objects(job=j).count(),
                "part_count": 0 if is_external else len(j.bom or []),
                "vendor_count": 0 if is_external else len(j.vendors or []),
                "external": bool(is_external),
                "required_total": required_total,
                "ordered_total": ordered_total,
                "received_total": received_total,
                "ordered_pct": min(100.0, max(0.0, ordered_pct)),
                "received_pct": min(100.0, max(0.0, received_pct)),
            }
        )
    now = utc_now()
    base_q = scope_queryset(Job.objects(is_deleted=False), current_user, "jobs")
    active_count = base_q.filter(status__in=["released", "in_progress"]).count()
    overdue_count = base_q.filter(status__in=["released", "in_progress"], scheduled_end__lt=now).count()
    completed_week = base_q.filter(status="completed", actual_end__gte=now - timedelta(days=7)).count()
    deleted_count = scope_queryset(
        Job.objects(is_deleted=True),
        current_user,
        "jobs",
    ).count()
    return render_template(
        "admin/jobs_list.html",
        jobs=safe_jobs,
        active_count=active_count,
        overdue_count=overdue_count,
        completed_week=completed_week,
        deleted_count=deleted_count,
        filters={
            "status": status,
            "priority": priority,
            "job_q": job_q,
            "title_q": title_q,
            "customer_q": customer_q,
            "show_deleted": show_deleted,
            "from": request.args.get("from") or "",
            "to": request.args.get("to") or "",
        },
    )


@bp.get("/<job_id>")
@permissions_required("jobs.read")
def jobs_view(job_id):
    j = _scoped_job(job_id, "jobs.read")
    if not j:
        abort(404)
    is_external = uses_portal_presentation(
        current_user,
        "jobs.read",
        resource_type="jobs",
    )
    cust_ids = customer_scope_ids(current_user)
    supp_ids = supplier_scope_ids(current_user)
    supplier_only = bool(is_external and supp_ids and not cust_ids)
    # Supplier presentation never needs the customer DBRef.  Avoid both the
    # disclosure and an unnecessary dereference on the external hot path.
    if not supplier_only:
        try:
            _ = j.customer.id if j.customer else None
        except Exception:
            j.customer = None
    users = _eligible_job_users() if user_has_permission(current_user, "jobs.assign") else []
    suppliers, customers = ([], []) if is_external else _job_form_destinations()
    # Two different sets, and they must not be confused. ``allowed_bom`` only
    # ever authorises the job's own BOM lines. ``rollup_pairs`` authorises the
    # exploded multi-level requirement, so it may only be pre-supplied when it
    # already covers descendants - which the relationship scope does and the
    # global-scope fallback does not. Passing the root-only set to the rollup
    # collapsed Parts Not Yet Ordered to the job's roots.
    relationship_pairs = relationship_job_part_pairs(current_user, j)
    if relationship_pairs is None:
        allowed_bom = authorised_part_pairs(
            current_user,
            [
                (line.pn, _resolve_visible_rev(line.pn, line.rev))
                for line in (j.bom or [])
            ],
        )
        rollup_pairs = None
    else:
        allowed_bom = {
            (
                str(pn or "").strip().casefold(),
                str(rev or "").strip().casefold(),
            )
            for pn, rev in relationship_pairs
        }
        rollup_pairs = allowed_bom
    orders = _orders_for_job(j)
    visible_bom = [
        line
        for line in (j.bom or [])
        if (
            str(line.pn or "").strip().casefold(),
            _resolve_visible_rev(line.pn, line.rev).casefold(),
        )
        in allowed_bom
    ]
    if supplier_only:
        supplier_lines = {}
        for order in orders:
            if str(order.kind or "").strip().lower() != "purchase":
                continue
            for line in order.lines or []:
                revision = _resolve_visible_rev(line.pn, line.rev)
                key = (
                    str(line.pn or "").strip().casefold(),
                    revision.casefold(),
                )
                if key not in allowed_bom:
                    continue
                existing = supplier_lines.get(key)
                if existing is None:
                    supplier_lines[key] = JobBOMLine(
                        pn=str(line.pn or "").strip(),
                        rev=revision,
                        qty=float(line.qty or 0.0),
                    )
                else:
                    existing.qty = float(existing.qty or 0.0) + float(line.qty or 0.0)
        visible_bom = list(supplier_lines.values())
    bom_text = "\n".join(
        [f"{line.pn},{line.rev},{line.qty:g}" for line in visible_bom]
    )
    can_manage_orders = user_has_permission(current_user, "orders.update")
    rollup = _build_job_bom_rollup(
        j,
        can_manage_orders=can_manage_orders,
        bom_lines=visible_bom,
        user=current_user,
        allowed_pairs=rollup_pairs,
    )
    return render_template(
        "admin/jobs_form.html",
        users=users,
        suppliers=suppliers,
        customers=customers,
        job=j,
        bom_text=bom_text,
        orders=orders,
        ordered_parts=rollup["ordered_parts"],
        remaining_parts=rollup["remaining_parts_flat"],
        remaining_parts_tree=rollup["remaining_parts_tree"],
        oversupplied_parts=rollup["oversupplied_parts"],
        readonly=True,
        hide_participants=is_external,
        hide_vendors=bool(is_external),
        hide_customer=supplier_only,
        mask_supplier_names=bool(is_external and cust_ids),
    )

@bp.post("/<job_id>/delete")
@permissions_required("jobs.archive", "orders.update")
def jobs_delete(job_id):
    try:
        j = authorised_get(
            Job.objects(is_deleted=False),
            current_user,
            job_id,
            resource_type="jobs",
            permission="jobs.archive",
        )
        if not j:
            abort(404)
        related = scope_queryset(
            Order.objects(job=j),
            current_user,
            "orders",
            permission="orders.update",
        )
        if related.count() != Order.objects(job=j).count():
            abort(404)
        related.update(job=None, updated_at=utc_now())
        j.status = "cancelled"
        j.is_deleted = True
        j.updated_at = utc_now()
        j.save()
        flash("Job deleted.", "success")
    except Exception:
        flash("Delete failed.", "error")
    return redirect(url_for("admin_jobs.jobs_list"))


@bp.post("/purge_deleted")
@permissions_required("jobs.archive", "orders.update")
def jobs_purge_deleted():
    q = scope_queryset(
        Job.objects(is_deleted=True),
        current_user,
        "jobs",
        permission="jobs.archive",
    )
    ids = [j.id for j in q.only("id")]
    if not ids:
        flash("No deleted jobs to purge.", "info")
        return redirect(url_for("admin_jobs.jobs_list"))

    related = scope_queryset(
        Order.objects(job__in=ids),
        current_user,
        "orders",
        permission="orders.update",
    )
    if related.count() != Order.objects(job__in=ids).count():
        abort(404)
    related.update(job=None, updated_at=utc_now())

    try:
        deleted = Job.objects(id__in=ids, is_deleted=True).delete()
    except Exception:
        deleted = 0

    flash(f"Purged {int(deleted or 0)} deleted job(s).", "success")
    return redirect(url_for("admin_jobs.jobs_list"))


def _parse_bom_text(text: str):
    lines = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        parts = [x.strip() for x in s.split(",")]
        if len(parts) < 1:
            continue
        pn = _canonical_pn(parts[0])
        rev = clean_rev(parts[1] if len(parts) > 1 else "")
        if not rev:
            part = (
                scope_queryset(Part.objects, current_user, "parts")
                .filter(part_number__iexact=pn)
                .order_by("-updated_at")
                .first()
            )
            rev = clean_rev(getattr(part, "revision", "") if part else "")
        try:
            qty = float(parts[2]) if len(parts) > 2 else 1.0
        except Exception:
            qty = 1.0
        lines.append(JobBOMLine(pn=pn, rev=rev or "", qty=qty))
    return _consolidate_lines(lines)


def _consolidate_lines(lines):
    merged = {}
    for l in lines or []:
        pn_raw = (l.pn or "").strip()
        rev_raw = clean_rev(l.rev)
        key = (pn_raw.lower(), rev_raw)
        if key in merged:
            merged[key]["qty"] += float(l.qty or 0)
        else:
            merged[key] = {"pn": pn_raw, "rev": rev_raw, "qty": float(l.qty or 0)}
    out = []
    for item in merged.values():
        out.append(JobBOMLine(pn=item["pn"], rev=item["rev"], qty=item["qty"]))
    return out


def _canonical_pn(pn: str) -> str:
    pn = (pn or "").strip()
    if not pn:
        return pn
    p = Part.objects(part_number__iexact=pn).only("part_number").first()
    return p.part_number if p else pn


def _parse_date(value: str | None, *, end_of_day: bool = False):
    return parse_user_datetime(value, end_of_day=end_of_day)



@bp.route("/new", methods=["GET","POST"])
@permissions_required("jobs.create")
def jobs_new():
    if request.method == "POST":
        _require_job_form_permissions()
        job_number = (request.form.get("job_number") or "").strip() or generate_job_number()
        desc = (request.form.get("description") or "").strip()
        if Job.objects(job_number=job_number).first():
            flash("Job already exists.", "error")
            return redirect(url_for("admin_jobs.jobs_new"))
        j = Job(
            job_number=job_number,
            title=(request.form.get("title") or "").strip(),
            description=desc,
            status=(request.form.get("status") or "draft").strip(),
            priority=(request.form.get("priority") or "normal").strip(),
            scheduled_start=_parse_date(request.form.get("scheduled_start")),
            scheduled_end=_parse_date(request.form.get("scheduled_end")),
        )
        # participants
        user_ids = request.form.getlist("participants")
        if user_ids:
            j.participants = _filter_job_participants(user_ids)
        # vendors
        supp_ids = request.form.getlist("vendors")
        if supp_ids:
            scoped = scope_queryset(
                Supplier.objects(id__in=supp_ids),
                current_user,
                "suppliers",
                permission="jobs.assign",
            )
            j.vendors = list(scoped)
            if len(j.vendors) != len(set(supp_ids)):
                abort(404)
        # Customer
        cust_id = request.form.get("customer")
        if cust_id:
            try:
                j.customer = authorised_get(
                    Customer.objects,
                    current_user,
                    cust_id,
                    resource_type="customers",
                    permission="jobs.assign",
                )
                if not j.customer:
                    abort(404)
            except Exception:
                j.customer = None

        # BOM lines from textarea
        bom_text = request.form.get("bom_text") or ""
        j.bom = _parse_bom_text(bom_text)
        j.created_at = utc_now()
        j.updated_at = utc_now()
        j.save()
        flash("Job created.", "success")
        return redirect(url_for("admin_jobs.jobs_edit", job_id=str(j.id)))
    users = _eligible_job_users()
    suppliers, customers = _job_form_destinations()
    return render_template("admin/jobs_form.html", users=users, suppliers=suppliers, customers=customers, job=None)


@bp.route("/<job_id>/edit", methods=["GET","POST"])
@permissions_required("jobs.update")
def jobs_edit(job_id):
    j = _scoped_job(job_id, "jobs.update")
    if not j:
        abort(404)
    if request.method == "POST":
        _require_job_form_permissions()
        j.job_number = (request.form.get("job_number") or j.job_number).strip()
        j.title = (request.form.get("title") or "").strip()
        j.description = (request.form.get("description") or "").strip()
        j.status = (request.form.get("status") or j.status or "draft").strip()
        j.priority = (request.form.get("priority") or j.priority or "normal").strip()
        j.scheduled_start = _parse_date(request.form.get("scheduled_start"))
        j.scheduled_end = _parse_date(request.form.get("scheduled_end"))
        if user_has_permission(current_user, "jobs.assign"):
            cust_id = request.form.get("customer")
            j.customer = (
                authorised_get(
                    Customer.objects,
                    current_user,
                    cust_id,
                    resource_type="customers",
                    permission="jobs.assign",
                )
                if cust_id
                else None
            )
            if cust_id and not j.customer:
                abort(404)
            user_ids = request.form.getlist("participants")
            j.participants = _filter_job_participants(user_ids) if user_ids else []
            supp_ids = request.form.getlist("vendors")
            if supp_ids:
                j.vendors = list(
                    scope_queryset(
                        Supplier.objects(id__in=supp_ids),
                        current_user,
                        "suppliers",
                        permission="jobs.assign",
                    )
                )
                if len(j.vendors) != len(set(supp_ids)):
                    abort(404)
            else:
                j.vendors = []
        if user_has_permission(current_user, "jobs.bom.update"):
            bom_text = request.form.get("bom_text") or ""
            j.bom = _parse_bom_text(bom_text)
        j.updated_at = utc_now()
        j.save()
        flash("Job updated.", "success")
        return redirect(url_for("admin_jobs.jobs_edit", job_id=str(j.id)))
    users = _eligible_job_users()
    suppliers, customers = _job_form_destinations()
    # Clean up broken references to avoid deref errors
    try:
        _ = j.customer.id if j.customer else None
    except Exception:
        j.customer = None
    # Recompose bom_text for editing
    allowed_bom = authorised_part_pairs(
        current_user,
        [
            (line.pn, _resolve_visible_rev(line.pn, line.rev))
            for line in (j.bom or [])
        ],
    )
    visible_bom = [
        line
        for line in (j.bom or [])
        if (
            str(line.pn or "").strip().casefold(),
            _resolve_visible_rev(line.pn, line.rev).casefold(),
        )
        in allowed_bom
    ]
    bom_text = "\n".join(
        [f"{line.pn},{line.rev},{line.qty:g}" for line in visible_bom]
    )
    orders = _orders_for_job(j)
    rollup = _build_job_bom_rollup(
        j,
        can_manage_orders=True,
        bom_lines=visible_bom,
        user=current_user,
    )
    return render_template(
        "admin/jobs_form.html",
        users=users,
        suppliers=suppliers,
        customers=customers,
        job=j,
        bom_text=bom_text,
        orders=orders,
        ordered_parts=rollup["ordered_parts"],
        remaining_parts=rollup["remaining_parts_flat"],
        remaining_parts_tree=rollup["remaining_parts_tree"],
        oversupplied_parts=rollup["oversupplied_parts"],
    )


# ---- JSON helpers for interactive BOM editing ----

def _orders_for_job(job: Job):
    try:
        queryset = Order.objects(job=job, status__ne="cancelled")
        if not getattr(current_user, "is_authenticated", False):
            return list(queryset)
        return list(
            scope_queryset(
                queryset,
                current_user,
                "orders",
            )
        )
    except Exception:
        return []

def _job_order_totals(job: Job):
    required_map, _, _ = _job_required_structure(job)
    required_total = float(sum(required_map.values()) if required_map else 0.0)
    required_keys = set(required_map.keys()) if required_map else None

    ordered_map, _, _ = _job_order_coverage(
        job,
        required_keys=required_keys,
        can_manage_orders=False,
        include_links=False,
        use_received=False,
    )
    received_map, _, _ = _job_order_coverage(
        job,
        required_keys=required_keys,
        can_manage_orders=False,
        include_links=False,
        use_received=True,
    )
    ordered_total = float(sum(ordered_map.values()) if ordered_map else 0.0)
    received_total = float(sum(received_map.values()) if received_map else 0.0)

    if required_total == 0.0 and not required_map:
        required_total = ordered_total if ordered_total > 0.0 else 0.0

    return required_total, ordered_total, received_total

def _resolve_rev(pn: str, rev: str | None):
    if not clean_rev(rev):
        p = Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
        if not p:
            return ""
        attrs = harvest_part_attrs(p)
        return clean_rev(attrs.get("revision") or p.revision or "")
    return clean_rev(rev)


def _resolve_visible_rev(pn: str, rev: str | None) -> str:
    rev_clean = clean_rev(rev)
    if rev_clean:
        return rev_clean
    part = (
        scope_queryset(Part.objects, current_user, "parts")
        .filter(part_number__iexact=pn)
        .order_by("-updated_at")
        .first()
    )
    return clean_rev(getattr(part, "revision", "") if part else "")


def _part_meta(pn: str, rev: str, *, user=None):
    resolved_rev = _resolve_rev(pn, rev)
    p = Part.objects(part_number__iexact=pn, revision__iexact=resolved_rev).first()
    desc = ""
    thumb = ""
    if p:
        attrs = harvest_part_attrs(p)
        desc = attrs.get("description") or p.description or ""
        resolved_rev = clean_rev(attrs.get("revision") or p.revision or resolved_rev or "")
        urls = thumb_urls_for(pn, resolved_rev, user=user)
        thumb = urls[0] if urls else ""
    return {"desc": desc, "rev": resolved_rev, "thumb": thumb}

@bp.get("/<job_id>/bom_json")
@permissions_required("jobs.read")
def job_bom_json(job_id):
    j = authorised_get(
        Job.objects(is_deleted=False),
        current_user,
        job_id,
        resource_type="jobs",
    )
    if not j:
        abort(404)
    rows = []
    requested_pairs = [
        (line.pn, _resolve_visible_rev(line.pn, line.rev))
        for line in (j.bom or [])
        if str(line.pn or "").strip()
    ]
    expected_pairs = {
        (
            str(part_number or "").strip().casefold(),
            clean_rev(revision).casefold(),
        )
        for part_number, revision in requested_pairs
    }
    if authorised_part_pairs(current_user, requested_pairs) != expected_pairs:
        abort(403)
    boundary = response_context("jobs", current_user)
    can_manage = user_has_permission(current_user, "jobs.update")
    orders = _orders_for_job(j)
    for line in (j.bom or []):
        pn = line.pn
        stored_rev = (line.rev or "")
        rev = _resolve_visible_rev(pn, stored_rev)
        req = float(line.qty or 0)
        ordered = 0.0
        links = []
        for o in orders:
            if (o.status or "") == "draft" or not supplies_job_requirement(o):
                continue
            qty_in_o = 0.0
            for l in (o.lines or []):
                l_rev = _resolve_visible_rev(l.pn or "", l.rev or "")
                if (l.pn or "").strip().lower() == pn.lower() and l_rev == rev:
                    qty_in_o += float(l.qty or 0)
            if qty_in_o > 0:
                ordered += qty_in_o
                links.append(
                    filter_response_fields(
                        "order_reference",
                        current_user,
                        {
                            "order_number": o.order_number,
                            "href": url_for(
                                "admin_orders.orders_edit",
                                order_id=str(o.id),
                            ),
                        },
                        context={
                            "policy_context": response_context(
                                "orders",
                                current_user,
                            ),
                            "surface": "embedded",
                        },
                    )
                )
        rows.append(
            filter_response_fields(
                "job_bom_admin_line",
                current_user,
                {
                    "pn": pn,
                    "rev": rev,
                    "line_rev": stored_rev,
                    "qty": req,
                    "ordered_qty": ordered,
                    "remaining_qty": max(req - ordered, 0.0),
                    "orders": links,
                    "can_manage": can_manage,
                },
                context={"policy_context": boundary, "surface": "embedded"},
            )
        )
    return jsonify(rows)

@bp.post("/<job_id>/bom_update")
@permissions_required("jobs.bom.update")
def job_bom_update(job_id):
    j = _scoped_job(job_id, "jobs.bom.update") or abort(404)
    data = request.get_json(silent=True) or {}
    if set(data) - {"pn", "rev", "line_rev", "qty"}:
        abort(400)
    pn = _canonical_pn(data.get("pn") or "")
    rev = clean_rev(data.get("line_rev") if "line_rev" in data else data.get("rev") or "")
    try:
        qty = float(data.get("qty") or 1.0)
    except Exception:
        qty = 1.0
    if not pn:
        return jsonify({"error":"missing pn"}), 400
    if not authorise_part_access(current_user, pn, rev).allowed:
        abort(404)
    updated = False
    if j.bom is None:
        j.bom = []
    for line in j.bom:
        if line.pn.lower() == pn.lower() and clean_rev(line.rev) == rev:
            line.qty = qty; updated = True; break
    if not updated:
        j.bom.append(JobBOMLine(pn=pn, rev=rev or "", qty=qty))
    j.save()
    return jsonify({"ok": True})

@bp.post("/<job_id>/bom_remove")
@permissions_required("jobs.bom.update")
def job_bom_remove(job_id):
    j = _scoped_job(job_id, "jobs.bom.update") or abort(404)
    data = request.get_json(silent=True) or {}
    if set(data) - {"pn", "rev", "line_rev"}:
        abort(400)
    pn = (data.get("pn") or "").strip()
    rev = clean_rev(data.get("line_rev") if "line_rev" in data else data.get("rev") or "")
    before = len(j.bom or [])
    j.bom = [l for l in (j.bom or []) if not (l.pn.lower() == pn.lower() and clean_rev(l.rev) == rev)]
    if len(j.bom) != before:
        j.save()
    return jsonify({"ok": True, "removed": before - len(j.bom)})

@bp.post("/<job_id>/bom_replace")
@permissions_required("jobs.bom.update")
def job_bom_replace(job_id):
    j = _scoped_job(job_id, "jobs.bom.update") or abort(404)
    d = request.get_json(silent=True) or {}
    if set(d) - {"old_pn", "old_rev", "new_pn", "new_rev"}:
        abort(400)
    opn = (d.get("old_pn") or "").strip(); orev = clean_rev(d.get("old_rev") or "")
    npn = _canonical_pn(d.get("new_pn") or ""); nrev = clean_rev(d.get("new_rev") or "")
    if not npn:
        return jsonify({"error":"missing new_pn"}), 400
    if not authorise_part_access(current_user, npn, nrev).allowed:
        abort(404)
    for line in (j.bom or []):
        if line.pn.lower() == opn.lower() and clean_rev(line.rev) == orev:
            line.pn = npn; line.rev = nrev or ""; j.save(); return jsonify({"ok": True})
    return jsonify({"ok": False, "error":"not found"}), 404

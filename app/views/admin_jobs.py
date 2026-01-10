from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from datetime import datetime, timedelta
from flask_security import roles_required
from app.services.acl import permissions_required
from mongoengine.errors import DoesNotExist, ValidationError
from mongoengine.queryset.visitor import Q

from app.models.job import Job, JobBOMLine, JobStage
from app.models.supplier import Supplier
from app.models.customer import Customer
from app.models.auth import User
from app.models.order import Order
from app.models.part import Part
from app.services.attrs import harvest_part_attrs
from app.services.thumbs import thumb_urls_for
from app.services.biz_utils import generate_job_number

bp = Blueprint("admin_jobs", __name__, url_prefix="/admin/jobs")


@bp.get("/")
@permissions_required("jobs.view")
def jobs_list():
    q = Job.objects(is_deleted=False)
    status = (request.args.get("status") or "").strip()
    if status:
        q = q.filter(status=status)
    priority = (request.args.get("priority") or "").strip()
    if priority:
        q = q.filter(priority=priority)
    job_q = (request.args.get("job_q") or "").strip()
    title_q = (request.args.get("title_q") or "").strip()
    part_q = (request.args.get("part_q") or "").strip()
    customer_q = (request.args.get("customer_q") or "").strip()
    legacy_q = (request.args.get("q") or "").strip()
    if legacy_q and not (job_q or title_q or part_q or customer_q):
        job_q = legacy_q
        title_q = legacy_q
        part_q = legacy_q
        customer_q = legacy_q
    if job_q:
        q = q.filter(job_number__icontains=job_q)
    if title_q:
        q = q.filter(Q(title__icontains=title_q) | Q(description__icontains=title_q))
    if part_q:
        q = q.filter(Q(part_number__icontains=part_q) | Q(part_revision__icontains=part_q))
    if customer_q:
        custs = Customer.objects(Q(name__icontains=customer_q) | Q(code__icontains=customer_q))
        if custs:
            q = q.filter(customer__in=list(custs))
    date_from = _parse_date(request.args.get("from"))
    date_to = _parse_date(request.args.get("to"))
    if date_from:
        q = q.filter(scheduled_start__gte=date_from)
    if date_to:
        q = q.filter(scheduled_end__lte=date_to)

    jobs = q.order_by("job_number")
    safe_jobs = []
    for j in jobs:
        try:
            cust_name = j.customer.name if j.customer else "-"
        except Exception:
            cust_name = "-"
        try:
            vendors = ", ".join([v.name for v in (j.vendors or [])])
        except Exception:
            vendors = "-"
        try:
            parts = ", ".join([u.email for u in (j.participants or [])])
        except Exception:
            parts = "-"
        safe_jobs.append(
            {
                "id": j.id,
                "job_number": j.job_number,
                "title": j.title,
                "description": j.description,
                "part_number": j.part_number,
                "part_revision": j.part_revision,
                "status": j.status,
                "priority": j.priority,
                "scheduled_start": j.scheduled_start,
                "scheduled_end": j.scheduled_end,
                "qty_ordered": j.qty_ordered or 0.0,
                "qty_produced": j.qty_produced or 0.0,
                "customer_name": cust_name or "-",
                "participants": parts or "-",
                "vendors": vendors or "-",
            }
        )
    now = datetime.utcnow()
    active_count = Job.objects(status__in=["released", "in_progress"], is_deleted=False).count()
    overdue_count = Job.objects(status__in=["released", "in_progress"], scheduled_end__lt=now, is_deleted=False).count()
    completed_week = Job.objects(status="completed", actual_end__gte=now - timedelta(days=7), is_deleted=False).count()
    return render_template(
        "admin/jobs_list.html",
        jobs=safe_jobs,
        active_count=active_count,
        overdue_count=overdue_count,
        completed_week=completed_week,
        filters={
            "status": status,
            "priority": priority,
            "job_q": job_q,
            "title_q": title_q,
            "part_q": part_q,
            "customer_q": customer_q,
            "from": request.args.get("from") or "",
            "to": request.args.get("to") or "",
        },
    )

@bp.post("/<job_id>/delete")
@permissions_required("jobs.manage")
def jobs_delete(job_id):
    try:
        j = Job.objects.get(id=job_id)
        if j.status in ("in_progress", "completed"):
            flash("Job cannot be deleted in this status.", "error")
        else:
            j.status = "cancelled"
            j.is_deleted = True
            j.updated_at = datetime.utcnow()
            j.save()
            flash("Job cancelled.", "success")
    except Exception:
        flash("Delete failed.", "error")
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
        pn = parts[0]
        rev = parts[1] if len(parts) > 1 else ""
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
        rev_raw = (l.rev or "").strip()
        key = (pn_raw.lower(), rev_raw)
        if key in merged:
            merged[key]["qty"] += float(l.qty or 0)
        else:
            merged[key] = {"pn": pn_raw, "rev": rev_raw, "qty": float(l.qty or 0)}
    out = []
    for item in merged.values():
        out.append(JobBOMLine(pn=item["pn"], rev=item["rev"], qty=item["qty"]))
    return out


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _parse_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _parse_stages_text(text: str):
    stages = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        parts = [x.strip() for x in s.split(",")]
        if len(parts) < 2:
            continue
        try:
            seq = int(parts[0])
        except Exception:
            seq = len(stages) + 1
        name = parts[1]
        status = parts[2] if len(parts) > 2 else "pending"
        assigned = parts[3] if len(parts) > 3 else ""
        dept = parts[4] if len(parts) > 4 else ""
        est = _parse_float(parts[5], None) if len(parts) > 5 else None
        act = _parse_float(parts[6], None) if len(parts) > 6 else None
        stages.append(JobStage(
            name=name,
            sequence=seq,
            status=status or "pending",
            assigned_to=assigned,
            department=dept,
            estimated_hours=est,
            actual_hours=act,
        ))
    stages.sort(key=lambda s: s.sequence or 0)
    return stages


def _stages_to_text(stages):
    lines = []
    for s in stages or []:
        lines.append(",".join([
            str(s.sequence or 1),
            s.name or "",
            s.status or "",
            s.assigned_to or "",
            s.department or "",
            "" if s.estimated_hours is None else str(s.estimated_hours),
            "" if s.actual_hours is None else str(s.actual_hours),
        ]))
    return "\n".join(lines)


@bp.route("/new", methods=["GET","POST"])
@permissions_required("jobs.manage")
def jobs_new():
    if request.method == "POST":
        job_number = (request.form.get("job_number") or "").strip() or generate_job_number()
        desc = (request.form.get("description") or "").strip()
        if Job.objects(job_number=job_number).first():
            flash("Job already exists.", "error")
            return redirect(url_for("admin_jobs.jobs_new"))
        j = Job(
            job_number=job_number,
            title=(request.form.get("title") or "").strip(),
            description=desc,
            part_number=(request.form.get("part_number") or "").strip(),
            part_revision=(request.form.get("part_revision") or "").strip(),
            qty_ordered=_parse_float(request.form.get("qty_ordered"), 0.0),
            qty_produced=_parse_float(request.form.get("qty_produced"), 0.0),
            qty_scrapped=_parse_float(request.form.get("qty_scrapped"), 0.0),
            status=(request.form.get("status") or "draft").strip(),
            priority=(request.form.get("priority") or "normal").strip(),
            scheduled_start=_parse_date(request.form.get("scheduled_start")),
            scheduled_end=_parse_date(request.form.get("scheduled_end")),
            order_number=(request.form.get("order_number") or "").strip(),
            material_reserved=True if request.form.get("material_reserved") == "on" else False,
            estimated_hours=_parse_float(request.form.get("estimated_hours"), None),
            actual_hours=_parse_float(request.form.get("actual_hours"), None),
        )
        # participants
        user_ids = request.form.getlist("participants")
        if user_ids:
            j.participants = list(User.objects(id__in=user_ids))
        # vendors
        supp_ids = request.form.getlist("vendors")
        if supp_ids:
            j.vendors = list(Supplier.objects(id__in=supp_ids))
        # Customer
        cust_id = request.form.get("customer")
        if cust_id:
            try:
                j.customer = Customer.objects.get(id=cust_id)
            except Exception:
                j.customer = None

        # BOM lines from textarea
        bom_text = request.form.get("bom_text") or ""
        j.bom = _parse_bom_text(bom_text)
        stages_text = request.form.get("stages_text") or ""
        j.stages = _parse_stages_text(stages_text)
        j.created_at = datetime.utcnow()
        j.updated_at = datetime.utcnow()
        j.save()
        flash("Job created.", "success")
        return redirect(url_for("admin_jobs.jobs_edit", job_id=str(j.id)))
    users = User.objects().order_by("email")
    suppliers = Supplier.objects().order_by("name")
    customers = Customer.objects().order_by("name")
    return render_template("admin/jobs_form.html", users=users, suppliers=suppliers, customers=customers, job=None)


@bp.route("/<job_id>/edit", methods=["GET","POST"])
@permissions_required("jobs.manage")
def jobs_edit(job_id):
    try:
        j = Job.objects.get(id=job_id)
    except (DoesNotExist, ValidationError):
        abort(404)
    if request.method == "POST":
        j.job_number = (request.form.get("job_number") or j.job_number).strip()
        j.title = (request.form.get("title") or "").strip()
        j.description = (request.form.get("description") or "").strip()
        j.part_number = (request.form.get("part_number") or "").strip()
        j.part_revision = (request.form.get("part_revision") or "").strip()
        j.qty_ordered = _parse_float(request.form.get("qty_ordered"), 0.0)
        j.qty_produced = _parse_float(request.form.get("qty_produced"), 0.0)
        j.qty_scrapped = _parse_float(request.form.get("qty_scrapped"), 0.0)
        j.status = (request.form.get("status") or j.status or "draft").strip()
        j.priority = (request.form.get("priority") or j.priority or "normal").strip()
        j.scheduled_start = _parse_date(request.form.get("scheduled_start"))
        j.scheduled_end = _parse_date(request.form.get("scheduled_end"))
        j.order_number = (request.form.get("order_number") or "").strip()
        j.material_reserved = True if request.form.get("material_reserved") == "on" else False
        j.estimated_hours = _parse_float(request.form.get("estimated_hours"), None)
        j.actual_hours = _parse_float(request.form.get("actual_hours"), None)
        cust_id = request.form.get("customer")
        j.customer = Customer.objects(id=cust_id).first() if cust_id else None
        user_ids = request.form.getlist("participants")
        j.participants = list(User.objects(id__in=user_ids)) if user_ids else []
        supp_ids = request.form.getlist("vendors")
        j.vendors = list(Supplier.objects(id__in=supp_ids)) if supp_ids else []
        bom_text = request.form.get("bom_text") or ""
        j.bom = _parse_bom_text(bom_text)
        stages_text = request.form.get("stages_text") or ""
        j.stages = _parse_stages_text(stages_text)
        j.updated_at = datetime.utcnow()
        j.save()
        flash("Job updated.", "success")
        return redirect(url_for("admin_jobs.jobs_edit", job_id=str(j.id)))
    users = User.objects().order_by("email")
    suppliers = Supplier.objects().order_by("name")
    customers = Customer.objects().order_by("name")
    # Clean up broken references to avoid deref errors
    try:
        _ = j.customer.id if j.customer else None
    except Exception:
        j.customer = None
    # Recompose bom_text for editing
    bom_text = "\n".join([f"{l.pn},{l.rev},{l.qty:g}" for l in (j.bom or [])])
    stages_text = _stages_to_text(j.stages or [])
    orders = _orders_for_job(j)
    # aggregate ordered parts
    ordered_map = {}
    order_links = {}
    for o in orders:
        for l in (o.lines or []):
            rev_key = _resolve_rev(l.pn or "", l.rev or "")
            pn_key = (l.pn or "").strip()
            key = (pn_key.lower(), (rev_key or "").lower())
            ordered_map[key] = ordered_map.get(key, 0.0) + float(l.qty or 0)
            order_links.setdefault(key, []).append({
                "order_number": o.order_number,
                "href": url_for("admin_orders.orders_edit", order_id=str(o.id)),
                "supplier": getattr(o.supplier, "name", ""),
            })
    ordered_parts = []
    remaining_parts = []
    for line in (j.bom or []):
        resolved_rev = _resolve_rev(line.pn or "", line.rev or "")
        pn_key = (line.pn or "").strip()
        key = (pn_key.lower(), (resolved_rev or "").lower())
        req = float(line.qty or 0)
        ordered = ordered_map.get(key, 0.0)
        rem = max(req - ordered, 0.0)
        meta = _part_meta(line.pn, line.rev or "")
        row = {
            "pn": line.pn,
            "rev": meta.get("rev") or (line.rev or ""),
            "required": req,
            "ordered": ordered,
            "remaining": rem,
            "desc": meta.get("desc") or "",
            "thumb": meta.get("thumb") or "",
            "orders": order_links.get(key, []),
        }
        if ordered > 0:
            ordered_parts.append(row)
        if rem > 0:
            remaining_parts.append(row)
    return render_template(
        "admin/jobs_form.html",
        users=users,
        suppliers=suppliers,
        customers=customers,
        job=j,
        bom_text=bom_text,
        stages_text=stages_text,
        orders=orders,
        ordered_parts=ordered_parts,
        remaining_parts=remaining_parts,
    )


# ---- JSON helpers for interactive BOM editing ----

def _orders_for_job(job: Job):
    try:
        return list(Order.objects(job=job))
    except Exception:
        return []

def _resolve_rev(pn: str, rev: str):
    rev = (rev or "").strip()
    if rev:
        return rev
    p = Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
    if not p:
        return ""
    attrs = harvest_part_attrs(p)
    return (attrs.get("revision") or p.revision or "").strip()


def _part_meta(pn: str, rev: str):
    resolved_rev = _resolve_rev(pn, rev)
    p = Part.objects(part_number__iexact=pn, revision__iexact=resolved_rev).first() \
        or Part.objects(part_number__iexact=pn).order_by("-updated_at").first()
    desc = ""
    thumb = ""
    if p:
        attrs = harvest_part_attrs(p)
        desc = attrs.get("description") or p.description or ""
        resolved_rev = (attrs.get("revision") or p.revision or resolved_rev or "").strip()
        urls = thumb_urls_for(pn, resolved_rev or None)
        thumb = urls[0] if urls else ""
    return {"desc": desc, "rev": resolved_rev, "thumb": thumb}

@bp.get("/<job_id>/bom_json")
@permissions_required("jobs.view")
def job_bom_json(job_id):
    try:
        j = Job.objects.get(id=job_id)
    except (DoesNotExist, ValidationError):
        abort(404)
    rows = []
    orders = _orders_for_job(j)
    for line in (j.bom or []):
        pn = line.pn
        rev = _resolve_rev(pn, line.rev or "")
        req = float(line.qty or 0)
        ordered = 0.0
        links = []
        for o in orders:
            qty_in_o = 0.0
            for l in (o.lines or []):
                l_rev = _resolve_rev(l.pn or "", l.rev or "")
                if (l.pn or "").strip().lower() == pn.lower() and l_rev == rev:
                    qty_in_o += float(l.qty or 0)
            if qty_in_o > 0:
                ordered += qty_in_o
                links.append({"order_number": o.order_number, "href": url_for("admin_orders.orders_edit", order_id=str(o.id))})
        rows.append({
            "pn": pn, "rev": rev, "qty": req,
            "ordered_qty": ordered,
            "remaining_qty": max(req - ordered, 0.0),
            "orders": links,
        })
    return jsonify(rows)

@bp.post("/<job_id>/bom_update")
@permissions_required("jobs.manage")
def job_bom_update(job_id):
    j = Job.objects(id=job_id).first() or abort(404)
    data = request.get_json(silent=True) or {}
    pn = (data.get("pn") or "").strip(); rev = (data.get("rev") or "")
    try:
        qty = float(data.get("qty") or 1.0)
    except Exception:
        qty = 1.0
    if not pn:
        return jsonify({"error":"missing pn"}), 400
    updated = False
    if j.bom is None:
        j.bom = []
    for line in j.bom:
        if line.pn.lower() == pn.lower() and (line.rev or "") == rev:
            line.qty = qty; updated = True; break
    if not updated:
        j.bom.append(JobBOMLine(pn=pn, rev=rev or "", qty=qty))
    j.save()
    return jsonify({"ok": True})

@bp.post("/<job_id>/bom_remove")
@permissions_required("jobs.manage")
def job_bom_remove(job_id):
    j = Job.objects(id=job_id).first() or abort(404)
    data = request.get_json(silent=True) or {}
    pn = (data.get("pn") or "").strip(); rev = (data.get("rev") or "")
    before = len(j.bom or [])
    j.bom = [l for l in (j.bom or []) if not (l.pn.lower() == pn.lower() and (l.rev or "") == rev)]
    if len(j.bom) != before:
        j.save()
    return jsonify({"ok": True, "removed": before - len(j.bom)})

@bp.post("/<job_id>/bom_replace")
@permissions_required("jobs.manage")
def job_bom_replace(job_id):
    j = Job.objects(id=job_id).first() or abort(404)
    d = request.get_json(silent=True) or {}
    opn = (d.get("old_pn") or "").strip(); orev = (d.get("old_rev") or "")
    npn = (d.get("new_pn") or "").strip(); nrev = (d.get("new_rev") or "")
    if not npn:
        return jsonify({"error":"missing new_pn"}), 400
    for line in (j.bom or []):
        if line.pn.lower() == opn.lower() and (line.rev or "") == orev:
            line.pn = npn; line.rev = nrev or ""; j.save(); return jsonify({"ok": True})
    return jsonify({"ok": False, "error":"not found"}), 404

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_security import roles_required
from app.services.acl import permissions_required
from mongoengine.errors import DoesNotExist, ValidationError

from app.models.job import Job, JobBOMLine
from app.models.supplier import Supplier
from app.models.customer import Customer
from app.models.auth import User
from app.models.order import Order
from app.models.part import Part
from app.services.attrs import harvest_part_attrs

bp = Blueprint("admin_jobs", __name__, url_prefix="/admin/jobs")


@bp.get("/")
@permissions_required("jobs.view")
def jobs_list():
    jobs = Job.objects().order_by("job_number")
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
                "description": j.description,
                "customer_name": cust_name or "-",
                "participants": parts or "-",
                "vendors": vendors or "-",
            }
        )
    return render_template("admin/jobs_list.html", jobs=safe_jobs)

@bp.post("/<job_id>/delete")
@permissions_required("jobs.manage")
def jobs_delete(job_id):
    try:
        j = Job.objects.get(id=job_id)
        j.delete()
        flash("Job deleted.", "success")
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
        key = ((l.pn or "").strip().lower(), (l.rev or "").strip())
        merged.setdefault(key, 0.0)
        merged[key] += float(l.qty or 0)
    out = []
    for (pn, rev), qty in merged.items():
        out.append(JobBOMLine(pn=pn, rev=rev, qty=qty))
    return out


@bp.route("/new", methods=["GET","POST"])
@permissions_required("jobs.manage")
def jobs_new():
    if request.method == "POST":
        job_number = (request.form.get("job_number") or "").strip()
        desc = (request.form.get("description") or "").strip()
        if not job_number:
            flash("Job number is required.", "error")
            return redirect(url_for("admin_jobs.jobs_new"))
        if Job.objects(job_number=job_number).first():
            flash("Job already exists.", "error")
            return redirect(url_for("admin_jobs.jobs_new"))
        j = Job(job_number=job_number, description=desc)
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
        j.description = (request.form.get("description") or "").strip()
        cust_id = request.form.get("customer")
        j.customer = Customer.objects(id=cust_id).first() if cust_id else None
        user_ids = request.form.getlist("participants")
        j.participants = list(User.objects(id__in=user_ids)) if user_ids else []
        supp_ids = request.form.getlist("vendors")
        j.vendors = list(Supplier.objects(id__in=supp_ids)) if supp_ids else []
        bom_text = request.form.get("bom_text") or ""
        j.bom = _parse_bom_text(bom_text)
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
    orders = _orders_for_job(j)
    # aggregate ordered parts
    ordered_map = {}
    order_links = {}
    for o in orders:
        for l in (o.lines or []):
            key = (l.pn or "", l.rev or "")
            ordered_map[key] = ordered_map.get(key, 0.0) + float(l.qty or 0)
            order_links.setdefault(key, []).append({
                "order_number": o.order_number,
                "href": url_for("admin_orders.orders_edit", order_id=str(o.id)),
                "supplier": getattr(o.supplier, "name", ""),
            })
    ordered_parts = []
    remaining_parts = []
    for line in (j.bom or []):
        key = (line.pn or "", line.rev or "")
        req = float(line.qty or 0)
        ordered = ordered_map.get(key, 0.0)
        rem = max(req - ordered, 0.0)
        desc = _part_meta(line.pn, line.rev or "")
        row = {"pn": line.pn, "rev": line.rev or "", "required": req, "ordered": ordered, "remaining": rem, "desc": desc, "orders": order_links.get(key, [])}
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

def _part_meta(pn: str, rev: str):
    p = Part.objects(part_number=pn, revision=rev or "").first() or Part.objects(part_number=pn).order_by("-updated_at").first()
    desc = ""
    if p:
        attrs = harvest_part_attrs(p)
        desc = attrs.get("description") or p.description or ""
    return desc

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
        pn = line.pn; rev = line.rev or ""; req = float(line.qty or 0)
        ordered = 0.0
        links = []
        for o in orders:
            qty_in_o = 0.0
            for l in (o.lines or []):
                if (l.pn or "").strip().lower() == pn.lower() and (l.rev or "") == rev:
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

import json
import io

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, send_file
from flask_login import current_user
from datetime import datetime
from flask_security import roles_required
from app.services.acl import permissions_required, apply_order_scope, apply_job_scope
from mongoengine.errors import DoesNotExist, ValidationError
from mongoengine.queryset.visitor import Q

from app.models.order import Order, OrderLine
from app.models.job import Job
from app.models.supplier import Supplier
from app.models.customer import Customer
from app.models.part import Part
from app.services.biz_utils import generate_order_number, calculate_order_totals, consolidate_order_lines
from app.services.order_scope import build_scope_pdf, build_scope_zip

bp = Blueprint("admin_orders", __name__, url_prefix="/admin/orders")


@bp.get("/")
@permissions_required("orders.view")
def orders_list():
    job_id = (request.args.get('job') or '').strip()
    qs = Order.objects()
    if job_id:
        try:
            j = apply_job_scope(Job.objects(id=job_id), current_user).first()
            if not j:
                qs = qs.filter(id__in=[])
            else:
                qs = qs.filter(job=j)
        except Exception:
            qs = qs.filter(id__in=[])
    status = (request.args.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    kind = (request.args.get("type") or "").strip()
    if kind:
        qs = qs.filter(kind=kind)
    order_q = (request.args.get("order_q") or request.args.get("q") or "").strip()
    if order_q:
        qs = qs.filter(Q(order_number__icontains=order_q) | Q(description__icontains=order_q))
    job_q = (request.args.get("job_q") or "").strip()
    if job_q:
        jobs = Job.objects(Q(job_number__icontains=job_q) | Q(title__icontains=job_q))
        if jobs:
            qs = qs.filter(job__in=list(jobs))
        else:
            qs = qs.filter(id__in=[])
    supplier_q = (request.args.get("supplier_q") or "").strip()
    if supplier_q:
        sups = Supplier.objects(Q(name__icontains=supplier_q) | Q(code__icontains=supplier_q))
        if sups:
            qs = qs.filter(supplier__in=list(sups))
        else:
            qs = qs.filter(id__in=[])
    customer_q = (request.args.get("customer_q") or "").strip()
    if customer_q:
        custs = Customer.objects(Q(name__icontains=customer_q) | Q(code__icontains=customer_q))
        if custs:
            qs = qs.filter(customer__in=list(custs))
        else:
            qs = qs.filter(id__in=[])
    date_from = _parse_date(request.args.get("from"))
    if date_from:
        qs = qs.filter(order_date__gte=date_from)
    date_to = _parse_date(request.args.get("to"))
    if date_to:
        qs = qs.filter(order_date__lte=date_to)
    total_min = request.args.get("total_min")
    total_max = request.args.get("total_max")
    try:
        if total_min not in (None, ""):
            qs = qs.filter(total__gte=float(total_min))
    except Exception:
        pass
    try:
        if total_max not in (None, ""):
            qs = qs.filter(total__lte=float(total_max))
    except Exception:
        pass
    qs = apply_order_scope(qs, current_user)
    orders = qs.order_by("-created_at")
    safe_orders = []
    for o in orders:
        try:
            job_number = o.job.job_number if o.job else "-"
            job_id = str(o.job.id) if o.job else ""
        except Exception:
            job_number = "-"
            job_id = ""
        try:
            supplier_name = o.supplier.name if o.supplier else "-"
            supplier_id = str(o.supplier.id) if o.supplier else ""
        except Exception:
            supplier_name = "-"
            supplier_id = ""
        try:
            customer_name = o.customer.name if o.customer else "-"
            customer_id = str(o.customer.id) if o.customer else ""
        except Exception:
            customer_name = "-"
            customer_id = ""
        safe_orders.append(
            {
                "id": o.id,
                "order_number": o.order_number,
                "kind": o.kind,
                "job": job_number,
                "job_id": job_id,
                "supplier": supplier_name,
                "supplier_id": supplier_id,
                "customer": customer_name,
                "customer_id": customer_id,
                "status": o.status,
                "order_date": o.order_date,
                "total": o.total,
            }
        )
    return render_template(
        "admin/orders_list.html",
        orders=safe_orders,
        filters={
            "status": status,
            "type": kind,
            "order_q": order_q,
            "job_q": job_q,
            "supplier_q": supplier_q,
            "customer_q": customer_q,
            "from": request.args.get("from") or "",
            "to": request.args.get("to") or "",
            "total_min": request.args.get("total_min") or "",
            "total_max": request.args.get("total_max") or "",
        },
    )

@bp.post("/<order_id>/delete")
@permissions_required("orders.manage")
def orders_delete(order_id):
    try:
        o = Order.objects.get(id=order_id)
        o.delete()
        flash("Order deleted.", "success")
    except Exception:
        flash("Delete failed.", "error")
    return redirect(url_for("admin_orders.orders_list"))


@bp.post("/<order_id>/scope_pdf")
@permissions_required("orders.view")
def order_scope_pdf(order_id):
    order = apply_order_scope(Order.objects(id=order_id), current_user).first()
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin_orders.orders_list"))

    attach_docs = (request.form.get("attach_docs") or "").lower() in ("1", "true", "yes", "on")
    pdf_bytes = build_scope_pdf(order)
    if attach_docs:
        zip_bytes = build_scope_zip(order, pdf_bytes, attach_docs=True)
        return send_file(
            io.BytesIO(zip_bytes),
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{order.order_number}_scope.zip",
        )
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{order.order_number}_scope.pdf",
    )


def _parse_lines(text: str):
    out = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"): continue
        parts = [x.strip() for x in s.split(",")]
        pn = _canonical_pn(parts[0] if parts else "")
        rev = parts[1] if len(parts) > 1 else ""
        qty = 1.0
        if len(parts) > 2:
            try:
                qty = float(parts[2])
            except Exception:
                qty = 1.0
        uom = parts[3] if len(parts) > 3 else "EA"
        note = parts[4] if len(parts) > 4 else ""
        unit_price = 0.0
        discount_pct = 0.0
        tax_pct = 0.0
        if len(parts) > 5:
            try:
                unit_price = float(parts[5])
            except Exception:
                unit_price = 0.0
        if len(parts) > 6:
            try:
                discount_pct = float(parts[6])
            except Exception:
                discount_pct = 0.0
        if len(parts) > 7:
            try:
                tax_pct = float(parts[7])
            except Exception:
                tax_pct = 0.0
        if pn:
            out.append(OrderLine(
                pn=pn,
                rev=rev or "",
                qty=qty,
                uom=uom,
                note=note,
                unit_price=unit_price,
                discount_pct=discount_pct,
                tax_pct=tax_pct,
            ))
    return consolidate_order_lines(out)


def _canonical_pn(pn: str) -> str:
    pn = (pn or "").strip()
    if not pn:
        return pn
    p = Part.objects(part_number__iexact=pn).only("part_number").first()
    return p.part_number if p else pn


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


@bp.route("/new", methods=["GET","POST"])
@permissions_required("orders.manage")
def orders_new():
    if request.method == "POST":
        num = (request.form.get("order_number") or "").strip() or generate_order_number(request.form.get("kind") or "purchase")
        if Order.objects(order_number=num).first():
            flash("Order already exists.", "error"); return redirect(url_for("admin_orders.orders_new"))
        o = Order(order_number=num)
        o.description = (request.form.get("description") or "").strip()
        o.kind = (request.form.get("kind") or "purchase").strip()
        o.status = (request.form.get("status") or "draft").strip()
        o.customer_po = (request.form.get("customer_po") or "").strip()
        o.shipping_method = (request.form.get("shipping_method") or "").strip()
        o.carrier = (request.form.get("carrier") or "").strip()
        o.tracking_number = (request.form.get("tracking_number") or "").strip()
        o.order_date = _parse_date(request.form.get("order_date")) or datetime.utcnow()
        o.requested_delivery = _parse_date(request.form.get("requested_delivery"))
        o.promised_delivery = _parse_date(request.form.get("promised_delivery"))
        o.shipping_cost = float(request.form.get("shipping_cost") or 0.0)
        o.currency = (request.form.get("currency") or "USD").strip()
        job_id = request.form.get("job")
        supp_id = request.form.get("supplier")
        cust_id = request.form.get("customer")
        if job_id:
            o.job = Job.objects(id=job_id).first()
        if supp_id: o.supplier = Supplier.objects(id=supp_id).first()
        if cust_id: o.customer = Customer.objects(id=cust_id).first()
        if o.job and o.job.customer:
            o.customer = o.job.customer
        o.lines = _parse_lines(request.form.get("lines") or "")
        subtotal, tax_total, discount_total = calculate_order_totals(o.lines)
        o.subtotal = subtotal
        o.tax_amount = tax_total
        o.discount_amount = discount_total
        o.total = max(subtotal - discount_total + tax_total + float(o.shipping_cost or 0.0), 0.0)
        o.updated_at = datetime.utcnow()
        o.save()
        flash("Order created.", "success")
        return redirect(url_for("admin_orders.orders_edit", order_id=o.id))
    jobs_raw = Job.objects().order_by("job_number")
    jobs = []
    for j in jobs_raw:
        try:
            cust_id = str(j.customer.id) if j.customer else ""
        except Exception:
            cust_id = ""
        jobs.append({"id": j.id, "job_number": j.job_number, "customer_id": cust_id})
    sups = Supplier.objects().order_by("name")
    custs = Customer.objects().order_by("name")
    prefill_job = request.args.get("job") or ""
    prefill_customer = ""
    if prefill_job:
        job = Job.objects(id=prefill_job).first()
        if job and job.customer:
            prefill_customer = str(job.customer.id)
    return render_template(
        "admin/orders_form.html",
        order=None,
        jobs=jobs,
        suppliers=sups,
        customers=custs,
        prefill_job=prefill_job,
        prefill_customer=prefill_customer,
    )


@bp.route("/<order_id>/edit", methods=["GET","POST"])
@permissions_required("orders.manage")
def orders_edit(order_id):
    try:
        o = Order.objects.get(id=order_id)
    except (DoesNotExist, ValidationError):
        abort(404)
    # Guard broken references to avoid deref crashes
    for attr in ("job", "supplier", "customer"):
        try:
            _ = getattr(o, attr).id if getattr(o, attr) else None
        except Exception:
            setattr(o, attr, None)
    if o.lines:
        merged = consolidate_order_lines(o.lines)
        if len(merged) != len(o.lines):
            o.lines = merged
            subtotal, tax_total, discount_total = calculate_order_totals(o.lines)
            o.subtotal = subtotal
            o.tax_amount = tax_total
            o.discount_amount = discount_total
            o.total = max(subtotal - discount_total + tax_total + float(o.shipping_cost or 0.0), 0.0)
            o.updated_at = datetime.utcnow()
            o.save()
    if request.method == "POST":
        o.order_number = (request.form.get("order_number") or o.order_number).strip()
        o.description = (request.form.get("description") or "").strip()
        o.kind = (request.form.get("kind") or o.kind).strip()
        o.status = (request.form.get("status") or o.status or "draft").strip()
        o.customer_po = (request.form.get("customer_po") or "").strip()
        o.shipping_method = (request.form.get("shipping_method") or "").strip()
        o.carrier = (request.form.get("carrier") or "").strip()
        o.tracking_number = (request.form.get("tracking_number") or "").strip()
        o.order_date = _parse_date(request.form.get("order_date")) or o.order_date
        o.requested_delivery = _parse_date(request.form.get("requested_delivery"))
        o.promised_delivery = _parse_date(request.form.get("promised_delivery"))
        o.shipping_cost = float(request.form.get("shipping_cost") or 0.0)
        o.currency = (request.form.get("currency") or "USD").strip()
        job_id = request.form.get("job")
        supp_id = request.form.get("supplier")
        cust_id = request.form.get("customer")
        o.job = Job.objects(id=job_id).first() if job_id else None
        o.supplier = Supplier.objects(id=supp_id).first() if supp_id else None
        o.customer = Customer.objects(id=cust_id).first() if cust_id else None
        if o.job and o.job.customer:
            o.customer = o.job.customer
        o.lines = _parse_lines(request.form.get("lines") or "")
        subtotal, tax_total, discount_total = calculate_order_totals(o.lines)
        o.subtotal = subtotal
        o.tax_amount = tax_total
        o.discount_amount = discount_total
        o.total = max(subtotal - discount_total + tax_total + float(o.shipping_cost or 0.0), 0.0)
        o.updated_at = datetime.utcnow()
        o.save()
        flash("Order updated.", "success")
        return redirect(url_for("admin_orders.orders_edit", order_id=o.id))
    jobs_raw = Job.objects().order_by("job_number")
    jobs = []
    for j in jobs_raw:
        try:
            cust_id = str(j.customer.id) if j.customer else ""
        except Exception:
            cust_id = ""
        jobs.append({"id": j.id, "job_number": j.job_number, "customer_id": cust_id})
    sups = Supplier.objects().order_by("name")
    custs = Customer.objects().order_by("name")
    lines = "\n".join([f"{l.pn},{l.rev},{l.qty:g},{l.uom},{l.note or ''},{l.unit_price or 0},{l.discount_pct or 0},{l.tax_pct or 0}" for l in (o.lines or [])])
    return render_template("admin/orders_form.html", order=o, jobs=jobs, suppliers=sups, customers=custs, lines=lines)


@bp.post("/from_job/<job_id>")
@permissions_required("orders.manage")
def orders_from_job(job_id):
    job = Job.objects(id=job_id).first()
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("admin_jobs.jobs_list"))
    parts_raw = (request.form.get("parts_json") or "").strip()
    try:
        parts = json.loads(parts_raw) if parts_raw else []
    except Exception:
        parts = []
    if not parts:
        flash("Select at least one part to create the order.", "error")
        return redirect(url_for("admin_jobs.jobs_edit", job_id=job.id))
    o = Order(
        order_number=generate_order_number("purchase"),
        kind="purchase",
        status="draft",
        job=job,
        customer=job.customer if job.customer else None,
        order_date=datetime.utcnow(),
        currency="USD",
    )
    lines = []
    for p in parts:
        pn = _canonical_pn(p.get("pn") or "")
        if not pn:
            continue
        rev = (p.get("rev") or "").strip()
        try:
            qty = float(p.get("qty") or 1.0)
        except Exception:
            qty = 1.0
        if qty <= 0:
            continue
        lines.append(OrderLine(
            pn=pn,
            rev=rev,
            qty=qty,
            uom=(p.get("uom") or "EA").strip(),
            note=(p.get("note") or "").strip(),
            description=(p.get("desc") or "").strip(),
        ))
    if not lines:
        flash("No valid parts to create the order.", "error")
        return redirect(url_for("admin_jobs.jobs_edit", job_id=job.id))
    o.lines = consolidate_order_lines(lines)
    subtotal, tax_total, discount_total = calculate_order_totals(o.lines)
    o.subtotal = subtotal
    o.tax_amount = tax_total
    o.discount_amount = discount_total
    o.total = max(subtotal - discount_total + tax_total + float(o.shipping_cost or 0.0), 0.0)
    o.updated_at = datetime.utcnow()
    o.save()
    flash("Order created from job.", "success")
    return redirect(url_for("admin_orders.orders_edit", order_id=o.id))

# JSON helpers for interactive order lines

def _job_required_qty(job: Job, pn: str, rev: str) -> float:
    total = 0.0
    if not job:
        return total
    for l in (job.bom or []):
        if l.pn.lower() == (pn or '').lower() and (l.rev or '') == (rev or ''):
            try:
                total += float(l.qty or 0)
            except Exception:
                pass
    return total

def _total_ordered_for_job(job: Job, pn: str, rev: str) -> float:
    if not job:
        return 0.0
    tot = 0.0
    for o in Order.objects(job=job, status__ne="cancelled"):
        for l in (o.lines or []):
            if (l.pn or '').strip().lower() == (pn or '').lower() and (l.rev or '') == (rev or ''):
                try:
                    tot += float(l.qty or 0)
                except Exception:
                    pass
    return tot

@bp.get("/<order_id>/lines_json")
@permissions_required("orders.view")
def order_lines_json(order_id):
    try:
        o = Order.objects.get(id=order_id)
    except (DoesNotExist, ValidationError):
        abort(404)
    if o.lines:
        merged = consolidate_order_lines(o.lines)
        if len(merged) != len(o.lines):
            o.lines = merged
            subtotal, tax_total, discount_total = calculate_order_totals(o.lines)
            o.subtotal = subtotal
            o.tax_amount = tax_total
            o.discount_amount = discount_total
            o.total = max(subtotal - discount_total + tax_total + float(o.shipping_cost or 0.0), 0.0)
            o.updated_at = datetime.utcnow()
            o.save()
    rows = []
    for l in (o.lines or []):
        row = dict(pn=l.pn, rev=(l.rev or ''), qty=float(l.qty or 0), uom=(l.uom or 'EA'), note=(l.note or ''))
        if o.job:
            req = _job_required_qty(o.job, l.pn, (l.rev or ''))
            tot_ord = _total_ordered_for_job(o.job, l.pn, (l.rev or ''))
            row.update(job_required_qty=req, total_ordered_for_job=tot_ord)
        rows.append(row)
    return jsonify(rows)

@bp.post("/<order_id>/lines_update")
@permissions_required("orders.manage")
def order_lines_update(order_id):
    o = Order.objects(id=order_id).first() or abort(404)
    d = request.get_json(silent=True) or {}
    pn = _canonical_pn(d.get('pn') or ''); rev = (d.get('rev') or '')
    try:
        qty = float(d.get('qty') or 1.0)
    except Exception:
        qty = 1.0
    uom = (d.get('uom') or 'EA').strip(); note = (d.get('note') or '').strip()
    if not pn:
        return jsonify({"error":"missing pn"}), 400
    found = False
    if o.lines is None:
        o.lines = []
    for l in o.lines:
        if (l.pn or '').lower() == pn.lower() and (l.rev or '') == rev:
            l.qty = qty
            l.uom = uom
            l.note = note
            found = True
            break
    if not found:
        o.lines.append(OrderLine(pn=pn, rev=rev, qty=qty, uom=uom, note=note))
    o.lines = consolidate_order_lines(o.lines)
    subtotal, tax_total, discount_total = calculate_order_totals(o.lines)
    o.subtotal = subtotal
    o.tax_amount = tax_total
    o.discount_amount = discount_total
    o.total = max(subtotal - discount_total + tax_total + float(o.shipping_cost or 0.0), 0.0)
    o.updated_at = datetime.utcnow()
    o.save()
    return jsonify({"ok": True, "total": o.total})

@bp.post("/<order_id>/lines_remove")
@permissions_required("orders.manage")
def order_lines_remove(order_id):
    o = Order.objects(id=order_id).first() or abort(404)
    d = request.get_json(silent=True) or {}
    pn = (d.get('pn') or '').strip(); rev = (d.get('rev') or '')
    before = len(o.lines or [])
    o.lines = [l for l in (o.lines or []) if not ((l.pn or '').lower() == pn.lower() and (l.rev or '') == rev)]
    if len(o.lines) != before:
        o.lines = consolidate_order_lines(o.lines)
        subtotal, tax_total, discount_total = calculate_order_totals(o.lines)
        o.subtotal = subtotal
        o.tax_amount = tax_total
        o.discount_amount = discount_total
        o.total = max(subtotal - discount_total + tax_total + float(o.shipping_cost or 0.0), 0.0)
        o.updated_at = datetime.utcnow()
        o.save()
    return jsonify({"ok": True, "removed": before - len(o.lines), "total": o.total})

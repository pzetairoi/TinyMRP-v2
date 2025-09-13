from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_security import roles_required
from app.services.acl import permissions_required
from mongoengine.errors import DoesNotExist, ValidationError

from app.models.order import Order, OrderLine
from app.models.job import Job
from app.models.supplier import Supplier
from app.models.customer import Customer

bp = Blueprint("admin_orders", __name__, url_prefix="/admin/orders")


@bp.get("/")
@permissions_required("orders.view")
def orders_list():
    job_id = (request.args.get('job') or '').strip()
    qs = Order.objects()
    if job_id:
        try:
            j = Job.objects.get(id=job_id)
            qs = qs.filter(job=j)
        except Exception:
            pass
    orders = qs.order_by("-created_at")
    return render_template("admin/orders_list.html", orders=orders)


def _parse_lines(text: str):
    out = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"): continue
        parts = [x.strip() for x in s.split(",")]
        pn = parts[0] if parts else ""
        rev = parts[1] if len(parts) > 1 else ""
        qty = 1.0
        if len(parts) > 2:
            try:
                qty = float(parts[2])
            except Exception:
                qty = 1.0
        uom = parts[3] if len(parts) > 3 else "EA"
        note = parts[4] if len(parts) > 4 else ""
        if pn:
            out.append(OrderLine(pn=pn, rev=rev or "", qty=qty, uom=uom, note=note))
    return out


@bp.route("/new", methods=["GET","POST"])
@permissions_required("orders.manage")
def orders_new():
    if request.method == "POST":
        num = (request.form.get("order_number") or "").strip()
        if not num:
            flash("Order number is required.", "error"); return redirect(url_for("admin_orders.orders_new"))
        if Order.objects(order_number=num).first():
            flash("Order already exists.", "error"); return redirect(url_for("admin_orders.orders_new"))
        o = Order(order_number=num)
        o.description = (request.form.get("description") or "").strip()
        o.kind = (request.form.get("kind") or "purchase").strip()
        job_id = request.form.get("job")
        supp_id = request.form.get("supplier")
        cust_id = request.form.get("customer")
        if job_id: o.job = Job.objects(id=job_id).first()
        if supp_id: o.supplier = Supplier.objects(id=supp_id).first()
        if cust_id: o.customer = Customer.objects(id=cust_id).first()
        o.lines = _parse_lines(request.form.get("lines") or "")
        o.save()
        flash("Order created.", "success")
        return redirect(url_for("admin_orders.orders_list"))
    jobs = Job.objects().order_by("job_number")
    sups = Supplier.objects().order_by("name")
    custs = Customer.objects().order_by("name")
    return render_template("admin/orders_form.html", order=None, jobs=jobs, suppliers=sups, customers=custs)


@bp.route("/<order_id>/edit", methods=["GET","POST"])
@permissions_required("orders.manage")
def orders_edit(order_id):
    try:
        o = Order.objects.get(id=order_id)
    except (DoesNotExist, ValidationError):
        abort(404)
    if request.method == "POST":
        o.order_number = (request.form.get("order_number") or o.order_number).strip()
        o.description = (request.form.get("description") or "").strip()
        o.kind = (request.form.get("kind") or o.kind).strip()
        job_id = request.form.get("job")
        supp_id = request.form.get("supplier")
        cust_id = request.form.get("customer")
        o.job = Job.objects(id=job_id).first() if job_id else None
        o.supplier = Supplier.objects(id=supp_id).first() if supp_id else None
        o.customer = Customer.objects(id=cust_id).first() if cust_id else None
        o.lines = _parse_lines(request.form.get("lines") or "")
        o.save()
        flash("Order updated.", "success")
        return redirect(url_for("admin_orders.orders_list"))
    jobs = Job.objects().order_by("job_number")
    sups = Supplier.objects().order_by("name")
    custs = Customer.objects().order_by("name")
    lines = "\n".join([f"{l.pn},{l.rev},{l.qty:g},{l.uom},{l.note or ''}" for l in (o.lines or [])])
    return render_template("admin/orders_form.html", order=o, jobs=jobs, suppliers=sups, customers=custs, lines=lines)

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
    for o in Order.objects(job=job):
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
    pn = (d.get('pn') or '').strip(); rev = (d.get('rev') or '')
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
            l.qty = qty; l.uom = uom; l.note = note; found = True; break
    if not found:
        o.lines.append(OrderLine(pn=pn, rev=rev, qty=qty, uom=uom, note=note))
    o.save()
    return jsonify({"ok": True})

@bp.post("/<order_id>/lines_remove")
@permissions_required("orders.manage")
def order_lines_remove(order_id):
    o = Order.objects(id=order_id).first() or abort(404)
    d = request.get_json(silent=True) or {}
    pn = (d.get('pn') or '').strip(); rev = (d.get('rev') or '')
    before = len(o.lines or [])
    o.lines = [l for l in (o.lines or []) if not ((l.pn or '').lower() == pn.lower() and (l.rev or '') == rev)]
    if len(o.lines) != before:
        o.save()
    return jsonify({"ok": True, "removed": before - len(o.lines)})

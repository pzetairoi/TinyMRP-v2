import json
import io

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, send_file
from flask_login import current_user
from app.services.acl import (
    permissions_required,
    is_external_scoped_user,
    customer_scope_ids,
    supplier_scope_ids,
    user_has_permission,
)
from app.services.authorization import (
    authorised_get,
    authorised_part_pairs,
    authorise,
    has_permission,
    order_kind_allowed,
    order_relationship_allowed,
    scope_queryset,
)
from mongoengine.errors import DoesNotExist, ValidationError
from mongoengine.queryset.visitor import Q

from app.models.order import Order, OrderLine
from app.models.job import Job
from app.models.supplier import Supplier
from app.models.customer import Customer
from app.models.part import Part
from app.services.biz_utils import (
    ORDER_STATUS_FLOW,
    calculate_order_totals,
    can_transition_order,
    consolidate_order_lines,
    generate_order_number,
)
from app.services.order_scope import build_scope_pdf, build_scope_zip
from app.services.part_norm import clean_rev
from app.services.timezone_utils import parse_user_datetime, utc_now
from app.services.audit import log_action

bp = Blueprint("admin_orders", __name__, url_prefix="/admin/orders")

_ORDER_FORM_FIELDS = {
    "csrf_token",
    "order_number",
    "description",
    "kind",
    "status",
    "order_date",
    "currency",
    "job",
    "supplier",
    "customer",
    "customer_po",
    "shipping_method",
    "carrier",
    "tracking_number",
    "requested_delivery",
    "promised_delivery",
    "shipping_cost",
    "lines",
}


def _require(permission):
    if not authorise(current_user, permission).allowed:
        abort(403)


def _scoped_order(order_id, permission):
    return authorised_get(
        Order.objects,
        current_user,
        order_id,
        resource_type="orders",
        permission=permission,
    )


def _status_permission(status):
    return {
        "submitted": "orders.submit",
        "confirmed": "orders.approve",
        "in_production": "orders.fulfil",
        "ready_to_ship": "orders.fulfil",
        "shipped": "orders.ship",
        "delivered": "orders.fulfil",
        "cancelled": "orders.cancel",
    }.get(status, "orders.update")


def _require_order_form_permissions(current_status=None):
    if set(request.form) - _ORDER_FORM_FIELDS:
        abort(400)
    if set(request.form) & {
        "shipping_cost",
        "currency",
        "lines",
    }:
        _require("orders.financial.update")
    status = (request.form.get("status") or "").strip()
    if status and status != current_status:
        if status not in ORDER_STATUS_FLOW:
            abort(400)
        _require(_status_permission(status))
        if current_status and not can_transition_order(current_status, status):
            abort(400)


def _order_destinations(permission):
    jobs = scope_queryset(
        Job.objects(is_deleted=False),
        current_user,
        "jobs",
        permission=permission,
    ).order_by("job_number")
    suppliers = scope_queryset(
        Supplier.objects,
        current_user,
        "suppliers",
        permission=permission,
    ).order_by("name")
    customers = scope_queryset(
        Customer.objects,
        current_user,
        "customers",
        permission=permission,
    ).order_by("name")
    return jobs, suppliers, customers


def _destination(queryset, identifier, resource_type, permission):
    if not identifier:
        return None
    return authorised_get(
        queryset,
        current_user,
        identifier,
        resource_type=resource_type,
        permission=permission,
    )


@bp.get("/")
@permissions_required("orders.read")
def orders_list():
    job_id = (request.args.get('job') or '').strip()
    qs = scope_queryset(Order.objects, current_user, "orders")
    if job_id:
        try:
            j = authorised_get(
                Job.objects,
                current_user,
                job_id,
                resource_type="jobs",
            )
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
    date_to = _parse_date(request.args.get("to"), end_of_day=True)
    if date_to:
        qs = qs.filter(order_date__lte=date_to)
    total_min = request.args.get("total_min")
    total_max = request.args.get("total_max")
    if total_min not in (None, "") or total_max not in (None, ""):
        _require("orders.financial.read")
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
    is_external = is_external_scoped_user(current_user)
    cust_ids = customer_scope_ids(current_user)
    supp_ids = supplier_scope_ids(current_user)
    mask_supplier = bool(is_external and cust_ids)
    mask_customer = bool(is_external and supp_ids and not cust_ids)
    mask_job = bool(is_external and supp_ids and not cust_ids)
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
                "job": "-" if mask_job else job_number,
                "job_id": "" if mask_job else job_id,
                "supplier": "Hidden" if mask_supplier else supplier_name,
                "supplier_id": "" if mask_supplier else supplier_id,
                "customer": "Hidden" if mask_customer else customer_name,
                "customer_id": "" if mask_customer else customer_id,
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
@permissions_required("orders.archive")
def orders_delete(order_id):
    try:
        o = _scoped_order(order_id, "orders.archive")
        if not o:
            abort(404)
        o.status = "cancelled"
        o.updated_at = utc_now()
        o.save()
        flash("Order archived.", "success")
    except Exception:
        flash("Delete failed.", "error")
    return redirect(url_for("admin_orders.orders_list"))


@bp.get("/<order_id>")
@permissions_required("orders.read")
def orders_view(order_id):
    o = _scoped_order(order_id, "orders.read")
    if not o:
        abort(404)
    try:
        log_action("order.view", resource_type="order", resource=str(o.id))
    except Exception:
        pass
    is_external = is_external_scoped_user(current_user)
    cust_ids = customer_scope_ids(current_user)
    supp_ids = supplier_scope_ids(current_user)
    mask_supplier = bool(is_external and cust_ids)
    mask_customer = bool(is_external and supp_ids and not cust_ids)
    mask_job = bool(is_external and supp_ids and not cust_ids)
    jobs = []
    suppliers = []
    customers = []
    allowed_lines = authorised_part_pairs(
        current_user,
        [(line.pn, clean_rev(line.rev)) for line in (o.lines or [])],
    )
    visible_lines = [
        line
        for line in (o.lines or [])
        if (
            str(line.pn or "").strip().casefold(),
            clean_rev(line.rev).casefold(),
        )
        in allowed_lines
    ]
    lines = "\n".join([
        f"{l.pn},{l.rev},{l.qty:g},{l.uom},{l.note or ''},{l.unit_price or 0},{l.discount_pct or 0},{l.tax_pct or 0}"
        for l in visible_lines
    ])
    return render_template(
        "admin/orders_form.html",
        order=o,
        jobs=jobs,
        suppliers=suppliers,
        customers=customers,
        lines=lines,
        readonly=True,
        mask_supplier=mask_supplier,
        mask_customer=mask_customer,
        mask_job=mask_job,
        show_scope_download=not is_external,
    )


@bp.post("/<order_id>/scope_pdf")
@permissions_required("orders.read")
def order_scope_pdf(order_id):
    order = _scoped_order(order_id, "orders.read")
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin_orders.orders_list"))
    if is_external_scoped_user(current_user):
        abort(404)

    attach_docs = (request.form.get("attach_docs") or "").lower() in ("1", "true", "yes", "on")
    include_children = (request.form.get("include_children") or "").lower() in ("1", "true", "yes", "on")
    include_binder = (request.form.get("include_binder") or "").lower() in ("1", "true", "yes", "on")
    file_types = [v.strip().lower() for v in request.form.getlist("file_types") if (v or "").strip()]
    if file_types:
        attach_docs = True
    if include_children and not (attach_docs or include_binder):
        attach_docs = True
    pdf_bytes = build_scope_pdf(order)
    if attach_docs or include_children or include_binder:
        zip_bytes = build_scope_zip(
            order,
            pdf_bytes,
            attach_docs=attach_docs,
            include_children=include_children,
            file_types=file_types,
            include_binder=include_binder,
        )
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
        rev = clean_rev(parts[1] if len(parts) > 1 else "")
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


def _parse_date(value: str | None, *, end_of_day: bool = False):
    return parse_user_datetime(value, end_of_day=end_of_day)


@bp.route("/new", methods=["GET","POST"])
@permissions_required("orders.create")
def orders_new():
    if request.method == "POST":
        _require_order_form_permissions()
        num = (request.form.get("order_number") or "").strip() or generate_order_number(request.form.get("kind") or "purchase")
        if Order.objects(order_number=num).first():
            flash("Order already exists.", "error"); return redirect(url_for("admin_orders.orders_new"))
        o = Order(order_number=num)
        o.description = (request.form.get("description") or "").strip()
        o.kind = (request.form.get("kind") or "purchase").strip()
        if not order_kind_allowed(current_user, o.kind, "orders.create"):
            abort(403)
        o.status = (request.form.get("status") or "draft").strip()
        o.customer_po = (request.form.get("customer_po") or "").strip()
        o.shipping_method = (request.form.get("shipping_method") or "").strip()
        o.carrier = (request.form.get("carrier") or "").strip()
        o.tracking_number = (request.form.get("tracking_number") or "").strip()
        o.order_date = _parse_date(request.form.get("order_date")) or utc_now()
        o.requested_delivery = _parse_date(request.form.get("requested_delivery"))
        o.promised_delivery = _parse_date(request.form.get("promised_delivery"))
        o.shipping_cost = float(request.form.get("shipping_cost") or 0.0)
        o.currency = (request.form.get("currency") or "USD").strip()
        job_id = request.form.get("job")
        supp_id = request.form.get("supplier")
        cust_id = request.form.get("customer")
        if job_id:
            if not order_relationship_allowed(
                current_user, o.kind, "job", "orders.create"
            ):
                abort(404)
            o.job = _destination(
                Job.objects(is_deleted=False),
                job_id,
                "jobs",
                "orders.create",
            )
            if not o.job:
                abort(404)
        if supp_id:
            if not order_relationship_allowed(
                current_user, o.kind, "supplier", "orders.create"
            ):
                abort(404)
            o.supplier = _destination(
                Supplier.objects,
                supp_id,
                "suppliers",
                "orders.create",
            )
            if not o.supplier:
                abort(404)
        if cust_id:
            if not order_relationship_allowed(
                current_user, o.kind, "customer", "orders.create"
            ):
                abort(404)
            o.customer = _destination(
                Customer.objects,
                cust_id,
                "customers",
                "orders.create",
            )
            if not o.customer:
                abort(404)
        if o.job and o.job.customer:
            o.customer = o.job.customer
        o.lines = _parse_lines(request.form.get("lines") or "")
        subtotal, tax_total, discount_total = calculate_order_totals(o.lines)
        o.subtotal = subtotal
        o.tax_amount = tax_total
        o.discount_amount = discount_total
        o.total = max(subtotal - discount_total + tax_total + float(o.shipping_cost or 0.0), 0.0)
        o.updated_at = utc_now()
        o.save()
        flash("Order created.", "success")
        return redirect(url_for("admin_orders.orders_edit", order_id=o.id))
    jobs_raw, sups, custs = _order_destinations("orders.create")
    jobs = []
    for j in jobs_raw:
        try:
            cust_id = str(j.customer.id) if j.customer else ""
        except Exception:
            cust_id = ""
        jobs.append({"id": j.id, "job_number": j.job_number, "customer_id": cust_id})
    prefill_job = request.args.get("job") or ""
    prefill_customer = ""
    if prefill_job:
        job = _destination(
            Job.objects(is_deleted=False),
            prefill_job,
            "jobs",
            "orders.create",
        )
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
@permissions_required("orders.update")
def orders_edit(order_id):
    o = _scoped_order(order_id, "orders.update")
    if not o:
        abort(404)
    try:
        log_action("order.view", resource_type="order", resource=str(o.id))
    except Exception:
        pass
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
    if request.method == "POST":
        _require_order_form_permissions(o.status)
        target_kind = (request.form.get("kind") or o.kind).strip()
        if not order_kind_allowed(current_user, target_kind, "orders.update"):
            abort(403)
        o.order_number = (request.form.get("order_number") or o.order_number).strip()
        o.description = (request.form.get("description") or "").strip()
        o.kind = target_kind
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
        for identifier, relationship in (
            (job_id, "job"),
            (supp_id, "supplier"),
            (cust_id, "customer"),
        ):
            if identifier and not order_relationship_allowed(
                current_user,
                target_kind,
                relationship,
                "orders.update",
            ):
                abort(404)
        o.job = (
            _destination(
                Job.objects(is_deleted=False),
                job_id,
                "jobs",
                "orders.update",
            )
            if job_id
            else None
        )
        o.supplier = (
            _destination(
                Supplier.objects,
                supp_id,
                "suppliers",
                "orders.update",
            )
            if supp_id
            else None
        )
        o.customer = (
            _destination(
                Customer.objects,
                cust_id,
                "customers",
                "orders.update",
            )
            if cust_id
            else None
        )
        if (
            (job_id and not o.job)
            or (supp_id and not o.supplier)
            or (cust_id and not o.customer)
        ):
            abort(404)
        if o.job and o.job.customer:
            o.customer = o.job.customer
        o.lines = _parse_lines(request.form.get("lines") or "")
        subtotal, tax_total, discount_total = calculate_order_totals(o.lines)
        o.subtotal = subtotal
        o.tax_amount = tax_total
        o.discount_amount = discount_total
        o.total = max(subtotal - discount_total + tax_total + float(o.shipping_cost or 0.0), 0.0)
        o.updated_at = utc_now()
        o.save()
        flash("Order updated.", "success")
        return redirect(url_for("admin_orders.orders_edit", order_id=o.id))
    jobs_raw, sups, custs = _order_destinations("orders.update")
    jobs = []
    for j in jobs_raw:
        try:
            cust_id = str(j.customer.id) if j.customer else ""
        except Exception:
            cust_id = ""
        jobs.append({"id": j.id, "job_number": j.job_number, "customer_id": cust_id})
    allowed_lines = authorised_part_pairs(
        current_user,
        [(line.pn, clean_rev(line.rev)) for line in (o.lines or [])],
    )
    visible_lines = [
        line
        for line in (o.lines or [])
        if (
            str(line.pn or "").strip().casefold(),
            clean_rev(line.rev).casefold(),
        )
        in allowed_lines
    ]
    lines = "\n".join(
        [
            f"{line.pn},{line.rev},{line.qty:g},{line.uom},{line.note or ''},{line.unit_price or 0},{line.discount_pct or 0},{line.tax_pct or 0}"
            for line in visible_lines
        ]
    )
    return render_template("admin/orders_form.html", order=o, jobs=jobs, suppliers=sups, customers=custs, lines=lines)


@bp.post("/from_job/<job_id>")
@permissions_required("orders.create")
def orders_from_job(job_id):
    if not order_kind_allowed(current_user, "purchase", "orders.create"):
        abort(403)
    if not order_relationship_allowed(
        current_user,
        "purchase",
        "job",
        "orders.create",
    ):
        abort(404)
    job = _destination(
        Job.objects(is_deleted=False),
        job_id,
        "jobs",
        "orders.create",
    )
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
        order_date=utc_now(),
        currency="USD",
    )
    lines = []
    for p in parts:
        pn = _canonical_pn(p.get("pn") or "")
        if not pn:
            continue
        rev = clean_rev(p.get("rev") or "")
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
    o.updated_at = utc_now()
    o.save()
    flash("Order created from job.", "success")
    return redirect(url_for("admin_orders.orders_edit", order_id=o.id))

# JSON helpers for interactive order lines

def _job_required_qty(job: Job, pn: str, rev: str) -> float:
    total = 0.0
    if not job:
        return total
    for l in (job.bom or []):
        if l.pn.lower() == (pn or '').lower() and clean_rev(l.rev) == clean_rev(rev):
            try:
                total += float(l.qty or 0)
            except Exception:
                pass
    return total

def _total_ordered_for_job(job: Job, pn: str, rev: str) -> float:
    if not job:
        return 0.0
    tot = 0.0
    queryset = Order.objects(job=job, status__ne="cancelled")
    if getattr(current_user, "is_authenticated", False):
        queryset = scope_queryset(queryset, current_user, "orders")
    for o in queryset:
        if (o.status or "") == "draft":
            continue
        for l in (o.lines or []):
            if (l.pn or '').strip().lower() == (pn or '').lower() and clean_rev(l.rev) == clean_rev(rev):
                try:
                    tot += float(l.qty or 0)
                except Exception:
                    pass
    return tot

@bp.get("/<order_id>/lines_json")
@permissions_required("orders.read")
def order_lines_json(order_id):
    o = _scoped_order(order_id, "orders.read")
    if not o:
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
    rows = []
    for l in (o.lines or []):
        rev = clean_rev(l.rev)
        row = dict(pn=l.pn, rev=rev, qty=float(l.qty or 0), uom=(l.uom or 'EA'), note=(l.note or ''))
        if o.job:
            req = _job_required_qty(o.job, l.pn, rev)
            tot_ord = _total_ordered_for_job(o.job, l.pn, rev)
            row.update(job_required_qty=req, total_ordered_for_job=tot_ord)
        rows.append(row)
    return jsonify(rows)

@bp.post("/<order_id>/lines_update")
@permissions_required("orders.update")
def order_lines_update(order_id):
    o = _scoped_order(order_id, "orders.update") or abort(404)
    d = request.get_json(silent=True) or {}
    if set(d) - {"pn", "rev", "qty", "uom", "note"}:
        abort(400)
    pn = _canonical_pn(d.get('pn') or ''); rev = clean_rev(d.get('rev') or '')
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
        if (l.pn or '').lower() == pn.lower() and clean_rev(l.rev) == rev:
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
    o.updated_at = utc_now()
    o.save()
    return jsonify({"ok": True, "total": o.total})

@bp.post("/<order_id>/lines_remove")
@permissions_required("orders.update")
def order_lines_remove(order_id):
    o = _scoped_order(order_id, "orders.update") or abort(404)
    d = request.get_json(silent=True) or {}
    if set(d) - {"pn", "rev"}:
        abort(400)
    pn = (d.get('pn') or '').strip(); rev = clean_rev(d.get('rev') or '')
    before = len(o.lines or [])
    o.lines = [l for l in (o.lines or []) if not ((l.pn or '').lower() == pn.lower() and clean_rev(l.rev) == rev)]
    if len(o.lines) != before:
        o.lines = consolidate_order_lines(o.lines)
        subtotal, tax_total, discount_total = calculate_order_totals(o.lines)
        o.subtotal = subtotal
        o.tax_amount = tax_total
        o.discount_amount = discount_total
        o.total = max(subtotal - discount_total + tax_total + float(o.shipping_cost or 0.0), 0.0)
        o.updated_at = utc_now()
        o.save()
    return jsonify({"ok": True, "removed": before - len(o.lines), "total": o.total})

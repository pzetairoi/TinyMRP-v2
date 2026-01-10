from __future__ import annotations

from datetime import datetime
from typing import List

from flask import Blueprint, jsonify, request
from mongoengine.queryset.visitor import Q

from app.models.order import Order, OrderLine
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.job import Job
from app.models.common import Address
from app.services.api_auth import api_auth_required
from app.services.biz_utils import generate_order_number, can_transition_order, calculate_order_totals, ORDER_STATUS_FLOW, consolidate_order_lines
from app.services.acl import apply_order_scope
from app.views.api_helpers import json_error, ensure_permissions, parse_pagination, iso, get_json

bp = Blueprint("orders_api", __name__, url_prefix="/api/orders")


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _parse_address(data) -> Address | None:
    if not data:
        return None
    return Address(
        label=data.get("label") or "",
        line1=data.get("line1") or "",
        line2=data.get("line2") or "",
        city=data.get("city") or "",
        state=data.get("state") or "",
        postal=data.get("postal") or "",
        country=data.get("country") or "",
        is_default=bool(data.get("is_default")),
    )


def _parse_lines(items) -> List[OrderLine]:
    out = []
    for raw in items or []:
        pn = (raw.get("pn") or raw.get("part_number") or "").strip()
        if not pn:
            continue
        line = OrderLine(
            pn=pn,
            rev=(raw.get("rev") or raw.get("revision") or "").strip(),
            qty=float(raw.get("qty") or 1.0),
            uom=(raw.get("uom") or "EA").strip(),
            note=(raw.get("note") or "").strip(),
            description=(raw.get("description") or "").strip(),
            unit_price=float(raw.get("unit_price") or 0.0),
            discount_pct=float(raw.get("discount_pct") or 0.0),
            tax_pct=float(raw.get("tax_pct") or 0.0),
            qty_shipped=float(raw.get("qty_shipped") or 0.0),
            qty_received=float(raw.get("qty_received") or 0.0),
            requested_delivery=_parse_date(raw.get("requested_delivery")),
        )
        out.append(line)
    return consolidate_order_lines(out)


def _order_to_dict(o: Order):
    return {
        "order_number": o.order_number,
        "kind": o.kind,
        "description": o.description,
        "status": o.status,
        "customer": getattr(o.customer, "name", None),
        "supplier": getattr(o.supplier, "name", None),
        "job": getattr(o.job, "job_number", None),
        "order_date": iso(o.order_date),
        "requested_delivery": iso(o.requested_delivery),
        "promised_delivery": iso(o.promised_delivery),
        "actual_delivery": iso(o.actual_delivery),
        "subtotal": o.subtotal,
        "tax_amount": o.tax_amount,
        "shipping_cost": o.shipping_cost,
        "discount_amount": o.discount_amount,
        "total": o.total,
        "currency": o.currency,
        "customer_po": o.customer_po,
        "shipping_method": o.shipping_method,
        "carrier": o.carrier,
        "tracking_number": o.tracking_number,
        "approved_by": o.approved_by,
        "approved_at": iso(o.approved_at),
        "rejection_reason": o.rejection_reason,
        "lines": [
            {
                "pn": l.pn,
                "rev": l.rev or "",
                "qty": float(l.qty or 0.0),
                "uom": l.uom,
                "note": l.note,
                "description": l.description,
                "unit_price": l.unit_price,
                "discount_pct": l.discount_pct,
                "tax_pct": l.tax_pct,
                "line_total": l.line_total,
                "qty_shipped": l.qty_shipped,
                "qty_received": l.qty_received,
                "requested_delivery": iso(l.requested_delivery),
            }
            for l in (o.lines or [])
        ],
    }


def _list_orders(args, user):
    page, size = parse_pagination()
    q = Order.objects()
    kind = args.get("type")
    if kind:
        q = q.filter(kind__in=[k.strip() for k in kind.split(",") if k.strip()])
    status = args.get("status")
    if status:
        q = q.filter(status__in=[s.strip() for s in status.split(",") if s.strip()])
    q_text = args.get("q")
    if q_text:
        q = q.filter(Q(order_number__icontains=q_text) | Q(description__icontains=q_text))
    customer = args.get("customer")
    if customer:
        cust = Customer.objects(code=customer).first() or Customer.objects(id=customer).first()
        if cust:
            q = q.filter(customer=cust)
    supplier = args.get("supplier")
    if supplier:
        sup = Supplier.objects(code=supplier).first() or Supplier.objects(id=supplier).first()
        if sup:
            q = q.filter(supplier=sup)

    date_from = _parse_date(args.get("from"))
    date_to = _parse_date(args.get("to"))
    if date_from:
        q = q.filter(order_date__gte=date_from)
    if date_to:
        q = q.filter(order_date__lte=date_to)

    sort = args.get("sort", "order_date")
    direction = (args.get("direction", "desc") or "desc").lower()
    sort_key = "order_date" if sort not in ("order_date", "total", "status", "order_number") else sort
    if direction == "desc":
        sort_key = "-" + sort_key

    q = apply_order_scope(q, user)
    total = q.count()
    items = q.order_by(sort_key).skip((page - 1) * size).limit(size)
    return jsonify({
        "ok": True,
        "items": [_order_to_dict(o) for o in items],
        "page": page,
        "page_size": size,
        "total": total,
    })


@bp.get("")
@api_auth_required
def list_orders():
    user, err = ensure_permissions("orders.view")
    if err:
        return err
    return _list_orders(request.args, user)


@bp.get("/sales")
@api_auth_required
def list_sales_orders():
    user, err = ensure_permissions("orders.view")
    if err:
        return err
    args = request.args.to_dict(flat=True)
    args["type"] = "sales"
    return _list_orders(args, user)


@bp.get("/purchase")
@api_auth_required
def list_purchase_orders():
    user, err = ensure_permissions("orders.view")
    if err:
        return err
    args = request.args.to_dict(flat=True)
    args["type"] = "purchase"
    return _list_orders(args, user)


@bp.post("")
@api_auth_required
def create_order():
    user, err = ensure_permissions("orders.manage")
    if err:
        return err
    data = get_json()
    kind = (data.get("kind") or "purchase").strip()
    order_number = (data.get("order_number") or "").strip() or generate_order_number(kind)
    if Order.objects(order_number=order_number).first():
        return json_error("conflict", "Order number already exists.", 409)

    order = Order(
        order_number=order_number,
        description=(data.get("description") or "").strip(),
        kind=kind,
        status=(data.get("status") or "draft").strip(),
        customer_po=(data.get("customer_po") or "").strip(),
        order_date=_parse_date(data.get("order_date")) or datetime.utcnow(),
        requested_delivery=_parse_date(data.get("requested_delivery")),
        promised_delivery=_parse_date(data.get("promised_delivery")),
        actual_delivery=_parse_date(data.get("actual_delivery")),
        shipping_cost=float(data.get("shipping_cost") or 0.0),
        discount_amount=float(data.get("discount_amount") or 0.0),
        currency=(data.get("currency") or "USD").strip(),
        shipping_address=_parse_address(data.get("shipping_address")),
        shipping_method=(data.get("shipping_method") or "").strip(),
        carrier=(data.get("carrier") or "").strip(),
        tracking_number=(data.get("tracking_number") or "").strip(),
    )

    order.lines = _parse_lines(data.get("lines") or [])
    subtotal, tax_total, discount_total = calculate_order_totals(order.lines)
    order.subtotal = subtotal
    order.tax_amount = tax_total
    order.discount_amount = discount_total
    order.total = max(subtotal - discount_total + tax_total + float(order.shipping_cost or 0.0), 0.0)

    cust_id = data.get("customer_id") or ""
    cust_code = data.get("customer_code") or ""
    if cust_id or cust_code:
        order.customer = Customer.objects(id=cust_id).first() if cust_id else Customer.objects(code=cust_code).first()
    sup_id = data.get("supplier_id") or ""
    sup_code = data.get("supplier_code") or ""
    if sup_id or sup_code:
        order.supplier = Supplier.objects(id=sup_id).first() if sup_id else Supplier.objects(code=sup_code).first()
    job_id = data.get("job_id") or ""
    if job_id:
        order.job = Job.objects(id=job_id).first()

    order.updated_at = datetime.utcnow()
    order.save()
    return jsonify({"ok": True, "order": _order_to_dict(order)})


@bp.get("/<order_number>")
@api_auth_required
def get_order(order_number):
    user, err = ensure_permissions("orders.view")
    if err:
        return err
    order = apply_order_scope(Order.objects(order_number=order_number), user).first()
    if not order:
        return json_error("not_found", "Order not found.", 404)
    return jsonify({"ok": True, "order": _order_to_dict(order)})


@bp.put("/<order_number>")
@api_auth_required
def update_order(order_number):
    user, err = ensure_permissions("orders.manage")
    if err:
        return err
    order = Order.objects(order_number=order_number).first()
    if not order:
        return json_error("not_found", "Order not found.", 404)
    data = get_json()
    for key in ("description", "kind", "status", "customer_po", "shipping_method", "carrier", "tracking_number", "currency"):
        if key in data:
            setattr(order, key, (data.get(key) or "").strip())
    if "order_date" in data:
        order.order_date = _parse_date(data.get("order_date"))
    if "requested_delivery" in data:
        order.requested_delivery = _parse_date(data.get("requested_delivery"))
    if "promised_delivery" in data:
        order.promised_delivery = _parse_date(data.get("promised_delivery"))
    if "actual_delivery" in data:
        order.actual_delivery = _parse_date(data.get("actual_delivery"))
    if "shipping_cost" in data:
        order.shipping_cost = float(data.get("shipping_cost") or 0.0)
    if "discount_amount" in data:
        order.discount_amount = float(data.get("discount_amount") or 0.0)
    if "shipping_address" in data:
        order.shipping_address = _parse_address(data.get("shipping_address"))

    if "lines" in data:
        order.lines = _parse_lines(data.get("lines") or [])
        subtotal, tax_total, discount_total = calculate_order_totals(order.lines)
        order.subtotal = subtotal
        order.tax_amount = tax_total
        order.discount_amount = discount_total
        order.total = max(subtotal - discount_total + tax_total + float(order.shipping_cost or 0.0), 0.0)

    if "customer_id" in data or "customer_code" in data:
        cust_id = data.get("customer_id") or ""
        cust_code = data.get("customer_code") or ""
        order.customer = Customer.objects(id=cust_id).first() if cust_id else Customer.objects(code=cust_code).first()
    if "supplier_id" in data or "supplier_code" in data:
        sup_id = data.get("supplier_id") or ""
        sup_code = data.get("supplier_code") or ""
        order.supplier = Supplier.objects(id=sup_id).first() if sup_id else Supplier.objects(code=sup_code).first()
    if "job_id" in data:
        order.job = Job.objects(id=data.get("job_id")).first() if data.get("job_id") else None

    order.updated_at = datetime.utcnow()
    order.save()
    return jsonify({"ok": True, "order": _order_to_dict(order)})


@bp.delete("/<order_number>")
@api_auth_required
def delete_order(order_number):
    user, err = ensure_permissions("orders.manage")
    if err:
        return err
    order = Order.objects(order_number=order_number).first()
    if not order:
        return json_error("not_found", "Order not found.", 404)
    if order.status not in ("draft", "submitted", "cancelled"):
        return json_error("invalid_state", "Order cannot be deleted in this status.", 400)
    order.status = "cancelled"
    order.updated_at = datetime.utcnow()
    order.save()
    return jsonify({"ok": True})


@bp.post("/<order_number>/submit")
@api_auth_required
def order_submit(order_number):
    user, err = ensure_permissions("orders.manage")
    if err:
        return err
    order = Order.objects(order_number=order_number).first()
    if not order:
        return json_error("not_found", "Order not found.", 404)
    if not can_transition_order(order.status, "submitted"):
        return json_error("invalid_transition", "Status transition not allowed.", 400)
    order.status = "submitted"
    order.updated_at = datetime.utcnow()
    order.save()
    return jsonify({"ok": True, "order": _order_to_dict(order)})


@bp.post("/<order_number>/approve")
@api_auth_required
def order_approve(order_number):
    user, err = ensure_permissions("orders.manage")
    if err:
        return err
    order = Order.objects(order_number=order_number).first()
    if not order:
        return json_error("not_found", "Order not found.", 404)
    if not can_transition_order(order.status, "confirmed"):
        return json_error("invalid_transition", "Status transition not allowed.", 400)
    order.status = "confirmed"
    order.approved_by = getattr(user, "email", "")
    order.approved_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()
    order.save()
    return jsonify({"ok": True, "order": _order_to_dict(order)})


@bp.post("/<order_number>/ship")
@api_auth_required
def order_ship(order_number):
    user, err = ensure_permissions("orders.manage")
    if err:
        return err
    order = Order.objects(order_number=order_number).first()
    if not order:
        return json_error("not_found", "Order not found.", 404)
    data = get_json()
    if not can_transition_order(order.status, "shipped"):
        return json_error("invalid_transition", "Status transition not allowed.", 400)
    order.status = "shipped"
    order.carrier = (data.get("carrier") or order.carrier or "").strip()
    order.tracking_number = (data.get("tracking_number") or order.tracking_number or "").strip()
    order.actual_delivery = _parse_date(data.get("actual_delivery")) or order.actual_delivery
    order.updated_at = datetime.utcnow()
    order.save()
    return jsonify({"ok": True, "order": _order_to_dict(order)})


@bp.patch("/<order_number>/status")
@api_auth_required
def order_status(order_number):
    user, err = ensure_permissions("orders.manage")
    if err:
        return err
    order = Order.objects(order_number=order_number).first()
    if not order:
        return json_error("not_found", "Order not found.", 404)
    data = get_json()
    new_status = (data.get("status") or "").strip()
    if new_status not in ORDER_STATUS_FLOW:
        return json_error("invalid_status", "Invalid status.", 400)
    if not can_transition_order(order.status, new_status):
        return json_error("invalid_transition", "Status transition not allowed.", 400)
    order.status = new_status
    order.updated_at = datetime.utcnow()
    order.save()
    return jsonify({"ok": True, "order": _order_to_dict(order)})


@bp.get("/stats")
@api_auth_required
def order_stats():
    user, err = ensure_permissions("orders.view")
    if err:
        return err
    base = Order.objects()
    return jsonify({
        "ok": True,
        "status_counts": {s: base.filter(status=s).count() for s in ORDER_STATUS_FLOW.keys()},
        "revenue_month": sum([float(o.total or 0.0) for o in base.filter(order_date__gte=datetime.utcnow().replace(day=1))]),
        "avg_order_value": (sum([float(o.total or 0.0) for o in base]) / base.count()) if base.count() else 0.0,
    })


@bp.get("/dashboard")
@api_auth_required
def order_dashboard():
    user, err = ensure_permissions("orders.view")
    if err:
        return err
    recent = Order.objects().order_by("-order_date").limit(10)
    pending = Order.objects(status__in=["draft", "submitted"]).order_by("-order_date").limit(10)
    return jsonify({
        "ok": True,
        "recent": [_order_to_dict(o) for o in recent],
        "pending": [_order_to_dict(o) for o in pending],
    })

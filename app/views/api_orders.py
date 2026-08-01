from __future__ import annotations

from typing import List

from flask import Blueprint, jsonify, request
from mongoengine.queryset.visitor import Q

from app.models.order import Order, OrderLine
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.job import Job
from app.models.common import Address
from app.services.api_auth import api_auth_required
from app.services.authorization import (
    authorised_get,
    authorised_part_pairs,
    has_permission,
    order_kind_allowed,
    order_relationship_allowed,
    scope_queryset,
)
from app.services.biz_utils import order_status_permission, generate_order_number, can_transition_order, calculate_order_totals, ORDER_STATUS_FLOW, consolidate_order_lines, safe_ref
from app.services.field_policies import (
    filter_response_fields,
    response_context,
)
from app.services.part_norm import clean_rev
from app.services.timezone_utils import utc_now
from app.views.api_helpers import (
    add_datetime_fields,
    ensure_permissions,
    get_json,
    invalid_payload_fields,
    json_error,
    parse_datetime_param,
    parse_pagination,
)

bp = Blueprint("orders_api", __name__, url_prefix="/api/orders")

_ORDER_FIELDS = {
    "order_number",
    "description",
    "kind",
    "status",
    "customer_po",
    "order_date",
    "requested_delivery",
    "promised_delivery",
    "actual_delivery",
    "shipping_cost",
    "discount_amount",
    "currency",
    "shipping_address",
    "shipping_method",
    "carrier",
    "tracking_number",
    "lines",
    "customer_id",
    "customer_code",
    "supplier_id",
    "supplier_code",
    "job_id",
}
_ORDER_FINANCIAL_FIELDS = {"shipping_cost", "discount_amount", "currency"}
_LINE_FINANCIAL_FIELDS = {"unit_price", "discount_pct", "tax_pct"}
_LINE_FULFILMENT_FIELDS = {"qty_shipped", "qty_received"}
_LINE_FIELDS = {
    "pn",
    "part_number",
    "rev",
    "revision",
    "qty",
    "uom",
    "note",
    "description",
    "unit_price",
    "discount_pct",
    "tax_pct",
    "qty_shipped",
    "qty_received",
    "requested_delivery",
}
_ADDRESS_FIELDS = {
    "label",
    "line1",
    "line2",
    "city",
    "state",
    "postal",
    "country",
    "is_default",
}


def _has_financial_changes(data):
    if set(data) & _ORDER_FINANCIAL_FIELDS:
        return True
    return any(
        bool(set(raw or {}) & _LINE_FINANCIAL_FIELDS)
        for raw in (data.get("lines") or [])
        if isinstance(raw, dict)
    )


def _invalid_nested_fields(data):
    address = data.get("shipping_address")
    if isinstance(address, dict):
        invalid = invalid_payload_fields(address, _ADDRESS_FIELDS)
        if invalid:
            return invalid
    for raw in data.get("lines") or []:
        if not isinstance(raw, dict):
            return json_error("invalid_lines", "Order lines must be objects.", 400)
        invalid = invalid_payload_fields(raw, _LINE_FIELDS)
        if invalid:
            return invalid
    return None


def _has_fulfilment_changes(data):
    return any(
        bool(set(raw or {}) & _LINE_FULFILMENT_FIELDS)
        for raw in (data.get("lines") or [])
        if isinstance(raw, dict)
    )


def _scoped_order(user, order_number, permission):
    return authorised_get(
        Order.objects,
        user,
        order_number,
        resource_type="orders",
        identifier_field="order_number",
        permission=permission,
    )


def _scoped_related(user, queryset, identifier, resource_type, permission, field="id"):
    if not identifier:
        return None
    return authorised_get(
        queryset,
        user,
        identifier,
        resource_type=resource_type,
        identifier_field=field,
        permission=permission,
    )


def _related_by_id_or_code(user, queryset, resource_type, permission, object_id, code):
    item = _scoped_related(user, queryset, object_id, resource_type, permission)
    if item:
        return item
    return _scoped_related(
        user,
        queryset,
        code,
        resource_type,
        permission,
        field="code",
    )


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
            rev=clean_rev(raw.get("rev") or raw.get("revision") or ""),
            qty=float(raw.get("qty") or 1.0),
            uom=(raw.get("uom") or "EA").strip(),
            note=(raw.get("note") or "").strip(),
            description=(raw.get("description") or "").strip(),
            unit_price=float(raw.get("unit_price") or 0.0),
            discount_pct=float(raw.get("discount_pct") or 0.0),
            tax_pct=float(raw.get("tax_pct") or 0.0),
            qty_shipped=float(raw.get("qty_shipped") or 0.0),
            qty_received=float(raw.get("qty_received") or 0.0),
            requested_delivery=parse_datetime_param(raw.get("requested_delivery")),
        )
        out.append(line)
    return consolidate_order_lines(out)


def _order_to_dict(o: Order, *, user=None):
    allowed_parts = (
        authorised_part_pairs(
            user,
            [(line.pn, clean_rev(line.rev)) for line in (o.lines or [])],
        )
        if user is not None
        else None
    )

    def can_include(line) -> bool:
        if allowed_parts is None:
            return True
        return (
            str(line.pn or "").strip().casefold(),
            clean_rev(line.rev).casefold(),
        ) in allowed_parts

    boundary = response_context("orders", user)
    line_payloads = []
    for line in o.lines or []:
        if not can_include(line):
            continue
        line_payload = {
            "pn": line.pn,
            "rev": clean_rev(line.rev),
            "qty": float(line.qty or 0.0),
            "uom": line.uom,
            "note": line.note,
            "description": line.description,
            "unit_price": line.unit_price,
            "discount_pct": line.discount_pct,
            "tax_pct": line.tax_pct,
            "line_total": line.line_total,
            "qty_shipped": line.qty_shipped,
            "qty_received": line.qty_received,
        }
        add_datetime_fields(
            line_payload,
            "requested_delivery",
            line.requested_delivery,
        )
        line_payloads.append(
            filter_response_fields(
                "order_line",
                user,
                line_payload,
                context={
                    "policy_context": boundary,
                    "surface": "embedded",
                    "order_kind": o.kind,
                    "preserve_null_fields": _LINE_FINANCIAL_FIELDS
                    | {"line_total"},
                },
            )
        )
    payload = {
        "order_number": o.order_number,
        "kind": o.kind,
        "description": o.description,
        "status": o.status,
        "customer": getattr(safe_ref(o, "customer"), "name", None),
        "supplier": getattr(safe_ref(o, "supplier"), "name", None),
        "job": getattr(safe_ref(o, "job"), "job_number", None),
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
        "rejection_reason": o.rejection_reason,
        "lines": line_payloads,
    }
    for field_name, value in (
        ("order_date", o.order_date),
        ("requested_delivery", o.requested_delivery),
        ("promised_delivery", o.promised_delivery),
        ("actual_delivery", o.actual_delivery),
        ("approved_at", o.approved_at),
        ("created_at", o.created_at),
        ("updated_at", o.updated_at),
    ):
        add_datetime_fields(payload, field_name, value)
    return filter_response_fields(
        "orders",
        user,
        payload,
        context={
            "policy_context": boundary,
            "order_kind": o.kind,
            "preserve_null_fields": _ORDER_FINANCIAL_FIELDS
            | {"subtotal", "tax_amount", "total"},
        },
    )


def _list_orders(args, user):
    page, size = parse_pagination()
    q = scope_queryset(Order.objects, user, "orders")
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
        cust = _related_by_id_or_code(
            user,
            Customer.objects,
            "customers",
            "orders.read",
            customer,
            customer,
        )
        if cust:
            q = q.filter(customer=cust)
        else:
            q = q.filter(id__in=[])
    supplier = args.get("supplier")
    if supplier:
        sup = _related_by_id_or_code(
            user,
            Supplier.objects,
            "suppliers",
            "orders.read",
            supplier,
            supplier,
        )
        if sup:
            q = q.filter(supplier=sup)
        else:
            q = q.filter(id__in=[])

    date_from = parse_datetime_param(args.get("from"))
    date_to = parse_datetime_param(args.get("to"), end_of_day=True)
    if date_from:
        q = q.filter(order_date__gte=date_from)
    if date_to:
        q = q.filter(order_date__lte=date_to)

    sort = args.get("sort", "order_date")
    if sort == "total" and not has_permission(user, "orders.financial.read"):
        return json_error("forbidden", "Permission denied.", 403)
    direction = (args.get("direction", "desc") or "desc").lower()
    sort_key = "order_date" if sort not in ("order_date", "total", "status", "order_number") else sort
    if direction == "desc":
        sort_key = "-" + sort_key

    total = q.count()
    items = q.order_by(sort_key).skip((page - 1) * size).limit(size)
    return jsonify({
        "ok": True,
        "items": [_order_to_dict(o, user=user) for o in items],
        "page": page,
        "page_size": size,
        "total": total,
    })


@bp.get("")
@api_auth_required
def list_orders():
    user, err = ensure_permissions("orders.read")
    if err:
        return err
    return _list_orders(request.args, user)


@bp.get("/sales")
@api_auth_required
def list_sales_orders():
    user, err = ensure_permissions("orders.read")
    if err:
        return err
    args = request.args.to_dict(flat=True)
    args["type"] = "sales"
    return _list_orders(args, user)


@bp.get("/purchase")
@api_auth_required
def list_purchase_orders():
    user, err = ensure_permissions("orders.read")
    if err:
        return err
    args = request.args.to_dict(flat=True)
    args["type"] = "purchase"
    return _list_orders(args, user)


@bp.post("")
@api_auth_required
def create_order():
    user, err = ensure_permissions("orders.create")
    if err:
        return err
    data = get_json()
    invalid = invalid_payload_fields(data, _ORDER_FIELDS)
    if invalid:
        return invalid
    invalid = _invalid_nested_fields(data)
    if invalid:
        return invalid
    if _has_financial_changes(data):
        _, err = ensure_permissions("orders.financial.update")
        if err:
            return err
    if _has_fulfilment_changes(data):
        _, err = ensure_permissions("orders.fulfil")
        if err:
            return err
    kind = (data.get("kind") or "purchase").strip()
    if kind not in {"purchase", "sales"}:
        return json_error("invalid_kind", "Invalid order type.", 400)
    if not order_kind_allowed(user, kind, "orders.create"):
        return json_error("forbidden", "Permission denied.", 403)
    status = (data.get("status") or "draft").strip()
    if status not in ORDER_STATUS_FLOW:
        return json_error("invalid_status", "Invalid status.", 400)
    if status != "draft":
        _, err = ensure_permissions(order_status_permission(status))
        if err:
            return err
    order_number = (data.get("order_number") or "").strip() or generate_order_number(kind)
    if Order.objects(order_number=order_number).first():
        return json_error("conflict", "Order number already exists.", 409)

    order = Order(
        order_number=order_number,
        description=(data.get("description") or "").strip(),
        kind=kind,
        status=status,
        customer_po=(data.get("customer_po") or "").strip(),
        order_date=parse_datetime_param(data.get("order_date")) or utc_now(),
        requested_delivery=parse_datetime_param(data.get("requested_delivery")),
        promised_delivery=parse_datetime_param(data.get("promised_delivery")),
        actual_delivery=parse_datetime_param(data.get("actual_delivery")),
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
        if not order_relationship_allowed(user, kind, "customer", "orders.create"):
            return json_error("not_found", "Customer not found.", 404)
        order.customer = _related_by_id_or_code(
            user,
            Customer.objects,
            "customers",
            "orders.create",
            cust_id,
            cust_code,
        )
        if not order.customer:
            return json_error("not_found", "Customer not found.", 404)
    sup_id = data.get("supplier_id") or ""
    sup_code = data.get("supplier_code") or ""
    if sup_id or sup_code:
        if not order_relationship_allowed(user, kind, "supplier", "orders.create"):
            return json_error("not_found", "Supplier not found.", 404)
        order.supplier = _related_by_id_or_code(
            user,
            Supplier.objects,
            "suppliers",
            "orders.create",
            sup_id,
            sup_code,
        )
        if not order.supplier:
            return json_error("not_found", "Supplier not found.", 404)
    job_id = data.get("job_id") or ""
    if job_id:
        if not order_relationship_allowed(user, kind, "job", "orders.create"):
            return json_error("not_found", "Job not found.", 404)
        order.job = _scoped_related(
            user,
            Job.objects(is_deleted=False),
            job_id,
            "jobs",
            "orders.create",
        )
        if not order.job:
            return json_error("not_found", "Job not found.", 404)

    order.updated_at = utc_now()
    order.save()
    return jsonify({"ok": True, "order": _order_to_dict(order, user=user)})


@bp.get("/<order_number>")
@api_auth_required
def get_order(order_number):
    user, err = ensure_permissions("orders.read")
    if err:
        return err
    order = _scoped_order(user, order_number, "orders.read")
    if not order:
        return json_error("not_found", "Order not found.", 404)
    return jsonify({"ok": True, "order": _order_to_dict(order, user=user)})


@bp.put("/<order_number>")
@api_auth_required
def update_order(order_number):
    user, err = ensure_permissions("orders.update")
    if err:
        return err
    data = get_json()
    invalid = invalid_payload_fields(data, _ORDER_FIELDS - {"order_number"})
    if invalid:
        return invalid
    invalid = _invalid_nested_fields(data)
    if invalid:
        return invalid
    if _has_financial_changes(data):
        _, err = ensure_permissions("orders.financial.update")
        if err:
            return err
    if _has_fulfilment_changes(data):
        _, err = ensure_permissions("orders.fulfil")
        if err:
            return err
    order = _scoped_order(user, order_number, "orders.update")
    if not order:
        return json_error("not_found", "Order not found.", 404)
    target_kind = (data.get("kind") or order.kind or "purchase").strip()
    if target_kind not in {"purchase", "sales"}:
        return json_error("invalid_kind", "Invalid order type.", 400)
    if not order_kind_allowed(user, target_kind, "orders.update"):
        return json_error("forbidden", "Permission denied.", 403)
    if "status" in data:
        new_status = (data.get("status") or "").strip()
        if new_status not in ORDER_STATUS_FLOW:
            return json_error("invalid_status", "Invalid status.", 400)
        if new_status != order.status:
            _, err = ensure_permissions(order_status_permission(new_status))
            if err:
                return err
            if not can_transition_order(order.status, new_status):
                return json_error(
                    "invalid_transition",
                    "Status transition not allowed.",
                    400,
                )
    for key in (
        "description",
        "kind",
        "status",
        "customer_po",
        "shipping_method",
        "carrier",
        "tracking_number",
        "currency",
    ):
        if key in data:
            setattr(order, key, (data.get(key) or "").strip())
    if "order_date" in data:
        order.order_date = parse_datetime_param(data.get("order_date"))
    if "requested_delivery" in data:
        order.requested_delivery = parse_datetime_param(data.get("requested_delivery"))
    if "promised_delivery" in data:
        order.promised_delivery = parse_datetime_param(data.get("promised_delivery"))
    if "actual_delivery" in data:
        order.actual_delivery = parse_datetime_param(data.get("actual_delivery"))
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
        if not cust_id and not cust_code:
            order.customer = None
        else:
            if not order_relationship_allowed(
                user, target_kind, "customer", "orders.update"
            ):
                return json_error("not_found", "Customer not found.", 404)
            customer = _related_by_id_or_code(
                user,
                Customer.objects,
                "customers",
                "orders.update",
                cust_id,
                cust_code,
            )
            if not customer:
                return json_error("not_found", "Customer not found.", 404)
            order.customer = customer
    if "supplier_id" in data or "supplier_code" in data:
        sup_id = data.get("supplier_id") or ""
        sup_code = data.get("supplier_code") or ""
        if not sup_id and not sup_code:
            order.supplier = None
        else:
            if not order_relationship_allowed(
                user, target_kind, "supplier", "orders.update"
            ):
                return json_error("not_found", "Supplier not found.", 404)
            supplier = _related_by_id_or_code(
                user,
                Supplier.objects,
                "suppliers",
                "orders.update",
                sup_id,
                sup_code,
            )
            if not supplier:
                return json_error("not_found", "Supplier not found.", 404)
            order.supplier = supplier
    if "job_id" in data:
        if not data.get("job_id"):
            order.job = None
        else:
            if not order_relationship_allowed(user, target_kind, "job", "orders.update"):
                return json_error("not_found", "Job not found.", 404)
            job = _scoped_related(
                user,
                Job.objects(is_deleted=False),
                data.get("job_id"),
                "jobs",
                "orders.update",
            )
            if not job:
                return json_error("not_found", "Job not found.", 404)
            order.job = job

    order.updated_at = utc_now()
    order.save()
    return jsonify({"ok": True, "order": _order_to_dict(order, user=user)})


@bp.delete("/<order_number>")
@api_auth_required
def delete_order(order_number):
    user, err = ensure_permissions("orders.archive")
    if err:
        return err
    order = _scoped_order(user, order_number, "orders.archive")
    if not order:
        return json_error("not_found", "Order not found.", 404)
    if order.status not in ("draft", "submitted", "cancelled"):
        return json_error("invalid_state", "Order cannot be deleted in this status.", 400)
    order.status = "cancelled"
    order.updated_at = utc_now()
    order.save()
    return jsonify({"ok": True})


@bp.post("/<order_number>/submit")
@api_auth_required
def order_submit(order_number):
    user, err = ensure_permissions("orders.submit")
    if err:
        return err
    order = _scoped_order(user, order_number, "orders.submit")
    if not order:
        return json_error("not_found", "Order not found.", 404)
    if not can_transition_order(order.status, "submitted"):
        return json_error("invalid_transition", "Status transition not allowed.", 400)
    order.status = "submitted"
    order.updated_at = utc_now()
    order.save()
    return jsonify({"ok": True, "order": _order_to_dict(order, user=user)})


@bp.post("/<order_number>/approve")
@api_auth_required
def order_approve(order_number):
    user, err = ensure_permissions("orders.approve")
    if err:
        return err
    order = _scoped_order(user, order_number, "orders.approve")
    if not order:
        return json_error("not_found", "Order not found.", 404)
    if not can_transition_order(order.status, "confirmed"):
        return json_error("invalid_transition", "Status transition not allowed.", 400)
    order.status = "confirmed"
    order.approved_by = getattr(user, "email", "")
    order.approved_at = utc_now()
    order.updated_at = utc_now()
    order.save()
    return jsonify({"ok": True, "order": _order_to_dict(order, user=user)})


@bp.post("/<order_number>/ship")
@api_auth_required
def order_ship(order_number):
    user, err = ensure_permissions("orders.ship")
    if err:
        return err
    order = _scoped_order(user, order_number, "orders.ship")
    if not order:
        return json_error("not_found", "Order not found.", 404)
    data = get_json()
    invalid = invalid_payload_fields(
        data,
        {"carrier", "tracking_number", "actual_delivery"},
    )
    if invalid:
        return invalid
    if not can_transition_order(order.status, "shipped"):
        return json_error("invalid_transition", "Status transition not allowed.", 400)
    order.status = "shipped"
    order.carrier = (data.get("carrier") or order.carrier or "").strip()
    order.tracking_number = (data.get("tracking_number") or order.tracking_number or "").strip()
    order.actual_delivery = parse_datetime_param(data.get("actual_delivery")) or order.actual_delivery
    order.updated_at = utc_now()
    order.save()
    return jsonify({"ok": True, "order": _order_to_dict(order, user=user)})


@bp.patch("/<order_number>/status")
@api_auth_required
def order_status(order_number):
    data = get_json()
    invalid = invalid_payload_fields(data, {"status"})
    if invalid:
        return invalid
    new_status = (data.get("status") or "").strip()
    if new_status not in ORDER_STATUS_FLOW:
        return json_error("invalid_status", "Invalid status.", 400)
    permission = order_status_permission(new_status)
    user, err = ensure_permissions(permission)
    if err:
        return err
    order = _scoped_order(user, order_number, permission)
    if not order:
        return json_error("not_found", "Order not found.", 404)
    if not can_transition_order(order.status, new_status):
        return json_error("invalid_transition", "Status transition not allowed.", 400)
    order.status = new_status
    order.updated_at = utc_now()
    order.save()
    return jsonify({"ok": True, "order": _order_to_dict(order, user=user)})


@bp.get("/stats")
@api_auth_required
def order_stats():
    user, err = ensure_permissions("orders.read")
    if err:
        return err
    base = scope_queryset(Order.objects, user, "orders")
    financial = has_permission(user, "orders.financial.read")
    month_start = utc_now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month = base.filter(order_date__gte=month_start)
    count = base.count()
    total_value = float(base.sum("total") or 0.0) if financial else None
    return jsonify(
        filter_response_fields(
            "order_stats",
            user,
            {
                "ok": True,
                "status_counts": {
                    status: base.filter(status=status).count()
                    for status in ORDER_STATUS_FLOW
                },
                "revenue_month": (
                    float(month.sum("total") or 0.0) if financial else None
                ),
                "avg_order_value": (
                    (total_value / count)
                    if financial and count
                    else (0.0 if financial else None)
                ),
            },
            context={
                "policy_context": response_context("orders", user),
                "preserve_null_fields": {"revenue_month", "avg_order_value"},
            },
        )
    )


@bp.get("/dashboard")
@api_auth_required
def order_dashboard():
    user, err = ensure_permissions("orders.read")
    if err:
        return err
    base = scope_queryset(Order.objects, user, "orders")
    recent = base.order_by("-order_date").limit(10)
    pending = base.filter(status__in=["draft", "submitted"]).order_by("-order_date").limit(10)
    return jsonify({
        "ok": True,
        "recent": [
            _order_to_dict(o, user=user)
            for o in recent
        ],
        "pending": [
            _order_to_dict(o, user=user)
            for o in pending
        ],
    })

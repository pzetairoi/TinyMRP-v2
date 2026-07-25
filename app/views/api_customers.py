from __future__ import annotations

from typing import List

from flask import Blueprint, jsonify, request
from mongoengine.queryset.visitor import Q

from app.models.customer import Customer
from app.models.order import Order
from app.models.common import Contact, Address
from app.services.api_auth import api_auth_required
from app.services.authorization import authorised_get, has_permission, scope_queryset
from app.services.biz_utils import generate_customer_code
from app.views.api_helpers import json_error, ensure_permissions, parse_pagination, iso, get_json

bp = Blueprint("customers_api", __name__, url_prefix="/api/customers")


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


def _parse_contacts(items) -> List[Contact]:
    out = []
    for raw in items or []:
        name = (raw.get("name") or "").strip()
        if not name:
            continue
        out.append(Contact(
            name=name,
            title=raw.get("title") or "",
            email=raw.get("email") or "",
            phone=raw.get("phone") or "",
            is_primary=bool(raw.get("is_primary")),
        ))
    return out


_CUSTOMER_FIELDS = {
    "code",
    "name",
    "description",
    "is_company",
    "status",
    "customer_type",
    "segment",
    "tags",
    "contact",
    "email",
    "website",
    "phone",
    "billing_address",
    "shipping_addresses",
    "default_shipping_label",
    "tax_id",
    "payment_terms",
    "credit_limit",
    "discount_pct",
    "currency",
    "sales_rep",
    "industry",
    "contacts",
}
_CUSTOMER_FINANCIAL_FIELDS = {
    "billing_address",
    "tax_id",
    "payment_terms",
    "credit_limit",
    "discount_pct",
    "currency",
    "customer_type",
    "segment",
    "sales_rep",
    "industry",
}


def _invalid_payload_fields(data, allowed):
    invalid = sorted(set(data) - set(allowed))
    if invalid:
        return json_error(
            "invalid_fields",
            f"Unsupported fields: {', '.join(invalid)}.",
            400,
        )
    return None


def _scoped_customer(user, code, permission):
    customer = authorised_get(
        Customer.objects,
        user,
        code,
        resource_type="customers",
        identifier_field="code",
        permission=permission,
    )
    if customer:
        return customer
    return authorised_get(
        Customer.objects,
        user,
        code,
        resource_type="customers",
        permission=permission,
    )


def _customer_to_dict(c: Customer, *, include_financial=True):
    return {
        "code": c.code,
        "name": c.name,
        "description": c.description,
        "is_company": bool(c.is_company),
        "status": c.status,
        "customer_type": c.customer_type if include_financial else None,
        "segment": c.segment if include_financial else None,
        "tags": c.tags or [],
        "primary_contact": c.contact or "",
        "email": c.email,
        "website": c.website,
        "phone": c.phone,
        "billing_address": (
            c.billing_address.to_mongo()
            if include_financial and c.billing_address
            else None
        ),
        "shipping_addresses": [a.to_mongo() for a in (c.shipping_addresses or [])],
        "default_shipping_label": c.default_shipping_label,
        "tax_id": c.tax_id if include_financial else None,
        "payment_terms": c.payment_terms if include_financial else None,
        "credit_limit": c.credit_limit if include_financial else None,
        "discount_pct": c.discount_pct if include_financial else None,
        "currency": c.currency if include_financial else None,
        "sales_rep": c.sales_rep if include_financial else None,
        "industry": c.industry if include_financial else None,
        "contacts": [ct.to_mongo() for ct in (c.contacts or [])],
    }


@bp.get("")
@api_auth_required
def list_customers():
    user, err = ensure_permissions("customers.read")
    if err:
        return err
    page, size = parse_pagination()
    q = scope_queryset(Customer.objects, user, "customers")
    status = request.args.get("status")
    if status:
        q = q.filter(status__in=[s.strip() for s in status.split(",") if s.strip()])
    cust_type = request.args.get("type")
    if cust_type:
        if not has_permission(user, "customers.financial.read"):
            return json_error("forbidden", "Permission denied.", 403)
        q = q.filter(customer_type=cust_type)
    q_text = request.args.get("q")
    if q_text:
        q = q.filter(Q(name__icontains=q_text) | Q(code__icontains=q_text))

    sort = request.args.get("sort", "name")
    if sort == "customer_type" and not has_permission(
        user,
        "customers.financial.read",
    ):
        return json_error("forbidden", "Permission denied.", 403)
    direction = request.args.get("direction", "asc").lower()
    sort_key = "name" if sort not in ("name", "status", "customer_type") else sort
    if direction == "desc":
        sort_key = "-" + sort_key

    total = q.count()
    items = q.order_by(sort_key).skip((page - 1) * size).limit(size)
    financial = has_permission(user, "customers.financial.read")
    return jsonify({
        "ok": True,
        "items": [_customer_to_dict(c, include_financial=financial) for c in items],
        "page": page,
        "page_size": size,
        "total": total,
    })


@bp.post("")
@api_auth_required
def create_customer():
    user, err = ensure_permissions("customers.update")
    if err:
        return err
    data = get_json()
    invalid = _invalid_payload_fields(data, _CUSTOMER_FIELDS)
    if invalid:
        return invalid
    if set(data) & _CUSTOMER_FINANCIAL_FIELDS:
        _, err = ensure_permissions("customers.financial.update")
        if err:
            return err
    name = (data.get("name") or "").strip()
    if not name:
        return json_error("missing_name", "Customer name is required.")
    if Customer.objects(name=name).first():
        return json_error("conflict", "Customer already exists.", 409)
    code = (data.get("code") or "").strip() or generate_customer_code()
    c = Customer(
        code=code,
        name=name,
        description=(data.get("description") or "").strip(),
        is_company=bool(data.get("is_company", True)),
        status=(data.get("status") or "active").strip(),
        customer_type=(data.get("customer_type") or "oem").strip(),
        segment=(data.get("segment") or "").strip(),
        tags=data.get("tags") or [],
        contact=(data.get("contact") or "").strip(),
        email=(data.get("email") or "").strip(),
        website=(data.get("website") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        billing_address=_parse_address(data.get("billing_address")),
        shipping_addresses=[_parse_address(a) for a in (data.get("shipping_addresses") or []) if a],
        default_shipping_label=(data.get("default_shipping_label") or "").strip(),
        tax_id=(data.get("tax_id") or "").strip(),
        payment_terms=(data.get("payment_terms") or "").strip(),
        credit_limit=data.get("credit_limit"),
        discount_pct=data.get("discount_pct"),
        currency=(data.get("currency") or "USD").strip(),
        sales_rep=(data.get("sales_rep") or "").strip(),
        industry=(data.get("industry") or "").strip(),
        contacts=_parse_contacts(data.get("contacts") or []),
    )
    c.save()
    return jsonify({
        "ok": True,
        "customer": _customer_to_dict(
            c,
            include_financial=has_permission(user, "customers.financial.read"),
        ),
    })


@bp.get("/<code>")
@api_auth_required
def get_customer(code):
    user, err = ensure_permissions("customers.read")
    if err:
        return err
    c = _scoped_customer(user, code, "customers.read")
    if not c:
        return json_error("not_found", "Customer not found.", 404)
    return jsonify({
        "ok": True,
        "customer": _customer_to_dict(
            c,
            include_financial=has_permission(user, "customers.financial.read"),
        ),
    })


@bp.put("/<code>")
@api_auth_required
def update_customer(code):
    user, err = ensure_permissions("customers.update")
    if err:
        return err
    c = _scoped_customer(user, code, "customers.update")
    if not c:
        return json_error("not_found", "Customer not found.", 404)
    data = get_json()
    invalid = _invalid_payload_fields(data, _CUSTOMER_FIELDS - {"code"})
    if invalid:
        return invalid
    if set(data) & _CUSTOMER_FINANCIAL_FIELDS:
        _, err = ensure_permissions("customers.financial.update")
        if err:
            return err
    for key in ("name", "description", "status", "customer_type", "segment", "contact", "email", "website", "phone", "tax_id", "payment_terms", "currency", "sales_rep", "industry"):
        if key in data:
            setattr(c, key, (data.get(key) or "").strip())
    if "is_company" in data:
        c.is_company = bool(data.get("is_company"))
    if "tags" in data:
        c.tags = data.get("tags") or []
    if "credit_limit" in data:
        c.credit_limit = data.get("credit_limit")
    if "discount_pct" in data:
        c.discount_pct = data.get("discount_pct")
    if "billing_address" in data:
        c.billing_address = _parse_address(data.get("billing_address"))
    if "shipping_addresses" in data:
        c.shipping_addresses = [_parse_address(a) for a in (data.get("shipping_addresses") or []) if a]
    if "default_shipping_label" in data:
        c.default_shipping_label = (data.get("default_shipping_label") or "").strip()
    if "contacts" in data:
        c.contacts = _parse_contacts(data.get("contacts") or [])
    c.save()
    return jsonify({
        "ok": True,
        "customer": _customer_to_dict(
            c,
            include_financial=has_permission(user, "customers.financial.read"),
        ),
    })


@bp.post("/<code>/shipping-addresses")
@api_auth_required
def add_shipping_address(code):
    user, err = ensure_permissions("customers.update", "customers.financial.update")
    if err:
        return err
    c = _scoped_customer(user, code, "customers.update")
    if not c:
        return json_error("not_found", "Customer not found.", 404)
    data = get_json()
    invalid = _invalid_payload_fields(
        data,
        {
            "label",
            "line1",
            "line2",
            "city",
            "state",
            "postal",
            "country",
            "is_default",
        },
    )
    if invalid:
        return invalid
    addr = _parse_address(data)
    if not addr:
        return json_error("missing_address", "Address payload required.")
    c.shipping_addresses.append(addr)
    c.save()
    return jsonify({
        "ok": True,
        "customer": _customer_to_dict(
            c,
            include_financial=has_permission(user, "customers.financial.read"),
        ),
    })


@bp.get("/<code>/orders")
@api_auth_required
def customer_orders(code):
    user, err = ensure_permissions("customers.read", "orders.read")
    if err:
        return err
    c = _scoped_customer(user, code, "customers.read")
    if not c:
        return json_error("not_found", "Customer not found.", 404)
    orders = (
        scope_queryset(Order.objects(customer=c), user, "orders")
        .order_by("-order_date")
        .limit(50)
    )
    financial = has_permission(user, "orders.financial.read")
    return jsonify({
        "ok": True,
        "orders": [
            {
                "order_number": o.order_number,
                "status": o.status,
                "total": o.total if financial else None,
                "order_date": iso(o.order_date),
            }
            for o in orders
        ]
    })


@bp.get("/<code>/stats")
@api_auth_required
def customer_stats(code):
    user, err = ensure_permissions("customers.read", "orders.read")
    if err:
        return err
    c = _scoped_customer(user, code, "customers.read")
    if not c:
        return json_error("not_found", "Customer not found.", 404)
    orders = scope_queryset(Order.objects(customer=c), user, "orders")
    total = orders.count()
    financial = has_permission(user, "orders.financial.read")
    revenue = float(orders.sum("total") or 0.0) if financial else None
    last = orders.order_by("-order_date").first()
    return jsonify({
        "ok": True,
        "orders_count": total,
        "total_revenue": revenue,
        "last_order_date": iso(last.order_date) if last else None,
    })


@bp.get("/dashboard")
@api_auth_required
def customer_dashboard():
    user, err = ensure_permissions("customers.read")
    if err:
        return err
    recent = scope_queryset(Customer.objects, user, "customers").order_by("-id").limit(10)
    financial = has_permission(user, "customers.financial.read")
    return jsonify({
        "ok": True,
        "recent": [
            _customer_to_dict(c, include_financial=financial)
            for c in recent
        ],
    })

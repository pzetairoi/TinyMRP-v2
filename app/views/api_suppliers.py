from __future__ import annotations

from typing import List

from flask import Blueprint, jsonify, request
from mongoengine.queryset.visitor import Q

from app.models.supplier import Supplier
from app.models.part import Part
from app.models.order import Order
from app.models.common import Contact, Address
from app.services.api_auth import api_auth_required
from app.services.authorization import authorised_get, has_permission, scope_queryset
from app.services.attrs import harvest_part_attrs
from app.services.biz_utils import generate_supplier_code
from app.views.api_helpers import json_error, ensure_permissions, parse_pagination, iso, get_json

bp = Blueprint("suppliers_api", __name__, url_prefix="/api/suppliers")


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


_SUPPLIER_FIELDS = {
    "code",
    "name",
    "description",
    "status",
    "rating",
    "tags",
    "categories",
    "contact",
    "email",
    "phone",
    "website",
    "tax_id",
    "payment_terms",
    "currency",
    "min_order_value",
    "lead_time_days",
    "address",
    "billing_address",
    "contacts",
    "processes",
}
_SUPPLIER_FINANCIAL_FIELDS = {
    "rating",
    "tax_id",
    "payment_terms",
    "currency",
    "min_order_value",
    "billing_address",
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


def _scoped_supplier(user, code, permission):
    supplier = authorised_get(
        Supplier.objects,
        user,
        code,
        resource_type="suppliers",
        identifier_field="code",
        permission=permission,
    )
    if supplier:
        return supplier
    return authorised_get(
        Supplier.objects,
        user,
        code,
        resource_type="suppliers",
        permission=permission,
    )


def _supplier_to_dict(s: Supplier, *, include_financial=True):
    return {
        "code": s.code,
        "name": s.name,
        "description": s.description,
        "status": s.status,
        "rating": s.rating if include_financial else None,
        "tags": s.tags or [],
        "categories": s.categories or [],
        "primary_contact": s.contact or "",
        "email": s.email,
        "phone": s.phone,
        "website": s.website,
        "tax_id": s.tax_id if include_financial else None,
        "payment_terms": s.payment_terms if include_financial else None,
        "currency": s.currency if include_financial else None,
        "min_order_value": s.min_order_value if include_financial else None,
        "lead_time_days": s.lead_time_days,
        "address": s.address.to_mongo() if s.address else None,
        "billing_address": (
            s.billing_address.to_mongo()
            if include_financial and s.billing_address
            else None
        ),
        "contacts": [c.to_mongo() for c in (s.contacts or [])],
        "created_at": None,
    }


@bp.get("")
@api_auth_required
def list_suppliers():
    user, err = ensure_permissions("suppliers.read")
    if err:
        return err
    page, size = parse_pagination()
    q = scope_queryset(Supplier.objects, user, "suppliers")
    status = request.args.get("status")
    if status:
        q = q.filter(status__in=[s.strip() for s in status.split(",") if s.strip()])
    category = request.args.get("category")
    if category:
        q = q.filter(categories__in=[category])
    rating = request.args.get("rating")
    if rating:
        if not has_permission(user, "suppliers.financial.read"):
            return json_error("forbidden", "Permission denied.", 403)
        try:
            q = q.filter(rating=int(rating))
        except Exception:
            pass
    q_text = request.args.get("q")
    if q_text:
        q = q.filter(Q(name__icontains=q_text) | Q(code__icontains=q_text))

    sort = request.args.get("sort", "name")
    if sort == "rating" and not has_permission(user, "suppliers.financial.read"):
        return json_error("forbidden", "Permission denied.", 403)
    direction = request.args.get("direction", "asc").lower()
    sort_key = "name" if sort not in ("name", "rating", "status") else sort
    if direction == "desc":
        sort_key = "-" + sort_key

    total = q.count()
    items = q.order_by(sort_key).skip((page - 1) * size).limit(size)
    financial = has_permission(user, "suppliers.financial.read")
    return jsonify({
        "ok": True,
        "items": [_supplier_to_dict(s, include_financial=financial) for s in items],
        "page": page,
        "page_size": size,
        "total": total,
    })


@bp.post("")
@api_auth_required
def create_supplier():
    user, err = ensure_permissions("suppliers.update")
    if err:
        return err
    data = get_json()
    invalid = _invalid_payload_fields(data, _SUPPLIER_FIELDS)
    if invalid:
        return invalid
    if set(data) & _SUPPLIER_FINANCIAL_FIELDS:
        _, err = ensure_permissions("suppliers.financial.update")
        if err:
            return err
    name = (data.get("name") or "").strip()
    if not name:
        return json_error("missing_name", "Supplier name is required.")
    if Supplier.objects(name=name).first():
        return json_error("conflict", "Supplier already exists.", 409)
    code = (data.get("code") or "").strip() or generate_supplier_code()
    s = Supplier(
        code=code,
        name=name,
        description=(data.get("description") or "").strip(),
        status=(data.get("status") or "active").strip(),
        rating=data.get("rating"),
        tags=data.get("tags") or [],
        categories=data.get("categories") or [],
        contact=(data.get("contact") or "").strip(),
        email=(data.get("email") or "").strip(),
        phone=(data.get("phone") or "").strip(),
        website=(data.get("website") or "").strip(),
        tax_id=(data.get("tax_id") or "").strip(),
        payment_terms=(data.get("payment_terms") or "").strip(),
        currency=(data.get("currency") or "USD").strip(),
        min_order_value=data.get("min_order_value"),
        lead_time_days=data.get("lead_time_days"),
        address=_parse_address(data.get("address")),
        billing_address=_parse_address(data.get("billing_address")),
        contacts=_parse_contacts(data.get("contacts") or []),
        processes=data.get("processes") or [],
    )
    s.save()
    return jsonify({
        "ok": True,
        "supplier": _supplier_to_dict(
            s,
            include_financial=has_permission(user, "suppliers.financial.read"),
        ),
    })


@bp.get("/<code>")
@api_auth_required
def get_supplier(code):
    user, err = ensure_permissions("suppliers.read")
    if err:
        return err
    s = _scoped_supplier(user, code, "suppliers.read")
    if not s:
        return json_error("not_found", "Supplier not found.", 404)
    return jsonify({
        "ok": True,
        "supplier": _supplier_to_dict(
            s,
            include_financial=has_permission(user, "suppliers.financial.read"),
        ),
    })


@bp.put("/<code>")
@api_auth_required
def update_supplier(code):
    user, err = ensure_permissions("suppliers.update")
    if err:
        return err
    s = _scoped_supplier(user, code, "suppliers.update")
    if not s:
        return json_error("not_found", "Supplier not found.", 404)
    data = get_json()
    invalid = _invalid_payload_fields(data, _SUPPLIER_FIELDS - {"code"})
    if invalid:
        return invalid
    if set(data) & _SUPPLIER_FINANCIAL_FIELDS:
        _, err = ensure_permissions("suppliers.financial.update")
        if err:
            return err
    for key in ("name", "description", "status", "contact", "email", "phone", "website", "tax_id", "payment_terms", "currency"):
        if key in data:
            setattr(s, key, (data.get(key) or "").strip())
    if "rating" in data:
        s.rating = data.get("rating")
    if "tags" in data:
        s.tags = data.get("tags") or []
    if "categories" in data:
        s.categories = data.get("categories") or []
    if "min_order_value" in data:
        s.min_order_value = data.get("min_order_value")
    if "lead_time_days" in data:
        s.lead_time_days = data.get("lead_time_days")
    if "address" in data:
        s.address = _parse_address(data.get("address"))
    if "billing_address" in data:
        s.billing_address = _parse_address(data.get("billing_address"))
    if "contacts" in data:
        s.contacts = _parse_contacts(data.get("contacts") or [])
    if "processes" in data:
        s.processes = data.get("processes") or []
    s.save()
    return jsonify({
        "ok": True,
        "supplier": _supplier_to_dict(
            s,
            include_financial=has_permission(user, "suppliers.financial.read"),
        ),
    })


@bp.patch("/<code>/status")
@api_auth_required
def supplier_status(code):
    user, err = ensure_permissions("suppliers.update")
    if err:
        return err
    s = _scoped_supplier(user, code, "suppliers.update")
    if not s:
        return json_error("not_found", "Supplier not found.", 404)
    data = get_json()
    invalid = _invalid_payload_fields(data, {"status"})
    if invalid:
        return invalid
    status = (data.get("status") or "").strip()
    if status not in ("active", "inactive", "pending", "blacklisted"):
        return json_error("invalid_status", "Invalid status.", 400)
    s.status = status
    s.save()
    return jsonify({
        "ok": True,
        "supplier": _supplier_to_dict(
            s,
            include_financial=has_permission(user, "suppliers.financial.read"),
        ),
    })


@bp.get("/<code>/orders")
@api_auth_required
def supplier_orders(code):
    user, err = ensure_permissions("suppliers.read", "orders.read")
    if err:
        return err
    s = _scoped_supplier(user, code, "suppliers.read")
    if not s:
        return json_error("not_found", "Supplier not found.", 404)
    orders = (
        scope_queryset(Order.objects(supplier=s), user, "orders")
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


@bp.get("/<code>/parts")
@api_auth_required
def supplier_parts(code):
    user, err = ensure_permissions("suppliers.read")
    if err:
        return err
    s = _scoped_supplier(user, code, "suppliers.read")
    if not s:
        return json_error("not_found", "Supplier not found.", 404)
    name = (s.name or "").strip()
    sup_code = (s.code or "").strip()
    filters = Q()
    for key in ("supplier", "supplier_name", "oem_supplier", "vendor", "vendor_name", "supplier_code"):
        if name:
            filters |= Q(**{f"attrs__{key}__iexact": name})
        if sup_code:
            filters |= Q(**{f"attrs__{key}__iexact": sup_code})
    if not filters:
        return jsonify({"ok": True, "items": []})
    parts = Part.objects(filters).only("part_number", "revision", "description", "category", "uom", "attrs")[:200]
    items = []
    for p in parts:
        attrs = harvest_part_attrs(p)
        items.append({
            "part_number": p.part_number,
            "revision": attrs.get("revision", "") or p.revision or "",
            "description": attrs.get("description") or p.description or "",
            "category": attrs.get("category") or p.category or "",
            "uom": p.uom or "EA",
        })
    return jsonify({"ok": True, "items": items})


@bp.get("/<code>/performance")
@api_auth_required
def supplier_performance(code):
    user, err = ensure_permissions("suppliers.read", "orders.read")
    if err:
        return err
    s = _scoped_supplier(user, code, "suppliers.read")
    if not s:
        return json_error("not_found", "Supplier not found.", 404)
    orders = scope_queryset(Order.objects(supplier=s), user, "orders")
    total = orders.count()
    on_time = 0
    avg_lead = 0.0
    for o in orders:
        if o.promised_delivery and o.actual_delivery:
            if o.actual_delivery <= o.promised_delivery:
                on_time += 1
            avg_lead += (o.actual_delivery - o.order_date).days if o.order_date else 0
    return jsonify({
        "ok": True,
        "on_time_rate": (on_time / total) if total else None,
        "avg_lead_days": (avg_lead / total) if total else None,
        "orders_count": total,
    })

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Tuple

from mongoengine.errors import DoesNotExist

from app.models.job import Job
from app.models.supplier import Supplier
from app.models.customer import Customer
from app.models.order import Order, OrderLine
from app.services.timezone_utils import utc_now


def safe_ref(doc, field: str):
    """Dereference a ReferenceField, returning None if the target document was deleted."""
    try:
        return getattr(doc, field)
    except DoesNotExist:
        return None


JOB_STATUS_FLOW = {
    "draft": {"released", "cancelled"},
    "released": {"in_progress", "on_hold", "cancelled"},
    "in_progress": {"on_hold", "completed", "cancelled"},
    "on_hold": {"in_progress", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

ORDER_STATUS_FLOW = {
    "draft": {"submitted", "cancelled"},
    "submitted": {"confirmed", "cancelled"},
    "confirmed": {"in_production", "ready_to_ship", "cancelled"},
    "in_production": {"ready_to_ship", "cancelled"},
    "ready_to_ship": {"shipped", "cancelled"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}


def generate_job_number(now: datetime | None = None) -> str:
    now = now or utc_now()
    date_tag = now.strftime("%Y%m%d")
    prefix = f"JOB-{date_tag}-"
    last = Job.objects(job_number__startswith=prefix).order_by("-job_number").first()
    seq = 1
    if last and last.job_number:
        try:
            seq = int(last.job_number.split("-")[-1]) + 1
        except Exception:
            seq = 1
    return f"{prefix}{seq:03d}"


def generate_supplier_code() -> str:
    prefix = "SUPP-"
    last = Supplier.objects(code__startswith=prefix).order_by("-code").first()
    seq = 1
    if last and last.code:
        try:
            seq = int(last.code.split("-")[-1]) + 1
        except Exception:
            seq = 1
    return f"{prefix}{seq:03d}"


def generate_customer_code() -> str:
    prefix = "CUST-"
    last = Customer.objects(code__startswith=prefix).order_by("-code").first()
    seq = 1
    if last and last.code:
        try:
            seq = int(last.code.split("-")[-1]) + 1
        except Exception:
            seq = 1
    return f"{prefix}{seq:03d}"


def generate_order_number(kind: str, now: datetime | None = None) -> str:
    now = now or utc_now()
    year = now.strftime("%Y")
    kind = (kind or "").lower().strip()
    prefix = "SO" if kind in ("sales", "sale", "sales_order") else "PO"
    key = f"{prefix}-{year}-"
    last = Order.objects(order_number__startswith=key).order_by("-order_number").first()
    seq = 1
    if last and last.order_number:
        try:
            seq = int(last.order_number.split("-")[-1]) + 1
        except Exception:
            seq = 1
    return f"{key}{seq:03d}"


def order_status_permission(status: str) -> str:
    """Permission required to move an order into ``status``.

    Shared so the admin forms and the JSON API cannot drift into enforcing
    different authority for the same transition.
    """

    return {
        "submitted": "orders.submit",
        "confirmed": "orders.approve",
        "in_production": "orders.fulfil",
        "ready_to_ship": "orders.fulfil",
        "shipped": "orders.ship",
        "delivered": "orders.fulfil",
        "cancelled": "orders.cancel",
    }.get(status, "orders.update")


def can_transition_job(old: str, new: str) -> bool:
    return new in JOB_STATUS_FLOW.get(old or "", set())


def can_transition_order(old: str, new: str) -> bool:
    return new in ORDER_STATUS_FLOW.get(old or "", set())


def calculate_order_totals(lines: Iterable[OrderLine]) -> Tuple[float, float, float]:
    subtotal = 0.0
    tax_total = 0.0
    discount_total = 0.0
    for line in lines or []:
        qty = float(line.qty or 0.0)
        unit = float(line.unit_price or 0.0)
        disc = float(line.discount_pct or 0.0)
        tax = float(line.tax_pct or 0.0)
        base = qty * unit
        discount_amt = base * (disc / 100.0)
        taxable = max(base - discount_amt, 0.0)
        tax_amt = taxable * (tax / 100.0)
        total = taxable + tax_amt
        line.line_total = total
        subtotal += base
        discount_total += discount_amt
        tax_total += tax_amt
    return subtotal, tax_total, discount_total


def supplies_job_requirement(order) -> bool:
    """Whether an order linked to a job covers that job's requirement.

    A job's BOM explosion is demand, and only procurement covers demand. The
    sales order a job is built for is the same demand seen from the customer
    side, so counting it as coverage reported every part in the tree as already
    bought. Anything not explicitly sales is a purchase, matching the model
    default so legacy rows without a kind still count.
    """

    return str(getattr(order, "kind", "") or "purchase").strip().lower() != "sales"


def consolidate_order_lines(lines: Iterable[OrderLine]) -> list[OrderLine]:
    merged: dict[tuple[str, str], OrderLine] = {}
    for line in lines or []:
        pn = (line.pn or "").strip()
        rev = (line.rev or "").strip()
        if not pn:
            continue
        key = (pn.lower(), rev.lower())
        if key not in merged:
            merged[key] = OrderLine(
                pn=pn,
                rev=rev,
                qty=float(line.qty or 0.0),
                uom=(line.uom or "EA").strip(),
                note=(line.note or "").strip(),
                description=(line.description or "").strip(),
                unit_price=float(line.unit_price or 0.0),
                discount_pct=float(line.discount_pct or 0.0),
                tax_pct=float(line.tax_pct or 0.0),
                qty_shipped=float(getattr(line, "qty_shipped", 0.0) or 0.0),
                qty_received=float(getattr(line, "qty_received", 0.0) or 0.0),
                requested_delivery=getattr(line, "requested_delivery", None),
            )
            continue
        merged_line = merged[key]
        merged_line.qty = float(merged_line.qty or 0.0) + float(line.qty or 0.0)
        if not merged_line.uom and line.uom:
            merged_line.uom = (line.uom or "").strip()
        if not merged_line.description and line.description:
            merged_line.description = (line.description or "").strip()
        if not merged_line.unit_price and line.unit_price:
            merged_line.unit_price = float(line.unit_price or 0.0)
        if not merged_line.discount_pct and line.discount_pct:
            merged_line.discount_pct = float(line.discount_pct or 0.0)
        if not merged_line.tax_pct and line.tax_pct:
            merged_line.tax_pct = float(line.tax_pct or 0.0)
        merged_line.qty_shipped = float(merged_line.qty_shipped or 0.0) + float(getattr(line, "qty_shipped", 0.0) or 0.0)
        merged_line.qty_received = float(merged_line.qty_received or 0.0) + float(getattr(line, "qty_received", 0.0) or 0.0)
        if getattr(line, "requested_delivery", None) and not merged_line.requested_delivery:
            merged_line.requested_delivery = getattr(line, "requested_delivery", None)
        note = (line.note or "").strip()
        if note and note not in (merged_line.note or ""):
            merged_line.note = (merged_line.note + " | " + note).strip(" |")
    return list(merged.values())

from __future__ import annotations

import re
import secrets
from typing import List

from flask_security import hash_password

from app.models.auth import User, Role
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.job import Job, JobBOMLine
from app.models.order import Order, OrderLine
from app.models.part import Part
from app.models.bom import BOMLink
from app.models.api_token import ApiToken
from app.models.user_settings import UserSettings
from app.services.biz_utils import calculate_order_totals
from app.services.standard_roles import STANDARD_ROLE_SLUGS
from app.services.timezone_utils import utc_now


DEMO_CUSTOMERS = [
    ("DEMO-CUST-A", "Outback Hire Fleet (Demo)"),
    ("DEMO-CUST-B", "Coastal Trailer Service (Demo)"),
    ("DEMO-CUST-OTHER", "Isolation Customer (Demo)"),
]
DEMO_SUPPLIERS = [
    ("DEMO-SUP-X", "Frame & Fabrication Works (Demo)"),
    ("DEMO-SUP-Y", "Running Gear Supply (Demo)"),
    ("DEMO-SUP-E", "ADR Electrical & Compliance (Demo)"),
    ("DEMO-SUP-OTHER", "Powder Coat & Finish (Demo)"),
]
DEMO_JOBS = [
    ("DEMO-JOB-A1", "DEMO-CUST-A", ["DEMO-SUP-X", "DEMO-SUP-Y", "DEMO-SUP-E", "DEMO-SUP-OTHER"]),
    ("DEMO-JOB-B1", "DEMO-CUST-B", ["DEMO-SUP-Y", "DEMO-SUP-E"]),
    ("DEMO-JOB-O1", "DEMO-CUST-OTHER", ["DEMO-SUP-OTHER"]),
]
DEMO_ORDERS = [
    ("DEMO-PO-X1", "purchase", None, "DEMO-SUP-X", "DEMO-JOB-A1"),
    ("DEMO-PO-Y1", "purchase", None, "DEMO-SUP-Y", "DEMO-JOB-A1"),
    ("DEMO-PO-E1", "purchase", None, "DEMO-SUP-E", "DEMO-JOB-A1"),
    ("DEMO-SO-A1", "sales", "DEMO-CUST-A", None, "DEMO-JOB-A1"),
    ("DEMO-SO-B1", "sales", "DEMO-CUST-B", None, "DEMO-JOB-B1"),
    ("DEMO-PO-O1", "purchase", None, "DEMO-SUP-OTHER", "DEMO-JOB-O1"),
]
DEMO_PARTS = [
    ("DEMO-ASM-1", "A", "Demo Assembly 1", "Assembly"),
    ("DEMO-ASM-2", "A", "Demo Assembly 2", "Assembly"),
    ("DEMO-CMP-A", "A", "Demo Component A", "Component"),
    ("DEMO-CMP-B", "A", "Demo Component B", "Component"),
    ("DEMO-SUB-1", "A", "Demo Subassembly 1", "Subassembly"),
    ("DEMO-SUB-2", "A", "Demo Subassembly 2", "Subassembly"),
    ("DEMO-RAW-1", "A", "Demo Raw 1", "Material"),
    ("DEMO-RAW-2", "A", "Demo Raw 2", "Material"),
]
DEMO_BOM = [
    ("DEMO-ASM-1", "A", "DEMO-CMP-A", "A", 2.0),
    ("DEMO-ASM-1", "A", "DEMO-SUB-1", "A", 1.0),
    ("DEMO-SUB-1", "A", "DEMO-RAW-1", "A", 3.0),
    ("DEMO-ASM-2", "A", "DEMO-CMP-B", "A", 2.0),
    ("DEMO-ASM-2", "A", "DEMO-SUB-2", "A", 1.0),
    ("DEMO-SUB-2", "A", "DEMO-RAW-2", "A", 3.0),
]

DEMO_USER_DISPLAY_NAMES = {
    "customer": "Alex Fleet (Customer)",
    "customer_spares": "Casey Service (Customer)",
    "customer_unreleased": "Morgan External Release Reviewer",
    "supplier": "Fran Fabrication (Supplier)",
    "supplier_unreleased": "Taylor Fabrication Release Reviewer",
    "supplier_running_gear": "Riley Gear (Supplier)",
    "supplier_electrical": "Emery Compliance (Supplier)",
    "supplier_finish": "Parker Finish (Supplier)",
    "engineering": "Erin Design Engineer",
    "engineering_manager": "Morgan Engineering Manager",
    "workshop": "Wes Workshop Lead",
    "commercial": "Sam Commercial Coordinator",
}

DEMO_CUSTOMER_PROFILES = {
    "DEMO-CUST-A": {
        "description": "Fleet buyer ordering complete CELLV03 trailers.",
        "customer_type": "wholesale",
        "segment": "fleet",
        "tags": ["demo", "complete-units"],
        "contact": "Alex Fleet",
        "email": "fleet@example.invalid",
        "payment_terms": "NET30",
        "currency": "AUD",
        "industry": "equipment-hire",
    },
    "DEMO-CUST-B": {
        "description": "Service customer ordering replacement trailer parts.",
        "customer_type": "distributor",
        "segment": "service-and-spares",
        "tags": ["demo", "spare-parts"],
        "contact": "Casey Service",
        "email": "service@example.invalid",
        "payment_terms": "NET14",
        "currency": "AUD",
        "industry": "trailer-service",
    },
    "DEMO-CUST-OTHER": {
        "description": "Unlinked isolation record for RLS negative tests.",
        "customer_type": "retail",
        "segment": "isolation-test",
        "tags": ["demo", "rls-isolation"],
        "currency": "AUD",
    },
}

DEMO_SUPPLIER_PROFILES = {
    "DEMO-SUP-X": {
        "description": "Welded trailer frames and fabricated steel components.",
        "categories": ["fabrication", "frames"],
        "processes": ["welding", "fabrication"],
        "contact": "Fran Fabrication",
        "email": "frames@example.invalid",
        "payment_terms": "NET30",
        "currency": "AUD",
        "lead_time_days": 15,
        "rating": 5,
    },
    "DEMO-SUP-Y": {
        "description": "Suspension, hitch, jockey wheel and running-gear supplier.",
        "categories": ["running-gear", "purchased-parts"],
        "processes": ["purchase"],
        "contact": "Riley Gear",
        "email": "runninggear@example.invalid",
        "payment_terms": "NET30",
        "currency": "AUD",
        "lead_time_days": 7,
        "rating": 4,
    },
    "DEMO-SUP-E": {
        "description": "ADR lighting, reflectors and compliance hardware.",
        "categories": ["electrical", "adr-compliance"],
        "processes": ["purchase", "electrical"],
        "contact": "Emery Compliance",
        "email": "adr@example.invalid",
        "payment_terms": "NET14",
        "currency": "AUD",
        "lead_time_days": 5,
        "rating": 5,
    },
    "DEMO-SUP-OTHER": {
        "description": "Powder coating and final protective finish.",
        "categories": ["coating", "finishing"],
        "processes": ["powdercoat", "spray"],
        "contact": "Parker Finish",
        "email": "finish@example.invalid",
        "payment_terms": "NET30",
        "currency": "AUD",
        "lead_time_days": 4,
        "rating": 4,
    },
}

EXPECTED_VISIBILITY = {
    "custA.viewer": {
        "jobs": ["DEMO-JOB-A1"],
        "orders": ["DEMO-SO-A1"],
    },
    "custB.viewer": {
        "jobs": ["DEMO-JOB-B1"],
        "orders": ["DEMO-SO-B1"],
    },
    "supX.viewer": {
        "jobs": ["DEMO-JOB-A1"],
        "orders": ["DEMO-PO-X1"],
    },
    "supY.viewer": {
        "jobs": ["DEMO-JOB-A1", "DEMO-JOB-B1"],
        "orders": ["DEMO-PO-Y1"],
    },
    "misconfig.custrole": {
        "jobs": [],
        "orders": [],
    },
    "admin": {
        "jobs": ["DEMO-JOB-A1", "DEMO-JOB-B1", "DEMO-JOB-O1"],
        "orders": ["DEMO-PO-X1", "DEMO-PO-Y1", "DEMO-PO-E1", "DEMO-SO-A1", "DEMO-SO-B1", "DEMO-PO-O1"],
    },
    "planner": {
        "jobs": ["DEMO-JOB-A1", "DEMO-JOB-B1", "DEMO-JOB-O1"],
        "orders": ["DEMO-PO-X1", "DEMO-PO-Y1", "DEMO-PO-E1", "DEMO-SO-A1", "DEMO-SO-B1", "DEMO-PO-O1"],
    },
    "operator": {
        "jobs": ["DEMO-JOB-A1", "DEMO-JOB-B1", "DEMO-JOB-O1"],
        "orders": ["DEMO-PO-X1", "DEMO-PO-Y1", "DEMO-PO-E1", "DEMO-SO-A1", "DEMO-SO-B1", "DEMO-PO-O1"],
    },
}

def _normalize_domain(domain: str) -> str:
    value = (domain or "").strip().lower()
    if not value:
        return "demo.com"
    if value.endswith(".com"):
        return value
    parts = value.split(".")
    if len(parts) == 1:
        return value + ".com"
    parts[-1] = "com"
    return ".".join(parts)


def _user_email(alias: str, domain: str) -> str:
    return f"{alias}@{domain}".lower()


def _upsert_user(email: str, role: Role, password: str) -> User:
    from app.services.api_tokens import revoke_user_tokens
    from app.services.session_lifecycle import revoke_user_sessions

    u = User.objects(email=email).first()
    existed = u is not None
    if not u:
        u = User(email=email, fs_uniquifier=secrets.token_hex(16))
    u.password = hash_password(password)
    u.roles = [role]
    u.active = True
    u.save()
    revoke_user_tokens(u, reason="demo_credential_refresh")
    if existed:
        revoke_user_sessions(u, reason="demo_credential_refresh")
    return u


def _upsert_customer(code: str, name: str, **fields) -> Customer:
    c = Customer.objects(code=code).first() or Customer(code=code)
    c.name = name
    for key, value in fields.items():
        setattr(c, key, value)
    c.status = c.status or "active"
    c.save()
    return c


def _upsert_supplier(code: str, name: str, **fields) -> Supplier:
    s = Supplier.objects(code=code).first() or Supplier(code=code)
    s.name = name
    for key, value in fields.items():
        setattr(s, key, value)
    s.status = s.status or "active"
    s.save()
    return s


def _upsert_part(pn: str, rev: str, desc: str, category: str) -> Part:
    p = Part.objects(part_number=pn, revision=rev).first() or Part(part_number=pn, revision=rev)
    p.description = desc
    p.category = category
    p.status = p.status or "active"
    p.save()
    return p


def _upsert_bom(parent_pn: str, parent_rev: str, child_pn: str, child_rev: str, qty: float):
    link = BOMLink.objects(
        parent_pn=parent_pn,
        parent_rev=parent_rev,
        child_pn=child_pn,
        child_rev=child_rev,
    ).first() or BOMLink(parent_pn=parent_pn, parent_rev=parent_rev, child_pn=child_pn, child_rev=child_rev)
    link.qty = qty
    link.uom = link.uom or "EA"
    link.updated_at = utc_now()
    link.save()


def _upsert_job(job_number: str, customer: Customer, vendors: List[Supplier], bom_lines: List[JobBOMLine]) -> Job:
    j = Job.objects(job_number=job_number).first() or Job(job_number=job_number)
    j.customer = customer
    j.vendors = vendors
    j.bom = bom_lines
    j.is_deleted = False
    j.status = j.status or "released"
    j.updated_at = utc_now()
    j.save()
    return j


def _upsert_order(order_number: str, kind: str, customer: Customer | None, supplier: Supplier | None, job: Job | None, lines: List[OrderLine]) -> Order:
    o = Order.objects(order_number=order_number).first() or Order(order_number=order_number)
    o.kind = kind
    o.customer = customer
    o.supplier = supplier
    o.job = job
    o.lines = lines
    subtotal, tax_total, discount_total = calculate_order_totals(o.lines)
    o.subtotal = subtotal
    o.tax_amount = tax_total
    o.discount_amount = discount_total
    o.total = max(subtotal - discount_total + tax_total + float(o.shipping_cost or 0.0), 0.0)
    o.status = o.status or "confirmed"
    o.updated_at = utc_now()
    o.save()
    return o


PERMISSION_TEST_ROLE_SCENARIOS: dict[str, tuple[str, ...]] = {
    **{slug: (slug,) for slug in STANDARD_ROLE_SLUGS},
    "engineering_commercial": ("engineering", "commercial"),
    "commercial_supplier": ("commercial", "supplier"),
    "security_customer": ("security_administrator", "customer"),
    # Explicit unreleased exceptions.  The portal boundary still strips every
    # unrelated auditor/engineering capability and keeps relationship scope.
    "customer_unreleased": ("auditor", "customer"),
    "customer_spares": ("customer",),
    "supplier_unreleased": ("engineering", "supplier"),
    "supplier_running_gear": ("supplier",),
    "supplier_electrical": ("engineering", "supplier"),
    "supplier_finish": ("supplier",),
}


def _permission_test_email(scenario: str, domain: str) -> str:
    return f"permtest.{scenario}@{_normalize_domain(domain)}".lower()


def _permission_test_users(domain: str) -> list[User]:
    normalized = _normalize_domain(domain)
    pattern = rf"^permtest\.[a-z0-9_]+@{re.escape(normalized)}$"
    return list(User.objects(email__regex=pattern))


def _standard_role_documents() -> dict[str, Role]:
    from app.services.standard_roles import STANDARD_ROLES, reconcile_standard_roles

    reconcile_standard_roles()
    roles = {
        role.name: role
        for role in Role.objects(name__in=list(STANDARD_ROLES))
    }
    missing = set(STANDARD_ROLES) - set(roles)
    if missing:
        raise RuntimeError(
            "Standard role reconciliation did not create: "
            + ", ".join(sorted(missing))
        )
    # Demo portal conversations and the RLS assertions require the canonical
    # external definitions.  Restore only these two roles; do not overwrite
    # operator-modified internal roles while refreshing demo data.
    for slug in ("customer", "supplier"):
        role = roles[slug]
        definition = STANDARD_ROLES[slug]
        if (
            role.display_name != definition.display_name
            or role.description != definition.description
            or tuple(role.permissions or ()) != definition.permissions
        ):
            role.display_name = definition.display_name
            role.description = definition.description
            role.permissions = list(definition.permissions)
            role.save()
    return roles


def _seed_permission_test_records(
    users: dict[str, User],
) -> tuple[dict[str, object], dict[str, int]]:
    from app.services.sample_dataset import ensure_sample_engineering_records

    sample_created = ensure_sample_engineering_records()
    created = {
        "customers": 0,
        "suppliers": 0,
        "jobs": 0,
        "orders": 0,
        "parts": 0,
        "bom_links": 0,
        "sample_parts": sample_created["parts"],
        "sample_bom_links": sample_created["bom_links"],
        "sample_approvals": sample_created["approvals_updated"],
        "sample_part_files": sample_created["part_files"],
    }

    customers: dict[str, Customer] = {}
    for code, name in DEMO_CUSTOMERS:
        if Customer.objects(code=code).first() is None:
            created["customers"] += 1
        customers[code] = _upsert_customer(
            code,
            name,
            **DEMO_CUSTOMER_PROFILES[code],
        )

    suppliers: dict[str, Supplier] = {}
    for code, name in DEMO_SUPPLIERS:
        if Supplier.objects(code=code).first() is None:
            created["suppliers"] += 1
        suppliers[code] = _upsert_supplier(
            code,
            name,
            **DEMO_SUPPLIER_PROFILES[code],
        )

    customers["DEMO-CUST-A"].users = [users["customer"]]
    customers["DEMO-CUST-B"].users = [
        users["security_customer"],
        users["customer_spares"],
    ]
    customers["DEMO-CUST-A"].users.append(users["customer_unreleased"])
    customers["DEMO-CUST-OTHER"].users = []
    suppliers["DEMO-SUP-X"].users = [
        users["supplier"],
        users["supplier_unreleased"],
    ]
    suppliers["DEMO-SUP-Y"].users = [
        users["commercial_supplier"],
        users["supplier_running_gear"],
    ]
    suppliers["DEMO-SUP-E"].users = [users["supplier_electrical"]]
    suppliers["DEMO-SUP-OTHER"].users = [users["supplier_finish"]]
    for customer in customers.values():
        customer.save()
    for supplier in suppliers.values():
        supplier.save()

    part_specs = [
        *DEMO_PARTS,
        ("DEMO-ASM-1", "B", "Demo Assembly 1 draft", "Assembly"),
        ("DEMO-CMP-A", "B", "Demo Component A draft", "Component"),
    ]
    seen_parts: set[tuple[str, str]] = set()
    for pn, rev, description, category in part_specs:
        key = (pn, rev)
        if key in seen_parts:
            continue
        seen_parts.add(key)
        if Part.objects(part_number=pn, revision=rev).first() is None:
            created["parts"] += 1
        part = _upsert_part(pn, rev, description, category)
        attrs = dict(part.attrs or {})
        if rev == "A":
            attrs["approvedby"] = "Permission Test QA"
        else:
            attrs.pop("approvedby", None)
            attrs.pop("approved_by", None)
        part.attrs = attrs
        part.save()

    for parent_pn, parent_rev, child_pn, child_rev, qty in DEMO_BOM:
        if BOMLink.objects(
            parent_pn=parent_pn,
            parent_rev=parent_rev,
            child_pn=child_pn,
            child_rev=child_rev,
        ).first() is None:
            created["bom_links"] += 1
        _upsert_bom(parent_pn, parent_rev, child_pn, child_rev, qty)

    job_specs = {
        "DEMO-JOB-A1": (
            customers["DEMO-CUST-A"],
            [
                suppliers["DEMO-SUP-X"],
                suppliers["DEMO-SUP-Y"],
                suppliers["DEMO-SUP-E"],
                suppliers["DEMO-SUP-OTHER"],
            ],
            [JobBOMLine(pn="CV03-TR-A01", rev="A", qty=3.0)],
            [
                users["workshop"],
                users["engineering_commercial"],
            ],
            {
                "title": "Fleet build: three CELLV03 trailers",
                "description": "Complete-unit build for the demo fleet customer.",
                "part_number": "CV03-TR-A01",
                "part_revision": "A",
                "qty_ordered": 3.0,
                "priority": "high",
                "status": "released",
            },
        ),
        "DEMO-JOB-B1": (
            customers["DEMO-CUST-B"],
            [suppliers["DEMO-SUP-Y"], suppliers["DEMO-SUP-E"]],
            [
                JobBOMLine(pn="ADR-HITCH", rev="A", qty=2.0),
                JobBOMLine(pn="OEM-JOCKEYWHEEL", rev="A", qty=2.0),
                JobBOMLine(pn="ADR-LED-IND", rev="", qty=4.0),
                JobBOMLine(pn="rego plate light", rev="", qty=2.0),
                JobBOMLine(pn="Mudguard", rev="A", qty=2.0),
            ],
            [],
            {
                "title": "Service stock: CELLV03 spare parts",
                "description": "Replacement running gear, lighting and body parts.",
                "part_number": "CV03-TR-A01",
                "part_revision": "A",
                "qty_ordered": 1.0,
                "priority": "normal",
                "status": "in_progress",
            },
        ),
        "DEMO-JOB-O1": (
            customers["DEMO-CUST-OTHER"],
            [suppliers["DEMO-SUP-OTHER"]],
            [JobBOMLine(pn="CV03-F02", rev="B", qty=1.0)],
            [],
            {
                "title": "Isolated frame refinishing",
                "description": "Negative RLS fixture using an approved BOM child.",
                "part_number": "CV03-F02",
                "part_revision": "B",
                "qty_ordered": 1.0,
                "priority": "low",
                "status": "on_hold",
            },
        ),
    }
    jobs: dict[str, Job] = {}
    for job_number, (customer, vendors, bom, participants, fields) in job_specs.items():
        if Job.objects(job_number=job_number).first() is None:
            created["jobs"] += 1
        job = _upsert_job(job_number, customer, vendors, bom)
        job.participants = participants
        for key, value in fields.items():
            setattr(job, key, value)
        job.save()
        jobs[job_number] = job

    order_specs = [
        (
            "DEMO-PO-X1",
            "purchase",
            None,
            suppliers["DEMO-SUP-X"],
            jobs["DEMO-JOB-A1"],
            [OrderLine(pn="CV03-F02", rev="B", qty=3.0, uom="EA", description="Welded trailer frame", unit_price=2400.0, tax_pct=10.0)],
            {"description": "Three welded CELLV03 frames", "currency": "AUD", "status": "confirmed"},
        ),
        (
            "DEMO-PO-Y1",
            "purchase",
            None,
            suppliers["DEMO-SUP-Y"],
            jobs["DEMO-JOB-A1"],
            [
                OrderLine(pn="SUSPENSIONKIT-93in", rev="A", qty=3.0, uom="EA", description="ADR suspension kit", unit_price=850.0, tax_pct=10.0),
                OrderLine(pn="OEM-JOCKEYWHEEL", rev="A", qty=3.0, uom="EA", description="Jockey wheel kit", unit_price=160.0, tax_pct=10.0),
                OrderLine(pn="ADR-HITCH", rev="A", qty=3.0, uom="EA", description="50 mm ball hitch", unit_price=120.0, tax_pct=10.0),
            ],
            {"description": "Running gear for fleet build", "currency": "AUD", "status": "submitted"},
        ),
        (
            "DEMO-PO-E1",
            "purchase",
            # Deliberate cross-kind field: customers must not gain a purchase
            # order merely because their reference is present for drop-ship.
            customers["DEMO-CUST-A"],
            suppliers["DEMO-SUP-E"],
            jobs["DEMO-JOB-A1"],
            [
                OrderLine(pn="ADR-LED-IND", rev="", qty=6.0, uom="EA", description="Rear combination lamp", unit_price=85.0, tax_pct=10.0),
                OrderLine(pn="rego plate light", rev="", qty=3.0, uom="EA", description="Registration plate lamp", unit_price=32.0, tax_pct=10.0),
                OrderLine(pn="ADR-REF-A", rev="A", qty=6.0, uom="EA", description="Amber reflector", unit_price=9.0, tax_pct=10.0),
                OrderLine(pn="ADR-REF-W", rev="A", qty=12.0, uom="EA", description="White reflector", unit_price=9.0, tax_pct=10.0),
                OrderLine(pn="ADR-VIN-PLATE", rev="A", qty=3.0, uom="EA", description="VIN compliance plate", unit_price=25.0, tax_pct=10.0),
                OrderLine(pn="R104-CMARK", rev="A", qty=3.0, uom="EA", description="Conspicuity marking tape", unit_price=60.0, tax_pct=10.0),
            ],
            {"description": "ADR electrical and compliance kit", "currency": "AUD", "status": "confirmed"},
        ),
        (
            "DEMO-SO-A1",
            "sales",
            customers["DEMO-CUST-A"],
            None,
            jobs["DEMO-JOB-A1"],
            [OrderLine(pn="CV03-TR-A01", rev="A", qty=3.0, uom="EA", description="CELLV03 complete trailer", unit_price=12900.0, tax_pct=10.0)],
            {"description": "Fleet order for three complete trailers", "currency": "AUD", "status": "in_production", "customer_po": "OHF-2408"},
        ),
        (
            "DEMO-SO-B1",
            "sales",
            customers["DEMO-CUST-B"],
            # Deliberate malformed legacy reference.  Supplier scoping must
            # ignore supplier fields on sales orders.
            suppliers["DEMO-SUP-E"],
            jobs["DEMO-JOB-B1"],
            [
                OrderLine(pn="ADR-HITCH", rev="A", qty=2.0, uom="EA", description="Replacement ball hitch", unit_price=185.0, tax_pct=10.0),
                OrderLine(pn="OEM-JOCKEYWHEEL", rev="A", qty=2.0, uom="EA", description="Replacement jockey wheel", unit_price=245.0, tax_pct=10.0),
                OrderLine(pn="ADR-LED-IND", rev="", qty=4.0, uom="EA", description="Replacement rear lamp", unit_price=135.0, tax_pct=10.0),
                OrderLine(pn="rego plate light", rev="", qty=2.0, uom="EA", description="Replacement plate lamp", unit_price=55.0, tax_pct=10.0),
                OrderLine(pn="Mudguard", rev="A", qty=2.0, uom="EA", description="Replacement mudguard", unit_price=190.0, tax_pct=10.0),
            ],
            {"description": "CELLV03 service and spare-parts order", "currency": "AUD", "status": "ready_to_ship", "customer_po": "CTS-SPARES-17"},
        ),
        (
            "DEMO-PO-O1",
            "purchase",
            None,
            suppliers["DEMO-SUP-OTHER"],
            jobs["DEMO-JOB-O1"],
            [OrderLine(pn="CV03-F02", rev="B", qty=1.0, uom="EA", description="Powder coat trailer frame", unit_price=650.0, tax_pct=10.0)],
            {"description": "Isolated powder-coat service order", "currency": "AUD", "status": "submitted"},
        ),
    ]
    for order_number, kind, customer, supplier, job, lines, fields in order_specs:
        if Order.objects(order_number=order_number).first() is None:
            created["orders"] += 1
        order = _upsert_order(
            order_number,
            kind,
            customer,
            supplier,
            job,
            lines,
        )
        for key, value in fields.items():
            setattr(order, key, value)
        subtotal, tax_total, discount_total = calculate_order_totals(order.lines)
        order.subtotal = subtotal
        order.tax_amount = tax_total
        order.discount_amount = discount_total
        order.total = max(subtotal - discount_total + tax_total + float(order.shipping_cost or 0.0), 0.0)
        order.save()

    from app.services.sample_reviews import seed_sample_review_history

    review_totals = seed_sample_review_history(users)
    created.update(
        {
            "sample_annotated_parts_total": review_totals["annotated_parts"],
            "sample_comments_total": review_totals["comments"],
            "sample_markup_threads_total": review_totals["markup_threads"],
        }
    )

    linked = {
        "customer_portal": {
            "customer": "DEMO-CUST-A",
            "job": "DEMO-JOB-A1",
        },
        "sales_customer": {
            "customer": "DEMO-CUST-B",
            "job": "DEMO-JOB-B1",
        },
        "security_customer": {
            "customer": "DEMO-CUST-B",
            "job": "DEMO-JOB-B1",
        },
        "customer_spares": {
            "customer": "DEMO-CUST-B",
            "job": "DEMO-JOB-B1",
        },
        "customer_unreleased": {
            "customer": "DEMO-CUST-A",
            "job": "DEMO-JOB-A1",
            "exception": "parts.read_unreleased",
        },
        "supplier_portal": {
            "supplier": "DEMO-SUP-X",
            "job": "DEMO-JOB-A1",
        },
        "procurement_supplier": {
            "supplier": "DEMO-SUP-Y",
            "job": "DEMO-JOB-A1",
        },
        "supplier_running_gear": {
            "supplier": "DEMO-SUP-Y",
            "job": "DEMO-JOB-A1",
        },
        "supplier_electrical": {
            "supplier": "DEMO-SUP-E",
            "job": "DEMO-JOB-A1",
        },
        "supplier_finish": {
            "supplier": "DEMO-SUP-OTHER",
            "job": "DEMO-JOB-A1",
        },
        "supplier_unreleased": {
            "supplier": "DEMO-SUP-X",
            "job": "DEMO-JOB-A1",
            "exception": "parts.read_unreleased",
        },
        "production_operator": {"job": "DEMO-JOB-A1"},
        "planner_production": {"job": "DEMO-JOB-A1"},
    }
    totals = {
        "customers": Customer.objects(code__startswith="DEMO-CUST-").count(),
        "suppliers": Supplier.objects(code__startswith="DEMO-SUP-").count(),
        "jobs": Job.objects(job_number__startswith="DEMO-").count(),
        "orders": Order.objects(order_number__startswith="DEMO-").count(),
        "parts": Part.objects(part_number__startswith="DEMO-").count(),
        "bom_links": BOMLink.objects(
            __raw__={
                "$or": [
                    {"parent_pn": {"$regex": "^DEMO-"}},
                    {"child_pn": {"$regex": "^DEMO-"}},
                ]
            }
        ).count(),
    }
    return linked, {**created, **{f"{key}_total": value for key, value in totals.items()}}


def seed_permission_test_environment(
    domain: str = "demo.com",
) -> dict[str, object]:
    """Create canonical roles/RLS records plus the CV03 sample metadata.

    Managed fixture files are installed separately with
    ``tools/install_sample_dataset.py`` so seeding never writes into an
    operator's configured deliverables root implicitly.
    """

    from app.services.api_tokens import revoke_user_tokens
    from app.services.session_lifecycle import revoke_user_sessions

    normalized = _normalize_domain(domain)
    roles = _standard_role_documents()
    user_rows = []
    users: dict[str, User] = {}
    created_users = 0
    updated_users = 0
    for scenario, role_slugs in PERMISSION_TEST_ROLE_SCENARIOS.items():
        email = _permission_test_email(scenario, normalized)
        user = User.objects(email=email).first()
        created = user is None
        if user is None:
            user = User(
                email=email,
                fs_uniquifier=secrets.token_hex(16),
            )
            created_users += 1
        else:
            updated_users += 1
        password = secrets.token_urlsafe(18)
        user.password = hash_password(password)
        user.password_changed_at = utc_now()
        user.roles = [roles[slug] for slug in role_slugs]
        user.active = True
        user.updated_at = utc_now()
        user.save()
        settings = UserSettings.objects(user_id=user).first() or UserSettings(
            user_id=user
        )
        profile = dict(settings.profile or {})
        profile["display_name"] = DEMO_USER_DISPLAY_NAMES.get(
            scenario,
            f"Demo {scenario.replace('_', ' ').title()}",
        )
        settings.profile = profile
        settings.updated_at = utc_now()
        settings.save()
        revoke_user_tokens(user, reason="permission_test_credential_refresh")
        if not created:
            revoke_user_sessions(
                user,
                reason="permission_test_credential_refresh",
            )
        users[scenario] = user
        user_rows.append(
            {
                "scenario": scenario,
                "email": email,
                "password": password,
                "roles": list(role_slugs),
                "created": created,
            }
        )

    linked, record_counts = _seed_permission_test_records(users)
    for row in user_rows:
        row["linked"] = linked.get(row["scenario"], {})
    return {
        "domain": normalized,
        "users": user_rows,
        "counts": {
            "users_created": created_users,
            "users_updated": updated_users,
            **record_counts,
        },
    }


def reset_permission_test_environment(
    domain: str = "demo.com",
) -> dict[str, int]:
    """Remove only the reserved permission-test namespace and DEMO records."""

    from app.services.sample_reviews import remove_sample_review_history

    removed_reviews = remove_sample_review_history()
    users = _permission_test_users(domain)
    user_ids = [user.id for user in users]
    deleted_settings = (
        UserSettings.objects(user_id__in=user_ids).delete()
        if user_ids
        else 0
    )
    deleted_tokens = (
        ApiToken.objects(user_id__in=user_ids).delete()
        if user_ids
        else 0
    )
    deleted_users = (
        User.objects(id__in=user_ids).delete()
        if user_ids
        else 0
    )
    deleted_bom = BOMLink.objects(
        __raw__={
            "$or": [
                {"parent_pn": {"$regex": "^DEMO-"}},
                {"child_pn": {"$regex": "^DEMO-"}},
            ]
        }
    ).delete()
    deleted_orders = Order.objects(
        order_number__startswith="DEMO-"
    ).delete()
    deleted_jobs = Job.objects(job_number__startswith="DEMO-").delete()
    deleted_customers = Customer.objects(
        code__startswith="DEMO-CUST-"
    ).delete()
    deleted_suppliers = Supplier.objects(
        code__startswith="DEMO-SUP-"
    ).delete()
    deleted_parts = Part.objects(
        part_number__startswith="DEMO-"
    ).delete()
    return {
        "tokens": int(deleted_tokens or 0),
        "user_settings": int(deleted_settings or 0),
        "users": int(deleted_users or 0),
        "customers": int(deleted_customers or 0),
        "suppliers": int(deleted_suppliers or 0),
        "jobs": int(deleted_jobs or 0),
        "orders": int(deleted_orders or 0),
        "parts": int(deleted_parts or 0),
        "bom_links": int(deleted_bom or 0),
        "sample_comments": removed_reviews["comments"],
        "sample_markup_threads": removed_reviews["markup_threads"],
    }

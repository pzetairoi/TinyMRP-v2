from __future__ import annotations

import csv
import json
import os
import re
import secrets
from datetime import datetime
from typing import Dict, List, Tuple

from flask import current_app
from flask_security import hash_password

from app.models.auth import User, Role
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.job import Job, JobBOMLine
from app.models.order import Order, OrderLine
from app.models.part import Part
from app.models.bom import BOMLink
from app.models.api_token import ApiToken
from app.services.api_tokens import create_token
from app.services.biz_utils import calculate_order_totals
from app.services.acl import apply_job_scope, apply_order_scope, allowed_parts_for
from app.services.standard_roles import STANDARD_ROLE_SLUGS
from app.services.timezone_utils import utc_iso, utc_now


DEMO_CUSTOMERS = [
    ("DEMO-CUST-A", "Demo Customer A"),
    ("DEMO-CUST-B", "Demo Customer B"),
    ("DEMO-CUST-OTHER", "Demo Customer Other"),
]
DEMO_SUPPLIERS = [
    ("DEMO-SUP-X", "Demo Supplier X"),
    ("DEMO-SUP-Y", "Demo Supplier Y"),
    ("DEMO-SUP-OTHER", "Demo Supplier Other"),
]
DEMO_JOBS = [
    ("DEMO-JOB-A1", "DEMO-CUST-A", ["DEMO-SUP-X"]),
    ("DEMO-JOB-B1", "DEMO-CUST-B", ["DEMO-SUP-Y"]),
    ("DEMO-JOB-O1", "DEMO-CUST-OTHER", ["DEMO-SUP-OTHER"]),
]
DEMO_ORDERS = [
    ("DEMO-PO-X1", "purchase", None, "DEMO-SUP-X", "DEMO-JOB-O1"),
    ("DEMO-PO-Y1", "purchase", None, "DEMO-SUP-Y", "DEMO-JOB-A1"),
    ("DEMO-SO-A1", "sales", "DEMO-CUST-A", None, None),
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

EXPECTED_VISIBILITY = {
    "custA.viewer": {
        "jobs": ["DEMO-JOB-A1"],
        "orders": ["DEMO-SO-A1"],
    },
    "custB.viewer": {
        "jobs": ["DEMO-JOB-B1"],
        "orders": [],
    },
    "supX.viewer": {
        "jobs": ["DEMO-JOB-A1", "DEMO-JOB-O1"],
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
        "orders": ["DEMO-PO-X1", "DEMO-PO-Y1", "DEMO-SO-A1", "DEMO-PO-O1"],
    },
    "planner": {
        "jobs": ["DEMO-JOB-A1", "DEMO-JOB-B1", "DEMO-JOB-O1"],
        "orders": ["DEMO-PO-X1", "DEMO-PO-Y1", "DEMO-SO-A1", "DEMO-PO-O1"],
    },
    "operator": {
        "jobs": ["DEMO-JOB-A1", "DEMO-JOB-B1", "DEMO-JOB-O1"],
        "orders": ["DEMO-PO-X1", "DEMO-PO-Y1", "DEMO-SO-A1", "DEMO-PO-O1"],
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


def _upsert_customer(code: str, name: str) -> Customer:
    c = Customer.objects(code=code).first() or Customer(code=code)
    c.name = name
    c.status = c.status or "active"
    c.save()
    return c


def _upsert_supplier(code: str, name: str) -> Supplier:
    s = Supplier.objects(code=code).first() or Supplier(code=code)
    s.name = name
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
    return roles


def _seed_permission_test_records(
    users: dict[str, User],
) -> tuple[dict[str, object], dict[str, int]]:
    created = {
        "customers": 0,
        "suppliers": 0,
        "jobs": 0,
        "orders": 0,
        "parts": 0,
        "bom_links": 0,
    }

    customers: dict[str, Customer] = {}
    for code, name in DEMO_CUSTOMERS:
        if Customer.objects(code=code).first() is None:
            created["customers"] += 1
        customers[code] = _upsert_customer(code, name)

    suppliers: dict[str, Supplier] = {}
    for code, name in DEMO_SUPPLIERS:
        if Supplier.objects(code=code).first() is None:
            created["suppliers"] += 1
        suppliers[code] = _upsert_supplier(code, name)

    customers["DEMO-CUST-A"].users = [
        users["customer"],
        users["security_customer"],
    ]
    customers["DEMO-CUST-B"].users = []
    suppliers["DEMO-SUP-X"].users = [users["supplier"]]
    suppliers["DEMO-SUP-Y"].users = [users["commercial_supplier"]]
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
            [suppliers["DEMO-SUP-X"]],
            [JobBOMLine(pn="DEMO-ASM-1", rev="A", qty=1.0)],
            [
                users["workshop"],
                users["engineering_commercial"],
            ],
        ),
        "DEMO-JOB-B1": (
            customers["DEMO-CUST-B"],
            [suppliers["DEMO-SUP-Y"]],
            [JobBOMLine(pn="DEMO-ASM-2", rev="A", qty=1.0)],
            [],
        ),
        "DEMO-JOB-O1": (
            customers["DEMO-CUST-OTHER"],
            [suppliers["DEMO-SUP-OTHER"]],
            [JobBOMLine(pn="DEMO-CMP-A", rev="A", qty=1.0)],
            [],
        ),
    }
    jobs: dict[str, Job] = {}
    for job_number, (customer, vendors, bom, participants) in job_specs.items():
        if Job.objects(job_number=job_number).first() is None:
            created["jobs"] += 1
        job = _upsert_job(job_number, customer, vendors, bom)
        job.participants = participants
        job.save()
        jobs[job_number] = job

    order_specs = [
        (
            "DEMO-PO-X1",
            "purchase",
            None,
            suppliers["DEMO-SUP-X"],
            jobs["DEMO-JOB-A1"],
            [OrderLine(pn="DEMO-CMP-A", rev="A", qty=5.0, uom="EA")],
        ),
        (
            "DEMO-PO-Y1",
            "purchase",
            None,
            suppliers["DEMO-SUP-Y"],
            jobs["DEMO-JOB-B1"],
            [OrderLine(pn="DEMO-CMP-B", rev="A", qty=3.0, uom="EA")],
        ),
        (
            "DEMO-SO-A1",
            "sales",
            customers["DEMO-CUST-A"],
            None,
            jobs["DEMO-JOB-A1"],
            [OrderLine(pn="DEMO-ASM-1", rev="A", qty=1.0, uom="EA")],
        ),
        (
            "DEMO-PO-O1",
            "purchase",
            None,
            suppliers["DEMO-SUP-OTHER"],
            jobs["DEMO-JOB-O1"],
            [OrderLine(pn="DEMO-RAW-1", rev="A", qty=10.0, uom="EA")],
        ),
    ]
    for order_number, kind, customer, supplier, job, lines in order_specs:
        if Order.objects(order_number=order_number).first() is None:
            created["orders"] += 1
        _upsert_order(
            order_number,
            kind,
            customer,
            supplier,
            job,
            lines,
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
            "customer": "DEMO-CUST-A",
            "job": "DEMO-JOB-A1",
        },
        "supplier_portal": {
            "supplier": "DEMO-SUP-X",
            "job": "DEMO-JOB-A1",
        },
        "procurement_supplier": {
            "supplier": "DEMO-SUP-Y",
            "job": "DEMO-JOB-B1",
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
    """Create the small canonical permission-test environment without tokens/files."""

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

    users = _permission_test_users(domain)
    user_ids = [user.id for user in users]
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
        "users": int(deleted_users or 0),
        "customers": int(deleted_customers or 0),
        "suppliers": int(deleted_suppliers or 0),
        "jobs": int(deleted_jobs or 0),
        "orders": int(deleted_orders or 0),
        "parts": int(deleted_parts or 0),
        "bom_links": int(deleted_bom or 0),
    }

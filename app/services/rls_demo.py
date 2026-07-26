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


def _ensure_roles() -> Dict[str, Role]:
    from app.services.permissions import LEGACY_PERMISSION_IDENTIFIERS

    def ensure(name: str, desc: str, perms: list[str]) -> Role:
        r = Role.objects(name=name).first()
        if r:
            return r
        r = Role(name=name, description=desc, permissions=perms).save()
        return r

    roles = {
        "admin": ensure(
            "admin",
            "Full access",
            list(LEGACY_PERMISSION_IDENTIFIERS),
        ),
        "planner": ensure("planner", "Plan and run MRP", [
            "items.view","bom.view","mrp.run","reports.view",
            "jobs.view","jobs.manage","orders.view","orders.manage",
            "suppliers.view","customers.view",
            "tools.view","import.bom"
        ]),
        "operator": ensure("operator", "Execute work orders", [
            "workorders.view","workorders.edit","workorders.close",
            "inventory.issue","inventory.receive",
            "items.view","bom.view",
            "tools.view","import.bom"
        ]),
        "viewer": ensure("viewer", "Read-only", [
            "items.view","bom.view","workorders.view","reports.view",
            "jobs.view","orders.view","suppliers.view","customers.view"
        ]),
        "customer_viewer": ensure("customer_viewer", "Customer-linked viewer", [
            "items.view","bom.view","jobs.view","orders.view","customers.view"
        ]),
        "supplier_viewer": ensure("supplier_viewer", "Supplier-linked viewer", [
            "items.view","bom.view","orders.view","suppliers.view"
        ]),
    }
    return roles


def _user_email(alias: str, domain: str) -> str:
    return f"{alias}@{domain}".lower()


def _upsert_user(email: str, role: Role, password: str) -> User:
    u = User.objects(email=email).first()
    if not u:
        u = User(email=email, fs_uniquifier=secrets.token_hex(16))
    u.password = hash_password(password)
    u.roles = [role]
    u.active = True
    u.save()
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


def reset_rls_demo(domain: str) -> Dict[str, int]:
    normalized = _normalize_domain(domain)
    domains = {normalized, (domain or "").strip().lower()}
    domains = {d for d in domains if d}
    emails = []
    for dom in domains:
        emails.extend([
            _user_email("admin", dom),
            _user_email("planner", dom),
            _user_email("operator", dom),
            _user_email("custA.viewer", dom),
            _user_email("custB.viewer", dom),
            _user_email("supX.viewer", dom),
            _user_email("supY.viewer", dom),
            _user_email("misconfig.custrole", dom),
        ])
    users = list(User.objects(email__in=emails))
    user_ids = [u.id for u in users]

    deleted_tokens = ApiToken.objects(user_id__in=user_ids).delete() if user_ids else 0
    deleted_users = User.objects(id__in=user_ids).delete() if user_ids else 0

    deleted_customers = Customer.objects(code__startswith="DEMO-CUST-").delete()
    deleted_suppliers = Supplier.objects(code__startswith="DEMO-SUP-").delete()
    deleted_jobs = Job.objects(job_number__startswith="DEMO-").delete()
    deleted_orders = Order.objects(order_number__startswith="DEMO-").delete()
    deleted_parts = Part.objects(part_number__startswith="DEMO-").delete()
    deleted_bom = BOMLink.objects(
        __raw__={
            "$or": [{"parent_pn": {"$regex": "^DEMO-"}}, {"child_pn": {"$regex": "^DEMO-"}}]
        }
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


def seed_rls_demo(reset: bool = False, domain: str = "demo.com", password: str | None = None) -> Dict[str, Dict]:
    normalized = _normalize_domain(domain)
    if reset:
        reset_rls_demo(domain)

    roles = _ensure_roles()

    if password:
        pwd_map = {k: password for k in ["admin", "planner", "operator", "custA.viewer", "custB.viewer", "supX.viewer", "supY.viewer", "misconfig.custrole"]}
    else:
        pwd_map = {k: secrets.token_urlsafe(10) for k in ["admin", "planner", "operator", "custA.viewer", "custB.viewer", "supX.viewer", "supY.viewer", "misconfig.custrole"]}

    users = {
        "admin": _upsert_user(_user_email("admin", normalized), roles["admin"], pwd_map["admin"]),
        "planner": _upsert_user(_user_email("planner", normalized), roles["planner"], pwd_map["planner"]),
        "operator": _upsert_user(_user_email("operator", normalized), roles["operator"], pwd_map["operator"]),
        "custA.viewer": _upsert_user(_user_email("custA.viewer", normalized), roles["viewer"], pwd_map["custA.viewer"]),
        "custB.viewer": _upsert_user(_user_email("custB.viewer", normalized), roles["viewer"], pwd_map["custB.viewer"]),
        "supX.viewer": _upsert_user(_user_email("supX.viewer", normalized), roles["viewer"], pwd_map["supX.viewer"]),
        "supY.viewer": _upsert_user(_user_email("supY.viewer", normalized), roles["viewer"], pwd_map["supY.viewer"]),
        "misconfig.custrole": _upsert_user(_user_email("misconfig.custrole", normalized), roles["customer_viewer"], pwd_map["misconfig.custrole"]),
    }

    customers = {code: _upsert_customer(code, name) for code, name in DEMO_CUSTOMERS}
    suppliers = {code: _upsert_supplier(code, name) for code, name in DEMO_SUPPLIERS}

    customers["DEMO-CUST-A"].users = [users["custA.viewer"]]
    customers["DEMO-CUST-B"].users = [users["custB.viewer"]]
    suppliers["DEMO-SUP-X"].users = [users["supX.viewer"]]
    suppliers["DEMO-SUP-Y"].users = [users["supY.viewer"]]
    for c in customers.values():
        c.save()
    for s in suppliers.values():
        s.save()

    for pn, rev, desc, cat in DEMO_PARTS:
        _upsert_part(pn, rev, desc, cat)
    for parent_pn, parent_rev, child_pn, child_rev, qty in DEMO_BOM:
        _upsert_bom(parent_pn, parent_rev, child_pn, child_rev, qty)

    job_map = {
        "DEMO-JOB-A1": _upsert_job(
            "DEMO-JOB-A1",
            customers["DEMO-CUST-A"],
            [suppliers["DEMO-SUP-X"]],
            [JobBOMLine(pn="DEMO-ASM-1", rev="A", qty=1.0)],
        ),
        "DEMO-JOB-B1": _upsert_job(
            "DEMO-JOB-B1",
            customers["DEMO-CUST-B"],
            [suppliers["DEMO-SUP-Y"]],
            [JobBOMLine(pn="DEMO-ASM-2", rev="A", qty=1.0)],
        ),
        "DEMO-JOB-O1": _upsert_job(
            "DEMO-JOB-O1",
            customers["DEMO-CUST-OTHER"],
            [suppliers["DEMO-SUP-OTHER"]],
            [JobBOMLine(pn="DEMO-ASM-1", rev="A", qty=1.0)],
        ),
    }

    _upsert_order(
        "DEMO-PO-X1",
        "purchase",
        None,
        suppliers["DEMO-SUP-X"],
        job_map["DEMO-JOB-O1"],
        [OrderLine(pn="DEMO-CMP-A", rev="A", qty=5.0, uom="EA")],
    )
    _upsert_order(
        "DEMO-PO-Y1",
        "purchase",
        None,
        suppliers["DEMO-SUP-Y"],
        job_map["DEMO-JOB-A1"],
        [OrderLine(pn="DEMO-CMP-B", rev="A", qty=3.0, uom="EA")],
    )
    _upsert_order(
        "DEMO-SO-A1",
        "sales",
        customers["DEMO-CUST-A"],
        None,
        None,
        [OrderLine(pn="DEMO-ASM-1", rev="A", qty=1.0, uom="EA")],
    )
    _upsert_order(
        "DEMO-PO-O1",
        "purchase",
        None,
        suppliers["DEMO-SUP-OTHER"],
        job_map["DEMO-JOB-O1"],
        [OrderLine(pn="DEMO-RAW-1", rev="A", qty=10.0, uom="EA")],
    )

    ApiToken.objects(user_id__in=[u.id for u in users.values()]).delete()

    tokens = {}
    for key, u in users.items():
        token_doc, raw = create_token(u, "rlsdemo")
        tokens[key] = raw

    instance_dir = current_app.instance_path
    os.makedirs(instance_dir, exist_ok=True)
    if password is None:
        csv_path = os.path.join(instance_dir, "rlsdemo_users.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["email", "password", "roles"])
            for alias, u in users.items():
                writer.writerow([u.email, pwd_map[alias], ",".join([r.name for r in u.roles])])
            writer.writerow([])
            writer.writerow(["note", "Delete this file after use."])
            writer.writerow(["generated_at", utc_iso(utc_now()) or ""])

    token_path = os.path.join(instance_dir, "rlsdemo_tokens.json")
    with open(token_path, "w", encoding="utf-8") as f:
        json.dump(tokens, f, indent=2)

    return {
        "domain": normalized,
        "users": {k: {"email": u.email, "password": pwd_map[k], "roles": [r.name for r in u.roles]} for k, u in users.items()},
        "tokens": tokens,
        "token_path": token_path,
    }


PERMISSION_TEST_ROLE_SCENARIOS: dict[str, tuple[str, ...]] = {
    **{slug: (slug,) for slug in (
        "security_administrator",
        "system_administrator",
        "engineering_data_steward",
        "import_operator",
        "import_approver",
        "planner",
        "procurement",
        "sales_customer_service",
        "production_operator",
        "quality_reviewer",
        "internal_viewer",
        "customer_portal",
        "supplier_portal",
        "auditor",
        "break_glass_administrator",
    )},
    "engineering_quality": (
        "engineering_data_steward",
        "quality_reviewer",
    ),
    "planner_production": (
        "planner",
        "production_operator",
    ),
    "procurement_supplier": (
        "procurement",
        "supplier_portal",
    ),
    "sales_customer": (
        "sales_customer_service",
        "customer_portal",
    ),
    "security_customer": (
        "security_administrator",
        "customer_portal",
    ),
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
        users["customer_portal"],
        users["security_customer"],
    ]
    customers["DEMO-CUST-B"].users = [users["sales_customer"]]
    suppliers["DEMO-SUP-X"].users = [users["supplier_portal"]]
    suppliers["DEMO-SUP-Y"].users = [users["procurement_supplier"]]
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
                users["production_operator"],
                users["planner_production"],
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


def build_visibility_report(domain: str = "demo.com") -> Dict[str, Dict]:
    normalized = _normalize_domain(domain)
    report = {}
    user_map = {
        "admin": _user_email("admin", normalized),
        "planner": _user_email("planner", normalized),
        "operator": _user_email("operator", normalized),
        "custA.viewer": _user_email("custA.viewer", normalized),
        "custB.viewer": _user_email("custB.viewer", normalized),
        "supX.viewer": _user_email("supX.viewer", normalized),
        "supY.viewer": _user_email("supY.viewer", normalized),
        "misconfig.custrole": _user_email("misconfig.custrole", normalized),
    }
    for alias, email in user_map.items():
        u = User.objects(email=email).first()
        if not u:
            report[alias] = {"error": "missing user"}
            continue
        cust_codes = [c.code for c in Customer.objects(users=u).only("code")]
        supp_codes = [s.code for s in Supplier.objects(users=u).only("code")]
        jobs = [j.job_number for j in apply_job_scope(Job.objects(), u) if (j.job_number or "").startswith("DEMO-")]
        orders = [o.order_number for o in apply_order_scope(Order.objects(), u) if (o.order_number or "").startswith("DEMO-")]
        parts = allowed_parts_for(u)
        report[alias] = {
            "email": u.email,
            "roles": [r.name for r in (u.roles or [])],
            "customers": cust_codes,
            "suppliers": supp_codes,
            "jobs": sorted(jobs),
            "orders": sorted(orders),
            "parts_allowed": None if parts is None else len(parts),
            "parts_sample": [] if not parts or parts is None else list(sorted(parts))[:10],
            "expected": EXPECTED_VISIBILITY.get(alias, {}),
        }
    return report


def smoke_rls_demo(domain: str = "demo.com") -> Dict[str, Dict]:
    normalized = _normalize_domain(domain)
    token_path = os.path.join(current_app.instance_path, "rlsdemo_tokens.json")
    if not os.path.exists(token_path):
        return {"error": "tokens_file_missing"}
    with open(token_path, "r", encoding="utf-8") as f:
        tokens = json.load(f) or {}

    user_map = {
        "custA.viewer": _user_email("custA.viewer", normalized),
        "custB.viewer": _user_email("custB.viewer", normalized),
        "supX.viewer": _user_email("supX.viewer", normalized),
        "supY.viewer": _user_email("supY.viewer", normalized),
        "misconfig.custrole": _user_email("misconfig.custrole", normalized),
        "planner": _user_email("planner", normalized),
    }

    from flask import current_app as _app
    client = _app.test_client()

    results = {}
    overall_ok = True
    internal_aliases = {"planner"}
    for alias, email in user_map.items():
        token = tokens.get(alias)
        if not token:
            results[alias] = {"error": "missing token"}
            continue
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Auth-Token": token,
            "Authentication-Token": token,
        }

        r_jobs = client.get("/api/jobs", headers=headers)
        r_orders = client.get("/api/orders", headers=headers)

        got_jobs = [
            j["job_number"]
            for j in (r_jobs.json or {}).get("items", [])
            if (j.get("job_number") or "").startswith("DEMO-")
        ] if r_jobs.status_code == 200 else []
        got_orders = [
            o["order_number"]
            for o in (r_orders.json or {}).get("items", [])
            if (o.get("order_number") or "").startswith("DEMO-")
        ] if r_orders.status_code == 200 else []
        got_jobs = sorted(got_jobs)
        got_orders = sorted(got_orders)

        expected = EXPECTED_VISIBILITY.get(alias, {})
        exp_jobs = sorted(expected.get("jobs", []))
        exp_orders = sorted(expected.get("orders", []))

        forbidden_job = "DEMO-JOB-O1"
        if alias == "supX.viewer":
            forbidden_job = "DEMO-JOB-B1"
        elif alias == "supY.viewer":
            forbidden_job = "DEMO-JOB-O1"
        elif alias == "custA.viewer":
            forbidden_job = "DEMO-JOB-B1"
        elif alias == "custB.viewer":
            forbidden_job = "DEMO-JOB-A1"
        elif alias == "misconfig.custrole":
            forbidden_job = "DEMO-JOB-A1"

        forbidden_order = "DEMO-PO-X1"
        if alias == "supX.viewer":
            forbidden_order = "DEMO-PO-Y1"
        elif alias == "supY.viewer":
            forbidden_order = "DEMO-PO-X1"
        elif alias == "custA.viewer":
            forbidden_order = "DEMO-PO-X1"
        elif alias == "custB.viewer":
            forbidden_order = "DEMO-PO-Y1"
        elif alias == "misconfig.custrole":
            forbidden_order = "DEMO-PO-X1"

        r_job_forbidden = client.get(f"/api/jobs/{forbidden_job}", headers=headers)
        r_order_forbidden = client.get(f"/api/orders/{forbidden_order}", headers=headers)

        expected_forbidden_job_status = 200 if alias in internal_aliases else 404
        expected_forbidden_order_status = 200 if alias in internal_aliases else 404

        ok = (
            r_jobs.status_code == 200
            and r_orders.status_code == 200
            and got_jobs == exp_jobs
            and got_orders == exp_orders
            and r_job_forbidden.status_code == expected_forbidden_job_status
            and r_order_forbidden.status_code == expected_forbidden_order_status
        )
        if not ok:
            overall_ok = False
        results[alias] = {
            "jobs_list_status": r_jobs.status_code,
            "orders_list_status": r_orders.status_code,
            "jobs": got_jobs,
            "orders": got_orders,
            "expected_jobs": exp_jobs,
            "expected_orders": exp_orders,
            "forbidden_job": forbidden_job,
            "forbidden_job_status": r_job_forbidden.status_code,
            "forbidden_job_expected": expected_forbidden_job_status,
            "forbidden_order": forbidden_order,
            "forbidden_order_status": r_order_forbidden.status_code,
            "forbidden_order_expected": expected_forbidden_order_status,
            "ok": ok,
        }

    return {"ok": overall_ok, "results": results}

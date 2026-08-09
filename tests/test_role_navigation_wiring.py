import io
import uuid

import pytest

from app.models.auth import Role, User
from app.models.customer import Customer
from app.models.job import Job, JobBOMLine
from app.models.order import Order, OrderLine
from app.models.part import Part
from app.models.supplier import Supplier
from app.services.api_tokens import create_token
from app.services.rls_demo import seed_permission_test_environment
from app.services.standard_roles import STANDARD_ROLES


NAV_HREFS = {
    "parts": "/ui/parts",
    "jobs": "/admin/jobs/",
    "orders": "/admin/orders/",
    "customers": "/admin/customers/",
    "suppliers": "/admin/suppliers/",
    "tools": "/tools/",
    "import": "/ui/upload-pack",
}

ROLE_NAVIGATION = {
    "administrator": set(NAV_HREFS) | {"admin"},
    "security_administrator": {"admin"},
    "engineering_manager": {"parts", "jobs", "orders", "tools", "import", "admin"},
    "engineering": {"parts", "jobs", "orders", "tools", "import"},
    "commercial": {"parts", "jobs", "orders", "customers", "suppliers", "tools"},
    "internal": {"parts", "jobs", "orders", "customers", "suppliers", "tools"},
    "workshop": {"parts", "jobs"},
    "customer": {"parts", "jobs", "orders", "customers"},
    "supplier": {"parts", "jobs", "orders", "suppliers"},
    "auditor": {
        "parts",
        "jobs",
        "orders",
        "customers",
        "suppliers",
        "admin",
    },
}

ROLE_LANDING = {
    "administrator": "/admin/",
    "security_administrator": "/admin/",
    "engineering_manager": "/ui/parts",
    "engineering": "/ui/parts",
    "commercial": "/admin/jobs/",
    "internal": "/admin/orders/",
    "workshop": "/admin/jobs/",
    "customer": "/admin/jobs/",
    "supplier": "/admin/jobs/",
    "auditor": "/admin/",
}

ROLE_FORBIDDEN = {
    "security_administrator": "/admin/jobs/",
    "engineering_manager": "/admin/customers/",
    "engineering": "/admin/customers/",
    "commercial": "/ui/upload-pack",
    "internal": "/admin/orders/new",
    "workshop": "/admin/orders/",
    "customer": "/admin/suppliers/",
    "supplier": "/admin/customers/",
    "auditor": "/admin/users/new",
}


def _role(name):
    existing = Role.objects(name=name).first()
    if existing:
        return existing
    definition = STANDARD_ROLES[name]
    return Role(
        name=name,
        display_name=definition.display_name,
        permissions=list(definition.permissions),
    ).save()


def _user(name, *role_names):
    return User(
        email=f"{name}-{uuid.uuid4().hex}@role-wiring.test",
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=[_role(role_name) for role_name in role_names],
    ).save()


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = user.get_id()
        session["_fresh"] = True


def _headers(user):
    _, token = create_token(user, "role-wiring")
    return {"Authorization": f"Bearer {token}"}


def _released_part(number="ROLE-PART", revision="A"):
    return Part(
        part_number=number,
        revision=revision,
        attrs={"approved": "yes"},
    ).save()


@pytest.mark.parametrize("role_name", tuple(STANDARD_ROLES))
def test_every_standard_role_has_canonical_navigation_and_direct_guards(
    client,
    role_name,
):
    user = _user(role_name, role_name)
    _login(client, user)

    response = client.get("/app")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    expected = ROLE_NAVIGATION[role_name]
    for item, href in NAV_HREFS.items():
        assert (f'href="{href}"' in body) is (item in expected)
    assert ('id="navAdmin"' in body) is ("admin" in expected)

    assert client.get(ROLE_LANDING[role_name]).status_code == 200
    if role_name in ROLE_FORBIDDEN:
        assert client.get(ROLE_FORBIDDEN[role_name]).status_code == 403


def test_permission_test_users_sign_in_and_open_expected_primary_navigation(
    client,
    app,
):
    scenarios = (
        "engineering",
        "engineering_manager",
        "commercial",
        "internal",
        "workshop",
        "customer",
        "supplier",
        "security_administrator",
        "auditor",
    )
    with app.app_context():
        seeded = seed_permission_test_environment("manual-role.test")
    credentials = {
        row["scenario"]: (row["email"], row["password"])
        for row in seeded["users"]
        if row["scenario"] in scenarios
    }

    for scenario in scenarios:
        email, password = credentials[scenario]
        signed_in = client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )
        assert signed_in.status_code in (302, 303)

        body = client.get("/app").get_data(as_text=True)
        expected = ROLE_NAVIGATION[scenario]
        for item, href in NAV_HREFS.items():
            assert (f'href="{href}"' in body) is (item in expected)
            if item in expected:
                assert client.get(href).status_code == 200
        if "admin" in expected:
            assert client.get("/admin/").status_code == 200
        assert client.get(ROLE_FORBIDDEN[scenario]).status_code == 403

        with client.session_transaction() as session:
            session.clear()


@pytest.mark.parametrize(
    ("roles", "expected"),
    (
        (
            ("commercial", "customer"),
            ROLE_NAVIGATION["customer"],
        ),
        (
            ("commercial", "supplier"),
            ROLE_NAVIGATION["supplier"],
        ),
        (
            ("internal", "customer"),
            ROLE_NAVIGATION["customer"],
        ),
        (
            ("engineering", "workshop"),
            ROLE_NAVIGATION["engineering"],
        ),
        (
            ("security_administrator", "customer"),
            ROLE_NAVIGATION["customer"],
        ),
    ),
)
def test_multi_role_navigation_is_the_capability_union(client, roles, expected):
    user = _user("-".join(roles), *roles)
    _login(client, user)
    body = client.get("/app").get_data(as_text=True)

    for item, href in NAV_HREFS.items():
        assert (f'href="{href}"' in body) is (item in expected)
    assert ('id="navAdmin"' in body) is ("admin" in expected)


def test_relationship_job_and_order_scopes_cover_portals_and_commercial(
    client,
):
    customer_portal = _user("customer-portal", "customer")
    supplier_portal = _user("supplier-portal", "supplier")
    customer = Customer(
        code="ROLE-CUSTOMER",
        name="Role Customer",
        users=[customer_portal],
    ).save()
    other_customer = Customer(code="ROLE-CUSTOMER-X", name="Other").save()
    supplier = Supplier(
        code="ROLE-SUPPLIER",
        name="Role Supplier",
        users=[supplier_portal],
    ).save()
    other_supplier = Supplier(code="ROLE-SUPPLIER-X", name="Other").save()
    customer_job = Job(job_number="ROLE-JOB-C", customer=customer).save()
    vendor_job = Job(job_number="ROLE-JOB-V", vendors=[supplier]).save()
    purchase_job = Job(job_number="ROLE-JOB-PO").save()
    unrelated = Job(job_number="ROLE-JOB-X").save()
    sales = Order(
        order_number="ROLE-SO",
        kind="sales",
        customer=customer,
        job=customer_job,
    ).save()
    purchase = Order(
        order_number="ROLE-PO",
        kind="purchase",
        supplier=supplier,
        job=purchase_job,
    ).save()
    Order(
        order_number="ROLE-PO-CUSTOMER-JOB",
        kind="purchase",
        supplier=other_supplier,
        job=customer_job,
    ).save()
    Order(
        order_number="ROLE-SO-SUPPLIER",
        kind="sales",
        customer=other_customer,
        job=vendor_job,
    ).save()

    customer_jobs = client.get(
        "/api/jobs",
        headers=_headers(customer_portal),
    ).get_json()["items"]
    customer_orders = client.get(
        "/api/orders",
        headers=_headers(customer_portal),
    ).get_json()["items"]
    assert {row["job_number"] for row in customer_jobs} == {customer_job.job_number}
    assert {row["order_number"] for row in customer_orders} == {sales.order_number}

    supplier_jobs = client.get(
        "/api/jobs",
        headers=_headers(supplier_portal),
    ).get_json()["items"]
    supplier_orders = client.get(
        "/api/orders",
        headers=_headers(supplier_portal),
    ).get_json()["items"]
    assert {row["job_number"] for row in supplier_jobs} == {
        vendor_job.job_number,
        purchase_job.job_number,
    }
    assert {row["order_number"] for row in supplier_orders} == {
        purchase.order_number
    }

    # Commercial covers both purchase and sales, so its scope is company-wide.
    commercial = _user("commercial", "commercial")
    commercial_jobs = client.get(
        "/api/jobs",
        headers=_headers(commercial),
    ).get_json()["items"]
    assert {row["job_number"] for row in commercial_jobs} == {
        customer_job.job_number,
        vendor_job.job_number,
        purchase_job.job_number,
        unrelated.job_number,
    }
    commercial_orders = client.get(
        "/api/orders",
        headers=_headers(commercial),
    ).get_json()["items"]
    assert {sales.order_number, purchase.order_number} <= {
        row["order_number"] for row in commercial_orders
    }

    # Portal scope stays narrowed to linked companies.
    assert unrelated.job_number not in {
        row["job_number"] for row in customer_jobs + supplier_jobs
    }
    assert client.get(
        f"/api/jobs/{unrelated.job_number}",
        headers=_headers(customer_portal),
    ).status_code == 404


def test_list_and_form_actions_follow_exact_operation_permissions(client):
    customer = Customer(code="ACTION-C", name="Action Customer").save()
    supplier = Supplier(code="ACTION-S", name="Action Supplier").save()
    job = Job(job_number="ACTION-J", customer=customer, vendors=[supplier]).save()
    purchase = Order(
        order_number="ACTION-PO",
        kind="purchase",
        supplier=supplier,
        job=job,
    ).save()
    sales = Order(
        order_number="ACTION-SO",
        kind="sales",
        customer=customer,
        job=job,
    ).save()

    commercial = _user("action-commercial", "commercial")
    _login(client, commercial)
    jobs_body = client.get("/admin/jobs/").get_data(as_text=True)
    orders_body = client.get("/admin/orders/").get_data(as_text=True)
    order_form = client.get("/admin/orders/new").get_data(as_text=True)
    assert "Create job" in jobs_body
    assert "New order" in orders_body
    assert "Edit" in jobs_body
    # Commercial owns both order kinds and the full approval workflow.
    assert 'value="purchase"' in order_form
    assert 'value="sales"' in order_form
    assert purchase.order_number in orders_body
    assert sales.order_number in orders_body

    for role_name in ("internal", "auditor"):
        reader = _user(f"action-{role_name}", role_name)
        _login(client, reader)
        body = client.get("/admin/jobs/").get_data(as_text=True)
        assert ">View</a>" in body
        assert ">Edit</a>" not in body
        assert "Create job" not in body
        assert "Delete</button>" not in body


def test_order_edit_only_offers_allowed_kind_and_valid_status_transitions(client):
    commercial = _user("order-options-commercial", "commercial")
    supplier = Supplier(code="OPTIONS-S", name="Options Supplier").save()
    order = Order(
        order_number="OPTIONS-PO",
        kind="purchase",
        status="submitted",
        supplier=supplier,
    ).save()
    _login(client, commercial)

    response = client.get(f"/admin/orders/{order.id}/edit")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'value="purchase"' in body
    assert 'value="submitted"' in body
    assert 'value="confirmed"' in body
    assert 'value="cancelled"' in body
    assert 'value="draft"' not in body
    assert 'value="shipped"' not in body

    saved = client.post(
        f"/admin/orders/{order.id}/edit",
        data={
            "order_number": order.order_number,
            "kind": "purchase",
            "status": "confirmed",
            "supplier": str(supplier.id),
        },
    )
    assert saved.status_code == 302
    assert Order.objects.get(id=order.id).status == "confirmed"


def test_portal_view_links_and_multi_role_internal_presentation(client):
    portal = _user("link-portal", "customer")
    customer = Customer(code="LINK-C", name="Link Customer", users=[portal]).save()
    job = Job(job_number="LINK-J", customer=customer).save()
    Order(
        order_number="LINK-SO",
        kind="sales",
        customer=customer,
        job=job,
    ).save()
    Job(
        job_number="UNLINKED-J",
        customer=Customer(code="OTHER-C", name="Other Customer").save(),
    ).save()
    _login(client, portal)
    assert ">View</a>" in client.get("/admin/jobs/").get_data(as_text=True)
    assert ">View</a>" in client.get("/admin/orders/").get_data(as_text=True)

    sales_portal = _user(
        "internal-sales-portal",
        "commercial",
        "customer",
    )
    customer.users.append(sales_portal)
    customer.save()
    Job(
        job_number="LINK-J-INTERNAL",
        customer=customer,
        participants=[sales_portal],
    ).save()
    _login(client, sales_portal)
    body = client.get("/admin/jobs/").get_data(as_text=True)
    assert "LINK-J-INTERNAL" in body
    assert "Hidden" not in body

    security_portal = _user(
        "security-portal",
        "security_administrator",
        "customer",
    )
    customer.users.append(security_portal)
    customer.save()
    _login(client, security_portal)
    scoped = client.get("/admin/jobs/").get_data(as_text=True)
    assert "LINK-J" in scoped
    assert "UNLINKED-J" not in scoped


def test_admin_navigation_and_mutations_are_filtered_without_legacy_admin(client):
    security = _user("admin-security", "security_administrator")
    _login(client, security)
    security_body = client.get("/admin/").get_data(as_text=True)
    assert "Users" in security_body
    assert "Roles &amp; permissions" in security_body
    assert "Audit log" in security_body
    assert "Application settings" not in security_body
    assert "System metrics" not in security_body

    # The administrator owns every administration surface, users and roles included.
    administrator = _user("admin-business", "administrator")
    _login(client, administrator)
    admin_home = client.get("/admin/").get_data(as_text=True)
    assert "Application settings" in admin_home
    assert "Fields &amp; exports" in admin_home
    assert "SolidWorks add-in" in admin_home
    assert "System metrics" in admin_home
    assert "New user" in client.get("/admin/users").get_data(as_text=True)
    assert client.get("/admin/users/new").status_code == 200
    assert client.get("/admin/roles/new").status_code == 200

    auditor = _user("admin-auditor", "auditor")
    _login(client, auditor)
    admin_body = client.get("/admin/").get_data(as_text=True)
    assert "Users" in admin_body
    assert "Roles &amp; permissions" in admin_body
    assert "Application settings" in admin_body
    assert "Fields &amp; exports" not in admin_body
    users_body = client.get("/admin/users").get_data(as_text=True)
    roles_body = client.get("/admin/roles/").get_data(as_text=True)
    settings_body = client.get("/admin/settings").get_data(as_text=True)
    assert "New user" not in users_body
    assert ">Edit</a>" not in users_body
    assert "New custom role" not in roles_body
    assert "Restore standard definitions" not in roles_body
    assert "Save settings" not in settings_body


def test_import_and_document_pack_entries_match_real_capabilities(client):
    part = _released_part()
    job = Job(
        job_number="PACK-J",
        bom=[JobBOMLine(pn=part.part_number, rev=part.revision, qty=1)],
    ).save()
    purchase = Order(
        order_number="PACK-PO",
        kind="purchase",
        lines=[OrderLine(pn=part.part_number, rev=part.revision, qty=1)],
    ).save()
    sales = Order(
        order_number="PACK-SO",
        kind="sales",
        lines=[OrderLine(pn=part.part_number, rev=part.revision, qty=1)],
    ).save()

    engineering = _user("pack-engineering", "engineering")
    _login(client, engineering)
    assert client.get(
        f"/api/docpacks/options?pn={part.part_number}&rev={part.revision}"
    ).status_code == 200
    assert "Open compiler" in client.get("/tools/").get_data(as_text=True)

    commercial = _user("pack-commercial", "commercial")
    _login(client, commercial)
    assert "Docpack export" in client.get(
        f"/admin/jobs/{job.id}"
    ).get_data(as_text=True)
    for order in (purchase, sales):
        assert "Docpack export" in client.get(
            f"/admin/orders/{order.id}"
        ).get_data(as_text=True)

    workshop = _user("pack-workshop", "workshop")
    _login(client, workshop)
    assert "Docpack export" not in client.get(
        f"/admin/jobs/{job.id}"
    ).get_data(as_text=True)
    assert client.post("/api/docpacks/build_job", json={"job_id": str(job.id)}).status_code == 403

    # Engineering runs low-risk imports; only the manager may override approved data.
    def _override_pack():
        import json
        import zipfile

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "ROLE_FLATBOM.txt",
                json.dumps(
                    {
                        "partnumber": part.part_number,
                        "revision": part.revision,
                        "description": "Override attempt",
                    }
                ),
            )
            archive.writestr(
                "ROLE_TREEBOM.txt",
                "ITEM NO.\tPART NUMBER\tRevision\tQTY.\n"
                f"1\t{part.part_number}\t{part.revision}\t1\n",
            )
        return buffer.getvalue()

    override_modes = {
        "data_mode": "replace_all",
        "bom_mode": "replace_all",
        "file_mode": "replace_all",
        "approval_mode": "replace_all",
    }
    _login(client, engineering)
    low_risk = client.post(
        "/api/upload/pack?dry_run=1",
        data={"file": (io.BytesIO(_override_pack()), "parts.zip")},
    )
    assert low_risk.status_code != 403
    denied = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(_override_pack()), "parts.zip"), **override_modes},
    )
    assert denied.status_code == 403
    assert "imports.override_approved" in (denied.get_json() or {}).get(
        "missing_permissions", []
    )

    manager = _user("import-manager", "engineering_manager")
    _login(client, manager)
    override = client.post(
        "/api/upload/pack",
        data={"file": (io.BytesIO(_override_pack()), "parts.zip"), **override_modes},
    )
    assert override.status_code != 403

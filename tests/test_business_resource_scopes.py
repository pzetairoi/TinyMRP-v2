import uuid

from app.models.auth import Role, User
from app.models.customer import Customer
from app.models.job import Job, JobStage
from app.models.order import Order, OrderLine
from app.models.supplier import Supplier
from app.services.api_tokens import create_token
from app.services.standard_roles import STANDARD_ROLES
from app.services.permissions import PERMISSION_REGISTRY


def _role(name, permissions):
    role = Role(name=name, permissions=list(permissions))
    role.save()
    return role


def _standard_role(name):
    existing = Role.objects(name=name).first()
    if existing:
        return existing
    definition = STANDARD_ROLES[name]
    return _role(name, definition.permissions)


def _user(email, *roles):
    user = User(
        email=email,
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=list(roles),
    )
    user.save()
    return user


def _headers(user):
    _, token = create_token(user, "stage3a")
    return {"Authorization": f"Bearer {token}"}


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = user.get_id()
        session["_fresh"] = True


def _numbers(response, key):
    return {item[key] for item in response.get_json()["items"]}


def test_commercial_covers_both_order_kinds_and_both_company_types(client):
    purchase = Order(order_number="PO-SCOPE", kind="purchase").save()
    sales = Order(order_number="SO-SCOPE", kind="sales").save()
    customer = Customer(code="C-SCOPE", name="Scoped Customer").save()
    supplier = Supplier(code="S-SCOPE", name="Scoped Supplier").save()

    commercial = _user("commercial@stage3a.test", _standard_role("commercial"))
    headers = _headers(commercial)

    response = client.get("/api/orders", headers=headers)
    assert {purchase.order_number, sales.order_number} <= _numbers(
        response, "order_number"
    )
    for order in (purchase, sales):
        assert client.get(
            f"/api/orders/{order.order_number}",
            headers=headers,
        ).status_code == 200

    assert client.put(
        f"/api/customers/{customer.code}",
        headers=headers,
        json={"credit_limit": 100},
    ).status_code == 200
    assert client.put(
        f"/api/suppliers/{supplier.code}",
        headers=headers,
        json={"rating": 4},
    ).status_code == 200


def test_commercial_plans_jobs_and_runs_the_full_order_workflow(client):
    commercial = _user("commercial.flow@stage3a.test", _standard_role("commercial"))
    headers = _headers(commercial)

    assert client.post(
        "/api/jobs",
        headers=headers,
        json={"job_number": "JOB-PLAN", "title": "Plan"},
    ).status_code == 200
    assert client.put(
        "/api/jobs/JOB-PLAN",
        headers=headers,
        json={"description": "Prepared"},
    ).status_code == 200

    assert client.post(
        "/api/orders",
        headers=headers,
        json={"order_number": "PO-PLAN", "kind": "purchase"},
    ).status_code == 200
    Order.objects(order_number="PO-PLAN").update(status="submitted")
    assert client.post(
        "/api/orders/PO-PLAN/approve",
        headers=headers,
        json={},
    ).status_code == 200


def test_workshop_updates_stages_shop_wide_without_commercial_authority(client):
    workshop = _user("workshop@stage3a.test", _standard_role("workshop"))
    stage = JobStage(stage_id="stage-1", name="Cut")
    assigned = Job(
        job_number="JOB-ASSIGNED",
        participants=[workshop],
        stages=[stage],
    ).save()
    other = Job(job_number="JOB-OTHER").save()
    Order(order_number="PO-NO-EDIT", kind="purchase").save()
    headers = _headers(workshop)

    # Workshop is shop-wide: unassigned jobs stay visible.
    response = client.get("/api/jobs", headers=headers)
    assert {assigned.job_number, other.job_number} <= _numbers(response, "job_number")
    assert client.get("/api/jobs/JOB-OTHER", headers=headers).status_code == 200
    assert client.post(
        "/api/jobs/JOB-ASSIGNED/stages/stage-1/complete",
        headers=headers,
        json={},
    ).status_code == 200
    assert client.put(
        "/api/jobs/JOB-ASSIGNED",
        headers=headers,
        json={"description": "No global editing"},
    ).status_code == 403
    assert client.put(
        "/api/orders/PO-NO-EDIT",
        headers=headers,
        json={"description": "No"},
    ).status_code == 403


def test_read_only_roles_can_read_but_not_write(client):
    customer = Customer(code="C-READ", name="Read Customer").save()
    supplier = Supplier(code="S-READ", name="Read Supplier").save()
    Job(job_number="JOB-READ").save()
    Order(
        order_number="PO-READ",
        kind="purchase",
        total=200,
        lines=[OrderLine(pn="P1", unit_price=200)],
    ).save()

    for role_name in ("internal", "auditor"):
        user = _user(
            f"{role_name}@stage3a.test",
            _standard_role(role_name),
        )
        headers = _headers(user)
        assert client.get("/api/jobs", headers=headers).status_code == 200
        assert client.get("/api/orders", headers=headers).status_code == 200
        assert client.get("/api/customers", headers=headers).status_code == 200
        assert client.get("/api/suppliers", headers=headers).status_code == 200
        assert client.put(
            f"/api/customers/{customer.code}",
            headers=headers,
            json={"name": "No"},
        ).status_code == 403
        assert client.put(
            f"/api/suppliers/{supplier.code}",
            headers=headers,
            json={"name": "No"},
        ).status_code == 403


def test_customer_portal_scope_applies_to_lists_details_and_counts(client):
    portal = _user(
        "customer.portal@stage3a.test",
        _standard_role("customer"),
    )
    linked = Customer(code="C-LINKED", name="Linked", users=[portal]).save()
    other = Customer(code="C-OTHER", name="Other").save()
    linked_job = Job(job_number="JOB-C-LINKED", customer=linked).save()
    Job(job_number="JOB-C-OTHER", customer=other).save()
    Order(
        order_number="SO-C-LINKED",
        kind="sales",
        customer=linked,
        job=linked_job,
        total=25,
    ).save()
    Order(
        order_number="SO-C-OTHER",
        kind="sales",
        customer=other,
        total=100,
    ).save()
    Order(
        order_number="PO-C-LINKED",
        kind="purchase",
        customer=linked,
    ).save()
    headers = _headers(portal)

    assert _numbers(
        client.get("/api/customers", headers=headers),
        "code",
    ) == {linked.code}
    assert _numbers(
        client.get("/api/jobs", headers=headers),
        "job_number",
    ) == {linked_job.job_number}
    assert _numbers(
        client.get("/api/orders", headers=headers),
        "order_number",
    ) == {"SO-C-LINKED"}
    assert client.get(
        f"/api/customers/{other.code}",
        headers=headers,
    ).status_code == 404
    assert client.get(
        "/api/orders/SO-C-OTHER",
        headers=headers,
    ).status_code == 404
    stats = client.get("/api/orders/stats", headers=headers).get_json()
    assert sum(stats["status_counts"].values()) == 1
    assert stats["revenue_month"] is None


def test_supplier_portal_scope_applies_to_issued_orders_related_jobs_and_counts(
    client,
):
    portal = _user(
        "supplier.portal@stage3a.test",
        _standard_role("supplier"),
    )
    linked = Supplier(code="S-LINKED", name="Linked", users=[portal]).save()
    other = Supplier(code="S-OTHER", name="OTHER-SUPPLIER-SECRET").save()
    confidential_customer = Customer(
        code="C-SUPPLIER-HIDDEN",
        name="Confidential Customer",
    ).save()
    related = Job(
        job_number="JOB-S-LINKED",
        customer=confidential_customer,
    ).save()
    hidden = Job(job_number="JOB-S-OTHER").save()
    Order(
        order_number="PO-S-LINKED",
        kind="purchase",
        supplier=linked,
        job=related,
    ).save()
    Order(
        order_number="PO-S-OTHER",
        kind="purchase",
        supplier=other,
        job=hidden,
    ).save()
    Order(
        order_number="SO-S-LINKED",
        kind="sales",
        supplier=linked,
        job=hidden,
    ).save()
    headers = _headers(portal)

    assert _numbers(
        client.get("/api/suppliers", headers=headers),
        "code",
    ) == {linked.code}
    assert _numbers(
        client.get("/api/orders", headers=headers),
        "order_number",
    ) == {"PO-S-LINKED"}
    assert _numbers(
        client.get("/api/jobs", headers=headers),
        "job_number",
    ) == {related.job_number}
    job_payload = client.get("/api/jobs", headers=headers).get_json()["items"][0]
    assert "customer" not in job_payload
    assert "customer_id" not in job_payload
    _login(client, portal)
    job_html = client.get(f"/admin/jobs/{related.id}").get_data(as_text=True)
    assert confidential_customer.name not in job_html
    assert other.name not in job_html
    assert client.get(
        f"/api/suppliers/{other.code}",
        headers=headers,
    ).status_code == 404
    assert client.get(
        "/api/orders/PO-S-OTHER",
        headers=headers,
    ).status_code == 404
    stats = client.get("/api/orders/stats", headers=headers).get_json()
    assert sum(stats["status_counts"].values()) == 1


def test_security_administrator_has_no_implicit_business_access(client):
    Job(job_number="JOB-ADMIN-DENY").save()
    user = _user(
        "security_administrator@stage3a.test",
        _standard_role("security_administrator"),
    )
    headers = _headers(user)
    assert client.get("/api/jobs", headers=headers).status_code == 403
    assert client.get("/api/orders", headers=headers).status_code == 403
    assert client.get("/api/customers", headers=headers).status_code == 403
    assert client.get("/api/suppliers", headers=headers).status_code == 403


def test_multiple_roles_union_only_permissions_that_grant_the_operation(client):
    linked_user = _user(
        "multi.customer@stage3a.test",
        _standard_role("customer"),
        _standard_role("internal"),
    )
    linked_customer = Customer(
        code="C-MULTI",
        name="Multi",
        users=[linked_user],
    ).save()
    Customer(code="C-MULTI-OTHER", name="Multi Other").save()
    Job(job_number="JOB-MULTI-LINKED", customer=linked_customer).save()
    Job(job_number="JOB-MULTI-GLOBAL").save()
    assert _numbers(
        client.get("/api/jobs", headers=_headers(linked_user)),
        "job_number",
    ) == {"JOB-MULTI-LINKED"}

    production_planner = _user(
        "multi.production@stage3a.test",
        _standard_role("workshop"),
        _standard_role("commercial"),
    )
    assert _numbers(
        client.get("/api/jobs", headers=_headers(production_planner)),
        "job_number",
    ) == {"JOB-MULTI-LINKED", "JOB-MULTI-GLOBAL"}

    security_portal = _user(
        "multi.security@stage3a.test",
        _standard_role("security_administrator"),
        _standard_role("customer"),
    )
    linked_customer.users.append(security_portal)
    linked_customer.save()
    assert _numbers(
        client.get("/api/jobs", headers=_headers(security_portal)),
        "job_number",
    ) == {"JOB-MULTI-LINKED"}

    custom = _user(
        "multi.custom@stage3a.test",
        _role("custom_business_reader", ["jobs.read"]),
    )
    assert _numbers(
        client.get("/api/jobs", headers=_headers(custom)),
        "job_number",
    ) == {"JOB-MULTI-LINKED", "JOB-MULTI-GLOBAL"}


def test_engineering_roles_stop_short_of_destructive_and_commercial_authority():
    user = _user(
        "multi.engineering@stage3a.test",
        _standard_role("engineering"),
        _standard_role("engineering_manager"),
    )
    permissions = {
        permission
        for role in user.roles
        for permission in (role.permissions or [])
    }

    assert {
        "parts.update",
        "reviews.approve",
        "imports.override_approved",
    } <= permissions
    assert {
        "parts.purge",
        "files.purge",
        "orders.approve",
        "security.users.manage",
    }.isdisjoint(permissions)


def test_portal_role_combined_with_commercial_keeps_external_boundary(client):
    portal = _user(
        "multi.supplier@stage3a.test",
        _standard_role("supplier"),
        _standard_role("commercial"),
    )
    supplier = Supplier(code="S-MULTI", name="Supplier Multi", users=[portal]).save()
    Order(
        order_number="PO-MULTI-LINKED",
        kind="purchase",
        supplier=supplier,
    ).save()
    Order(order_number="PO-MULTI-OTHER", kind="purchase").save()
    Order(order_number="SO-MULTI", kind="sales").save()

    # A portal role is a sticky security boundary.  The additional commercial
    # role neither widens the order rows nor restores commercial mutations.
    assert _numbers(
        client.get("/api/orders", headers=_headers(portal)),
        "order_number",
    ) == {"PO-MULTI-LINKED"}


def test_financial_permissions_deny_reads_and_mixed_writes_without_partial_save(
    client,
):
    customer = Customer(
        code="C-FIN",
        name="Original Customer",
        credit_limit=100,
        customer_type="oem",
    ).save()
    supplier = Supplier(
        code="S-FIN",
        name="Original Supplier",
        rating=4,
    ).save()
    order = Order(
        order_number="PO-FIN",
        kind="purchase",
        description="Original Order",
        total=100,
        shipping_cost=10,
    ).save()
    basic = _user(
        "basic.finance@stage3a.test",
        _role(
            "basic_business_editor",
            [
                "orders.read",
                "orders.update",
                "customers.read",
                "customers.update",
                "suppliers.read",
                "suppliers.update",
            ],
        ),
    )
    basic_headers = _headers(basic)

    customer_read = client.get(
        f"/api/customers/{customer.code}",
        headers=basic_headers,
    ).get_json()["customer"]
    assert customer_read["credit_limit"] is None
    assert customer_read["customer_type"] is None
    assert client.get(
        "/api/customers?type=oem",
        headers=basic_headers,
    ).status_code == 403
    assert client.get(
        "/api/suppliers?sort=rating",
        headers=basic_headers,
    ).status_code == 403
    assert client.get(
        "/api/orders?sort=total",
        headers=basic_headers,
    ).status_code == 403
    assert client.get(
        "/api/orders/stats",
        headers=basic_headers,
    ).get_json()["revenue_month"] is None

    assert client.put(
        f"/api/customers/{customer.code}",
        headers=basic_headers,
        json={"name": "Changed", "credit_limit": 999},
    ).status_code == 403
    assert client.put(
        f"/api/suppliers/{supplier.code}",
        headers=basic_headers,
        json={"name": "Changed", "rating": 1},
    ).status_code == 403
    assert client.put(
        f"/api/orders/{order.order_number}",
        headers=basic_headers,
        json={"description": "Changed", "shipping_cost": 999},
    ).status_code == 403
    customer.reload()
    supplier.reload()
    order.reload()
    assert customer.name == "Original Customer"
    assert customer.credit_limit == 100
    assert supplier.name == "Original Supplier"
    assert supplier.rating == 4
    assert order.description == "Original Order"
    assert order.shipping_cost == 10

    financial = _user(
        "allowed.finance@stage3a.test",
        _role(
            "financial_business_editor",
            [
                "orders.read",
                "orders.update",
                "orders.financial.read",
                "orders.financial.update",
                "customers.read",
                "customers.update",
                "customers.financial.read",
                "customers.financial.update",
                "suppliers.read",
                "suppliers.update",
                "suppliers.financial.read",
                "suppliers.financial.update",
            ],
        ),
    )
    headers = _headers(financial)
    assert client.put(
        f"/api/orders/{order.order_number}",
        headers=headers,
        json={"shipping_cost": 20},
    ).status_code == 200
    assert client.put(
        f"/api/customers/{customer.code}",
        headers=headers,
        json={"credit_limit": 200},
    ).status_code == 200
    assert client.put(
        f"/api/suppliers/{supplier.code}",
        headers=headers,
        json={"rating": 5},
    ).status_code == 200
    assert client.get(
        "/api/orders/stats",
        headers=headers,
    ).get_json()["revenue_month"] == 100


def test_invalid_inaccessible_and_scope_failure_identifiers_fail_closed(
    client,
    monkeypatch,
):
    portal = _user(
        "failclosed@stage3a.test",
        _standard_role("customer"),
    )
    linked = Customer(code="C-FAIL-LINK", name="Linked", users=[portal]).save()
    other = Customer(code="C-FAIL-OTHER", name="Other").save()
    Job(job_number="JOB-FAIL-LINK", customer=linked).save()
    Job(job_number="JOB-FAIL-OTHER", customer=other).save()
    headers = _headers(portal)

    assert client.get("/api/jobs/not-an-id", headers=headers).status_code == 404
    assert client.get(
        "/api/jobs/JOB-FAIL-OTHER",
        headers=headers,
    ).status_code == 404

    from app.services import authorization

    monkeypatch.setattr(
        authorization,
        "_build_scope_context",
        lambda _user: (_ for _ in ()).throw(RuntimeError("scope failure")),
    )
    response = client.get("/api/jobs", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["items"] == []
    assert response.get_json()["total"] == 0


def test_archive_endpoints_preserve_records_and_reject_unknown_fields(client):
    # Was an empty role named "admin", which only worked because that name
    # bypassed the permission registry. Archiving needs real permissions.
    admin = _user(
        "archive.administrator@stage3a.test",
        _role("administrator", sorted(PERMISSION_REGISTRY)),
    )
    headers = _headers(admin)
    job = Job(job_number="JOB-ARCHIVE").save()
    order = Order(order_number="PO-ARCHIVE", kind="purchase").save()
    customer = Customer(code="C-ARCHIVE", name="Archive Customer").save()
    supplier = Supplier(code="S-ARCHIVE", name="Archive Supplier").save()

    assert client.delete(
        f"/api/jobs/{job.job_number}",
        headers=headers,
    ).status_code == 200
    assert client.delete(
        f"/api/orders/{order.order_number}",
        headers=headers,
    ).status_code == 200
    assert client.put(
        f"/api/customers/{customer.code}",
        headers=headers,
        json={"unexpected": True},
    ).status_code == 400
    assert client.put(
        f"/api/suppliers/{supplier.code}",
        headers=headers,
        json={"unexpected": True},
    ).status_code == 400
    job.reload()
    order.reload()
    assert job.is_deleted is True
    assert job.status == "cancelled"
    assert order.status == "cancelled"

    _login(client, admin)
    assert client.post(
        f"/admin/customers/{customer.id}/delete",
    ).status_code == 302
    assert client.post(
        f"/admin/suppliers/{supplier.id}/delete",
    ).status_code == 302
    customer.reload()
    supplier.reload()
    assert customer.status == "inactive"
    assert supplier.status == "inactive"


def test_ordinary_company_updates_cannot_change_portal_user_relationships(client):
    linked = _user(
        "linked.portal@stage3a.test",
        _standard_role("customer"),
    )
    sales = _user(
        "sales.portal.assignment@stage3a.test",
        _standard_role("commercial"),
    )
    customer = Customer(
        code="C-PORTAL-USERS",
        name="Portal Users Customer",
        users=[linked],
    ).save()
    _login(client, sales)
    response = client.post(
        f"/admin/customers/{customer.id}/edit",
        data={"users": str(sales.id)},
    )
    assert response.status_code == 403
    customer.reload()
    assert [str(user.id) for user in customer.users] == [str(linked.id)]

    procurement = _user(
        "procurement.portal.assignment@stage3a.test",
        _standard_role("commercial"),
    )
    supplier = Supplier(
        code="S-PORTAL-USERS",
        name="Portal Users Supplier",
        users=[linked],
    ).save()
    _login(client, procurement)
    response = client.post(
        f"/admin/suppliers/{supplier.id}/edit",
        data={"users": str(procurement.id)},
    )
    assert response.status_code == 403
    supplier.reload()
    assert [str(user.id) for user in supplier.users] == [str(linked.id)]


def test_company_portal_assignment_requires_matching_canonical_role(client):
    admin = _user(
        "portal.assignment.admin@stage3a.test",
        _standard_role("administrator"),
    )
    internal = _user(
        "portal.assignment.internal@stage3a.test",
        _standard_role("internal"),
    )
    customer_user = _user(
        "portal.assignment.customer@stage3a.test",
        _standard_role("customer"),
    )
    supplier_user = _user(
        "portal.assignment.supplier@stage3a.test",
        _standard_role("supplier"),
    )
    customer = Customer(code="C-ROLE-GUARD", name="Role Guard Customer").save()
    supplier = Supplier(code="S-ROLE-GUARD", name="Role Guard Supplier").save()
    _login(client, admin)

    assert client.post(
        f"/admin/customers/{customer.id}/edit",
        data={"users": str(internal.id)},
    ).status_code == 400
    assert client.post(
        f"/admin/suppliers/{supplier.id}/edit",
        data={"users": str(customer_user.id)},
    ).status_code == 400
    customer.reload()
    supplier.reload()
    assert customer.users == []
    assert supplier.users == []

    assert client.post(
        f"/admin/customers/{customer.id}/edit",
        data={"users": str(customer_user.id)},
    ).status_code == 302
    assert client.post(
        f"/admin/suppliers/{supplier.id}/edit",
        data={"users": str(supplier_user.id)},
    ).status_code == 302
    customer.reload()
    supplier.reload()
    assert [str(user.id) for user in customer.users] == [str(customer_user.id)]
    assert [str(user.id) for user in supplier.users] == [str(supplier_user.id)]

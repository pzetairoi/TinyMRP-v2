import uuid

import pytest

from app.models.artifact import PartFile
from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.common import Contact
from app.models.customer import Customer
from app.models.job import Job, JobBOMLine, JobStage
from app.models.order import Order, OrderLine
from app.models.part import Part
from app.models.part_annotation import PartAnnotation
from app.models.supplier import Supplier
from app.services.field_config import save_field_config
from app.services.field_policies import filter_response_fields
from app.services.standard_roles import STANDARD_ROLES


def _role(name, permissions):
    return Role(name=name, permissions=list(permissions)).save()


def _standard_role(name):
    existing = Role.objects(name=name).first()
    if existing:
        return existing
    definition = STANDARD_ROLES[name]
    return _role(name, definition.permissions)


def _user(email, *roles):
    return User(
        email=email,
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=list(roles),
    ).save()


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = user.get_id()
        session["_fresh"] = True


def _released(part_number, revision="A", **kwargs):
    attrs = dict(kwargs.pop("attrs", {}) or {})
    attrs["approvedby"] = attrs.get("approvedby") or "QA"
    return Part(
        part_number=part_number,
        revision=revision,
        attrs=attrs,
        **kwargs,
    ).save()


def test_external_policy_filters_sensitive_fields_and_copies_values(app):
    with app.app_context():
        user = _user(
            "policy-copy@example.test",
            _role("customer_portal", ["parts.read"]),
        )
        nested = {"safe": [{"value": 1}]}
        payload = {
            "part_number": "COPY-1",
            "thumb_urls": nested,
            "internal_cost": 10,
            "storage_path": "C:/private",
            "unknown_custom": "must not appear",
        }

        filtered = filter_response_fields("parts", user, payload)

        assert filtered == {
            "part_number": "COPY-1",
            "thumb_urls": nested,
        }
        assert filtered["thumb_urls"] is not nested
        assert filtered["thumb_urls"]["safe"] is not nested["safe"]
        assert payload["storage_path"] == "C:/private"


def test_policy_unknown_resource_and_exception_fail_closed(app, monkeypatch):
    with app.app_context():
        user = _user(
            "policy-fail@example.test",
            _role("policy-fail", ["parts.read"]),
        )
        assert filter_response_fields(
            "unregistered_resource",
            user,
            {"secret": "value"},
        ) == {}

        monkeypatch.setattr(
            "app.services.field_policies._internal_fields",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        assert filter_response_fields(
            "parts",
            user,
            {"part_number": "FAIL-1", "secret": "value"},
        ) == {}


def test_part_list_detail_bom_and_dashboard_apply_equivalent_policies(
    client,
    app,
):
    user = _user(
        "engineering-route@field-policy.test",
        _standard_role("engineering"),
    )
    _login(client, user)
    with app.app_context():
        save_field_config(
            {
                "custom_fields": [
                    {
                        "id": "engineering_grade",
                        "label": "Engineering Grade",
                        "source_path": "attrs.engineering_grade",
                    },
                    {
                        "id": "secret_token",
                        "label": "Secret Token",
                        "source_path": "attrs.secret_token",
                    },
                ],
                "contexts": {
                    "parts_list": {
                        "allowed_field_ids": [
                            "part_number",
                            "revision",
                            "description",
                            "engineering_grade",
                            "secret_token",
                        ],
                        "default_field_ids": [
                            "part_number",
                            "engineering_grade",
                        ],
                    },
                    "part_detail_summary": {
                        "allowed_field_ids": [
                            "description",
                            "engineering_grade",
                            "secret_token",
                        ],
                        "default_field_ids": [
                            "description",
                            "engineering_grade",
                        ],
                    },
                    "bom_tree": {
                        "allowed_field_ids": [
                            "part_number",
                            "revision",
                            "description",
                            "qty",
                            "engineering_grade",
                            "secret_token",
                        ],
                        "default_field_ids": [
                            "part_number",
                            "qty",
                            "engineering_grade",
                        ],
                    },
                },
            }
        )
    root = _released(
        "FIELD-ROOT",
        attrs={
            "engineering_grade": "G1",
            "secret_token": "never",
            "storage_path": "C:/vault/private",
        },
    )
    child = _released(
        "FIELD-CHILD",
        attrs={
            "engineering_grade": "G2",
            "secret_token": "never-child",
        },
    )
    BOMLink(
        parent_pn=root.part_number,
        parent_rev=root.revision,
        child_pn=child.part_number,
        child_rev=child.revision,
        qty=2,
    ).save()

    listing = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {}},
    ).get_json()["data"]
    root_row = next(row for row in listing if row["part_number"] == root.part_number)
    assert root_row["engineering_grade"] == "G1"
    assert "secret_token" not in root_row

    detail = client.get(
        f"/api/part_detail?pn={root.part_number}&rev={root.revision}"
    ).get_json()
    attributes = detail["part"]["attributes"]
    assert attributes["engineering_grade"] == "G1"
    assert "secret_token" not in attributes
    assert "storage_path" not in attributes
    assert "secret_token" not in detail["part"]["field_values"]
    assert "arena_file_link_base_url" not in detail

    tree = client.get(
        f"/api/bom_tree?parent={root.part_number}&parent_rev={root.revision}"
    ).get_json()
    assert tree[0]["data"]["engineering_grade"] == "G2"
    assert "secret_token" not in tree[0]["data"]
    assert tree[0]["data"]["attrs"]["engineering_grade"] == "G2"
    assert "secret_token" not in tree[0]["data"]["attrs"]

    dashboard = client.get("/api/dashboard/summary").get_json()
    assert set(dashboard) <= {
        "counts",
        "doc_coverage",
        "data_health",
        "top_processes",
        "recent_parts",
        "top_hardware",
    }


def test_internal_viewer_and_portal_do_not_receive_review_or_revision_history(
    client,
):
    part = _released(
        "STRICT-PART",
        attrs={
            "material": "Steel",
            "approvedby": "reviewer@example.test",
            "private_path": "C:/private",
        },
    )
    Part(
        part_number=part.part_number,
        revision="B",
        description="Draft",
        attrs={"material": "Titanium"},
    ).save()

    viewer = _user(
        "internal-viewer@field-policy.test",
        _standard_role("internal"),
    )
    _login(client, viewer)
    viewer_detail = client.get(
        f"/api/part_detail?pn={part.part_number}&rev=A"
    ).get_json()
    assert viewer_detail["comments"] == []
    assert viewer_detail["uploader_profile"] == {}
    assert viewer_detail["approver_profile"] == {}
    assert all(
        row["revision"] == "A"
        for row in viewer_detail["other_versions"]
    )

    portal = _user(
        "customer-portal@field-policy.test",
        _standard_role("customer"),
    )
    customer = Customer(
        code="PORTAL-CUSTOMER",
        name="Portal Customer",
        users=[portal],
    ).save()
    Job(
        job_number="PORTAL-JOB",
        customer=customer,
        bom=[JobBOMLine(pn=part.part_number, rev=part.revision, qty=1)],
    ).save()
    _login(client, portal)
    portal_detail = client.get(
        f"/api/part_detail?pn={part.part_number}&rev=A"
    ).get_json()
    assert portal_detail["other_versions"] == []
    assert portal_detail["comments"] == []
    assert "attributes" not in portal_detail["part"]
    assert "whereused" in portal_detail
    assert portal_detail["whereused"] == []


def test_production_operator_receives_comments_for_an_assigned_part(client):
    operator = _user(
        "production-comments@field-policy.test",
        _standard_role("workshop"),
    )
    part = _released("PRODUCTION-COMMENT")
    Job(
        job_number="PRODUCTION-COMMENT-JOB",
        participants=[operator],
        bom=[JobBOMLine(pn=part.part_number, rev=part.revision, qty=1)],
    ).save()
    PartAnnotation(
        part_number=part.part_number,
        revision=part.revision,
        comments=[
            {
                "id": "production-comment",
                "author": "planner@example.test",
                "text": "Check this dimension before machining.",
                "status": "open",
            }
        ],
    ).save()
    _login(client, operator)

    detail = client.get(
        f"/api/part_detail?pn={part.part_number}&rev={part.revision}"
    )

    assert detail.status_code == 200
    payload = detail.get_json()
    assert payload["can_parts_note"] is True
    assert payload["comments"][0]["id"] == "production-comment"
    assert payload["comments"][0]["text"] == "Check this dimension before machining."
    assert "author" not in payload["comments"][0]


def test_file_metadata_retains_protected_urls_without_paths_or_hashes(
    client,
    app,
    tmp_path,
):
    user = _user(
        "file-policy@field-policy.test",
        _standard_role("engineering"),
    )
    _login(client, user)
    part = _released("FILE-POLICY")
    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
    path = tmp_path / "png" / "FILE-POLICY_REV_A.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"png")
    file_record = PartFile(
        part_number=part.part_number,
        revision=part.revision,
        ext_group="png",
        ext="png",
        rel_path="png/FILE-POLICY_REV_A.png",
        path=str(path),
        sha256="private-hash",
        is_dwg=True,
        size=3,
    ).save()

    row = client.get(
        f"/api/part_images?pn={part.part_number}&rev=A&mode=drawing"
    ).get_json()[0]
    assert row["urls"]
    assert row["source_file_id"] == str(file_record.id)
    assert "source_fingerprint" in row
    assert "path" not in row
    assert "rel_path" not in row
    assert "sha256" not in row
    assert "http_url" not in row

    overview = client.get(
        f"/api/parts/{part.part_number}/files_overview?rev=A"
    ).get_json()
    overview_row = overview["current_revision"]["files"][0]
    assert overview_row["url"]
    assert "id" not in overview_row
    assert "db_id" not in overview_row
    assert "collection" not in overview_row
    assert "rel_path" not in overview_row


def test_job_order_company_and_nested_field_policies(client):
    customer = Customer(
        code="FIELD-CUSTOMER",
        name="Field Customer",
        credit_limit=5000,
        payment_terms="NET30",
        contacts=[
            Contact(
                name="Private Contact",
                email="private@example.test",
                phone="123",
            )
        ],
    ).save()
    supplier = Supplier(
        code="FIELD-SUPPLIER",
        name="Field Supplier",
        rating=5,
        payment_terms="NET45",
    ).save()
    part = _released("FIELD-LINE")
    job = Job(
        job_number="FIELD-JOB",
        title="Production",
        customer=customer,
        part_number=part.part_number,
        part_revision=part.revision,
        estimated_hours=10,
        stages=[
            JobStage(
                name="Cut",
                assigned_to="operator@example.test",
                note="Use fixture",
                estimated_hours=2,
            )
        ],
        bom=[JobBOMLine(pn=part.part_number, rev=part.revision, qty=2)],
    ).save()
    order = Order(
        order_number="FIELD-ORDER",
        kind="purchase",
        supplier=supplier,
        job=job,
        subtotal=100,
        total=110,
        currency="AUD",
        lines=[
            OrderLine(
                pn=part.part_number,
                rev=part.revision,
                qty=2,
                note="Internal note",
                unit_price=50,
                line_total=100,
            )
        ],
    ).save()

    planner = _user(
        "planner-fields@example.test",
        _standard_role("commercial"),
    )
    _login(client, planner)
    planner_job = client.get(f"/api/jobs/{job.job_number}").get_json()["job"]
    assert planner_job["estimated_hours"] == 10
    assert planner_job["customer"] == customer.name
    assert planner_job["customer_id"] == str(customer.id)
    planner_order = client.get(
        f"/api/orders/{order.order_number}"
    ).get_json()["order"]
    # Commercial carries order financial authority.
    assert planner_order["total"] == 110
    assert planner_order["lines"][0]["unit_price"] == 50
    assert planner_order["supplier"] == supplier.name
    assert "note" in planner_order["lines"][0]

    procurement = _user(
        "procurement-fields@example.test",
        _standard_role("commercial"),
    )
    _login(client, procurement)
    purchase = client.get(
        f"/api/orders/{order.order_number}"
    ).get_json()["order"]
    assert purchase["supplier"] == supplier.name
    assert purchase["total"] == 110
    assert purchase["lines"][0]["unit_price"] == 50
    supplier_payload = client.get(
        f"/api/suppliers/{supplier.code}"
    ).get_json()["supplier"]
    assert supplier_payload["rating"] == 5
    assert supplier_payload["payment_terms"] == "NET45"
    assert "users" not in supplier_payload

    sales = _user(
        "sales-fields@example.test",
        _standard_role("commercial"),
    )
    _login(client, sales)
    customer_payload = client.get(
        f"/api/customers/{customer.code}"
    ).get_json()["customer"]
    assert customer_payload["credit_limit"] == 5000
    assert customer_payload["contacts"][0]["email"] == "private@example.test"
    assert "users" not in customer_payload


def test_production_and_portal_job_fields_are_strict(client):
    part = _released("OP-PART")
    customer_portal = _user(
        "job-customer-portal@example.test",
        _standard_role("customer"),
    )
    customer = Customer(
        code="OP-CUSTOMER",
        name="Operator Customer",
        users=[customer_portal],
    ).save()
    operator = _user(
        "production-fields@example.test",
        _standard_role("workshop"),
    )
    job = Job(
        job_number="OP-JOB",
        title="Assigned operation",
        customer=customer,
        participants=[operator],
        part_number=part.part_number,
        part_revision=part.revision,
        estimated_hours=20,
        stages=[
            JobStage(
                name="Assemble",
                assigned_to="operator@example.test",
                note="Operational note",
            )
        ],
    ).save()

    _login(client, operator)
    operator_payload = client.get(
        f"/api/jobs/{job.job_number}"
    ).get_json()["job"]
    assert operator_payload["job_number"] == job.job_number
    assert operator_payload["stages"][0]["note"] == "Operational note"
    # Workshop reads shop-wide internal job fields but never commercial ones.
    assert "customer" not in operator_payload
    assert "total" not in operator_payload

    _login(client, customer_portal)
    portal_payload = client.get(
        f"/api/jobs/{job.job_number}"
    ).get_json()["job"]
    assert portal_payload["job_number"] == job.job_number
    assert "stages" not in portal_payload
    assert "customer" not in portal_payload
    assert "estimated_hours" not in portal_payload


def test_financial_fields_are_null_or_absent_consistently(client):
    customer = Customer(
        code="NO-FIN-C",
        name="No Finance Customer",
        credit_limit=999,
        payment_terms="SECRET",
    ).save()
    supplier = Supplier(
        code="NO-FIN-S",
        name="No Finance Supplier",
        rating=5,
        payment_terms="SECRET",
    ).save()
    part = _released("NO-FIN-PART")
    order = Order(
        order_number="NO-FIN-ORDER",
        kind="sales",
        customer=customer,
        total=250,
        lines=[
            OrderLine(
                pn=part.part_number,
                rev=part.revision,
                qty=1,
                unit_price=250,
                line_total=250,
            )
        ],
    ).save()
    viewer = _user(
        "no-finance@example.test",
        _standard_role("internal"),
    )
    _login(client, viewer)

    order_payload = client.get(
        f"/api/orders/{order.order_number}"
    ).get_json()["order"]
    assert order_payload["total"] is None
    assert order_payload["lines"][0]["unit_price"] is None
    stats = client.get("/api/orders/stats").get_json()
    assert stats["revenue_month"] is None
    assert stats["avg_order_value"] is None
    customer_payload = client.get(
        f"/api/customers/{customer.code}"
    ).get_json()["customer"]
    assert customer_payload["credit_limit"] is None
    assert customer_payload["payment_terms"] is None
    supplier_payload = client.get(
        f"/api/suppliers/{supplier.code}"
    ).get_json()["supplier"]
    assert supplier_payload["rating"] is None
    assert supplier_payload["payment_terms"] is None


def test_portal_self_profiles_cross_domain_isolation_and_order_fields(client):
    customer_portal = _user(
        "customer-self@example.test",
        _standard_role("customer"),
    )
    supplier_portal = _user(
        "supplier-self@example.test",
        _standard_role("supplier"),
    )
    customer = Customer(
        code="SELF-C",
        name="Self Customer",
        users=[customer_portal],
        credit_limit=9000,
        payment_terms="PRIVATE-C",
        contacts=[
            Contact(
                name="Private Customer Contact",
                email="private-c@example.test",
            )
        ],
    ).save()
    supplier = Supplier(
        code="SELF-S",
        name="Self Supplier",
        users=[supplier_portal],
        rating=5,
        payment_terms="PRIVATE-S",
        contacts=[
            Contact(
                name="Private Supplier Contact",
                email="private-s@example.test",
            )
        ],
    ).save()
    part = _released(
        "SELF-PART",
        attrs={"supplier": supplier.name},
        category="Internal Category",
        uom="EA",
    )
    sales = Order(
        order_number="SELF-SALES",
        kind="sales",
        customer=customer,
        supplier=supplier,
        total=1000,
        lines=[
            OrderLine(
                pn=part.part_number,
                rev=part.revision,
                qty=1,
                unit_price=1000,
                line_total=1000,
            )
        ],
    ).save()
    purchase = Order(
        order_number="SELF-PURCHASE",
        kind="purchase",
        customer=customer,
        supplier=supplier,
        total=700,
        lines=[
            OrderLine(
                pn=part.part_number,
                rev=part.revision,
                qty=1,
                unit_price=700,
                line_total=700,
            )
        ],
    ).save()

    _login(client, customer_portal)
    own_customer = client.get(
        f"/api/customers/{customer.code}"
    ).get_json()["customer"]
    assert own_customer["credit_limit"] is None
    assert own_customer["payment_terms"] is None
    assert "contacts" not in own_customer
    assert client.get(f"/api/suppliers/{supplier.code}").status_code == 403
    customer_order = client.get(
        f"/api/orders/{sales.order_number}"
    ).get_json()["order"]
    assert customer_order["customer"] == customer.name
    assert "supplier" not in customer_order
    assert customer_order["total"] is None
    assert customer_order["lines"][0]["unit_price"] is None

    _login(client, supplier_portal)
    own_supplier = client.get(
        f"/api/suppliers/{supplier.code}"
    ).get_json()["supplier"]
    assert own_supplier["rating"] is None
    assert own_supplier["payment_terms"] is None
    assert "contacts" not in own_supplier
    assert client.get(f"/api/customers/{customer.code}").status_code == 403
    supplier_order = client.get(
        f"/api/orders/{purchase.order_number}"
    ).get_json()["order"]
    assert supplier_order["supplier"] == supplier.name
    assert "customer" not in supplier_order
    assert supplier_order["total"] is None
    assert supplier_order["lines"][0]["unit_price"] is None
    search_items = client.get(
        f"/api/suppliers/{supplier.code}/parts"
    ).get_json()["items"]
    assert len(search_items) == 1
    assert set(search_items[0]) == {
        "part_number",
        "revision",
        "description",
    }


def test_portal_field_config_excludes_custom_sources_and_review_config(
    client,
    app,
):
    with app.app_context():
        save_field_config(
            {
                "custom_fields": [
                    {
                        "id": "internal_code",
                        "label": "Internal Code",
                        "source_path": "attrs.internal_code",
                    }
                ],
                "contexts": {
                    "parts_list": {
                        "allowed_field_ids": [
                            "part_number",
                            "description",
                            "internal_code",
                        ],
                        "default_field_ids": [
                            "part_number",
                            "internal_code",
                        ],
                    }
                },
                "canonical_aliases": [
                    {
                        "field_id": "material",
                        "aliases": ["private_material_alias"],
                    }
                ],
            }
        )
    portal = _user(
        "config-portal@example.test",
        _standard_role("customer"),
    )
    Customer(code="CONFIG-C", name="Config Customer", users=[portal]).save()
    _login(client, portal)
    response = client.get("/api/field-config")
    assert response.status_code == 200
    config = response.get_json()["config"]
    assert "internal_code" not in {
        field["id"] for field in config["fields"]
    }
    assert config["canonical_aliases"] == []
    assert config["approval_rules"] == {}
    assert all(
        "source_path" not in field
        for field in config["fields"]
    )


def test_embedded_comment_profiles_redact_email_roles_and_permissions(client):
    reviewer = _user(
        "quality-route@example.test",
        _standard_role("engineering_manager"),
    )
    part = _released("REVIEW-FIELD")
    PartAnnotation(
        part_number=part.part_number,
        revision=part.revision,
        comments=[
            {
                "id": "review-comment",
                "author": reviewer.email,
                "text": "Review this",
                "status": "open",
            }
        ],
    ).save()
    _login(client, reviewer)
    detail = client.get(
        f"/api/part_detail?pn={part.part_number}&rev={part.revision}"
    ).get_json()
    comment = detail["comments"][0]
    assert comment["author_display"] == "User"
    assert "author" not in comment
    assert "email" not in comment["author_profile"]
    assert "roles" not in comment["author_profile"]
    assert "permissions" not in comment["author_profile"]


@pytest.mark.parametrize(
    ("method", "url", "payload", "model", "lookup", "field"),
    [
        (
            "put",
            "/api/customers/MUT-C",
            {"description": "changed", "users": ["forbidden"]},
            Customer,
            {"code": "MUT-C"},
            "description",
        ),
        (
            "put",
            "/api/suppliers/MUT-S",
            {"description": "changed", "storage_path": "C:/private"},
            Supplier,
            {"code": "MUT-S"},
            "description",
        ),
        (
            "put",
            "/api/jobs/MUT-J",
            {"description": "changed", "is_deleted": True},
            Job,
            {"job_number": "MUT-J"},
            "description",
        ),
        (
            "put",
            "/api/orders/MUT-O",
            {"description": "changed", "approved_by": "client"},
            Order,
            {"order_number": "MUT-O"},
            "description",
        ),
    ],
)
def test_mixed_protected_mutations_reject_without_partial_save(
    client,
    method,
    url,
    payload,
    model,
    lookup,
    field,
):
    customer = Customer(
        code="MUT-C",
        name="Mutation Customer",
        description="original",
    ).save()
    supplier = Supplier(
        code="MUT-S",
        name="Mutation Supplier",
        description="original",
    ).save()
    Job(job_number="MUT-J", description="original").save()
    Order(order_number="MUT-O", description="original").save()
    role = _role(
        f"mutation-{model.__name__}",
        [
            "customers.read",
            "customers.update",
            "suppliers.read",
            "suppliers.update",
            "jobs.read",
            "jobs.update",
            "orders.read",
            "orders.update",
            "parts.read",
        ],
    )
    user = _user(f"{model.__name__}@mutation.test", role)
    _login(client, user)

    response = getattr(client, method)(url, json=payload)
    assert response.status_code == 400
    document = model.objects(**lookup).first()
    assert getattr(document, field) == "original"
    assert customer is not None and supplier is not None


def test_nested_unknown_customer_contact_rejects_before_save(client):
    customer = Customer(code="NEST-C", name="Nested Customer").save()
    user = _user(
        "nested-write@example.test",
        _role(
            "nested-write",
            ["customers.read", "customers.update"],
        ),
    )
    _login(client, user)
    response = client.put(
        f"/api/customers/{customer.code}",
        json={
            "description": "changed",
            "contacts": [
                {
                    "name": "Contact",
                    "email": "contact@example.test",
                    "role_ids": ["forbidden"],
                }
            ],
        },
    )
    assert response.status_code == 400
    customer.reload()
    assert not customer.description
    assert customer.contacts == []

import uuid

import pytest

from app.models.api_token import ApiToken
from app.models.audit import AuditLog
from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.customer import Customer
from app.models.job import Job
from app.models.order import Order
from app.models.part import Part
from app.models.supplier import Supplier
from app.services.permissions import (
    CANONICAL_PERMISSION_IDENTIFIERS,
    LEGACY_PERMISSION_IDENTIFIERS,
)
from app.services.rls_demo import (
    PERMISSION_TEST_ROLE_SCENARIOS,
    reset_permission_test_environment,
    seed_permission_test_environment,
)
from app.services.standard_roles import STANDARD_ROLES, reconcile_standard_roles
from app.views import admin_roles


REQUIRED_TEST_SETUP_PERMISSIONS = (
    "security.roles.manage",
    "security.users.manage",
    "security.assignments.manage",
    "system.maintenance",
)


def _role(name, permissions=(), **values):
    return Role(name=name, permissions=list(permissions), **values).save()


def _user(email, roles=(), *, active=True):
    return User(
        email=email,
        password="test",
        active=active,
        fs_uniquifier=str(uuid.uuid4()),
        roles=list(roles),
    ).save()


def _login(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = user.get_id()
        session["_fresh"] = True


def _access_actor(*permissions):
    role = _role(
        f"access_manager_{uuid.uuid4().hex}",
        permissions or (
            "security.users.read",
            "security.users.manage",
            "security.roles.read",
            "security.roles.manage",
            "security.assignments.manage",
        ),
    )
    return _user(f"access-{uuid.uuid4().hex}@example.com", [role])


def test_admin_permission_editor_uses_complete_registry_and_separates_legacy(
    client,
    app,
):
    with app.app_context():
        actor = _access_actor("security.roles.manage")
    _login(client, actor)

    response = client.get("/admin/roles/new")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert len(CANONICAL_PERMISSION_IDENTIFIERS) == 72
    for permission in CANONICAL_PERMISSION_IDENTIFIERS:
        assert (
            f'value="{permission}" data-permission-kind="canonical"' in body
        )
    assert "Legacy compatibility permissions" in body
    assert "New roles should normally use canonical permissions." in body
    for permission in LEGACY_PERMISSION_IDENTIFIERS:
        assert f'value="{permission}" data-permission-kind="legacy"' in body
    assert "data-permission-action=\"read\"" in body
    assert not hasattr(admin_roles, "PERMISSIONS")
    assert "endsWith(\".read\")" in client.get(
        "/static/admin-access.js"
    ).get_data(as_text=True)


def test_admin_role_form_preserves_standard_slug_and_validates_custom_permissions(
    client,
    app,
):
    with app.app_context():
        actor = _access_actor("security.roles.manage")
        reconcile_standard_roles()
        standard = Role.objects.get(name="commercial")
    _login(client, actor)

    renamed = client.post(
        f"/admin/roles/{standard.id}/edit",
        data={
            "name": "renamed_commercial",
            "display_name": standard.display_name,
            "description": standard.description,
            "permissions": list(standard.permissions),
        },
    )
    assert renamed.status_code == 302
    standard.reload()
    assert standard.name == "commercial"
    assert Role.objects(name="renamed_commercial").first() is None

    created = client.post(
        "/admin/roles/new",
        data={
            "name": "document_reader",
            "display_name": "Document Reader",
            "description": "Reads released engineering records.",
            "permissions": ["parts.read", "bom.read", "files.read"],
        },
    )
    assert created.status_code == 302
    assert Role.objects.get(name="document_reader").permissions == [
        "parts.read",
        "bom.read",
        "files.read",
    ]

    invalid = client.post(
        "/admin/roles/new",
        data={
            "name": "invalid_role",
            "permissions": ["parts.read", "permission.does_not_exist"],
        },
    )
    assert invalid.status_code == 400
    assert Role.objects(name="invalid_role").first() is None


def test_custom_role_delete_blocks_assignments_and_protects_catalogue_roles(
    client,
    app,
):
    with app.app_context():
        actor = _access_actor(
            "security.roles.read",
            "security.roles.manage",
            "security.users.read",
        )
        assigned_role = _role(
            "assigned_custom_role",
            ["parts.read"],
            display_name="Assigned Custom Role",
        )
        assigned_user = _user("role-assignment@example.com", [assigned_role])
        empty_role = _role(
            "empty_custom_role",
            ["parts.read"],
            display_name="Empty Custom Role",
        )
        reconcile_standard_roles()
        standard = Role.objects.get(name="commercial")
        legacy_admin = _role("admin")
    _login(client, actor)

    edit = client.get(f"/admin/roles/{assigned_role.id}/edit")
    assert edit.status_code == 200
    body = edit.get_data(as_text=True)
    assert "Review 1 assigned user" in body
    assert "will not create dangling role references" in body

    blocked = client.post(f"/admin/roles/{assigned_role.id}/delete")
    assert blocked.status_code == 409
    assert "Role not deleted" in blocked.get_data(as_text=True)
    assigned_user.reload()
    assert [role.name for role in assigned_user.roles] == ["assigned_custom_role"]
    assert Role.objects(id=assigned_role.id).count() == 1
    assert AuditLog.objects(
        action="admin.role.delete_blocked",
        resource="assigned_custom_role",
    ).count() == 1

    deleted = client.post(f"/admin/roles/{empty_role.id}/delete")
    assert deleted.status_code == 302
    assert Role.objects(id=empty_role.id).count() == 0
    assert AuditLog.objects(
        action="admin.role.delete",
        resource="empty_custom_role",
    ).count() == 1

    assert client.post(f"/admin/roles/{standard.id}/delete").status_code == 403
    assert client.post(f"/admin/roles/{legacy_admin.id}/delete").status_code == 403
    assert Role.objects(id=standard.id).count() == 1
    assert Role.objects(id=legacy_admin.id).count() == 1


def test_custom_role_delete_requires_role_management_permission(client, app):
    with app.app_context():
        reader = _access_actor("security.roles.read")
        role = _role("protected_custom_role", ["parts.read"])
    _login(client, reader)

    assert client.post(f"/admin/roles/{role.id}/delete").status_code == 403
    assert Role.objects(id=role.id).count() == 1


def test_admin_role_list_reports_status_counts_and_reconciliation_is_safe(
    client,
    app,
):
    with app.app_context():
        actor = _access_actor(
            "security.roles.read",
            "security.roles.manage",
        )
        reconcile_standard_roles()
        commercial = Role.objects.get(name="commercial")
        assigned = _user("assigned@example.com", [commercial])
        original_role_ids = [str(role.id) for role in assigned.roles]
        Role.objects(id=commercial.id).update(
            set__display_name="Drifted Commercial",
        )
        custom = _role(
            "custom_reader",
            ["parts.read"],
            display_name="Custom Reader",
            description="A focused custom role.",
        )
        _user("custom-assigned@example.com", [custom])
        Role._get_collection().insert_one(
            {
                "name": "invalid_stored_role",
                "display_name": "Invalid Stored Role",
                "permissions": ["parts.read", "unknown.permission"],
            }
        )
        Role.objects(name="auditor").delete()
    _login(client, actor)

    response = client.get("/admin/roles/?q=commercial&filter=drifted")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Drifted Commercial" in body
    assert "Customised/drifted" in body
    assert "New custom role" in client.get("/admin/roles/").get_data(as_text=True)
    all_roles = client.get("/admin/roles/").get_data(as_text=True)
    assert "Custom Reader" in all_roles
    assert "Invalid permissions" in all_roles
    assert "Missing" in all_roles
    assert ">1</td>" in all_roles

    first_seed = client.post("/admin/roles/standard-roles/seed")
    second_seed = client.post("/admin/roles/standard-roles/seed")
    assert first_seed.status_code == second_seed.status_code == 302
    assert Role.objects(name="auditor").count() == 1
    commercial.reload()
    assert commercial.display_name == "Drifted Commercial"
    assigned.reload()
    assert [str(role.id) for role in assigned.roles] == original_role_ids

    restored = client.post("/admin/roles/standard-roles/restore")
    assert restored.status_code == 302
    commercial.reload()
    assigned.reload()
    assert commercial.display_name == STANDARD_ROLES["commercial"].display_name
    assert [str(role.id) for role in assigned.roles] == original_role_ids


def test_admin_users_search_filters_pagination_and_role_cards(client, app):
    with app.app_context():
        actor = _access_actor()
        role = _role(
            "service_desk",
            ["customers.read"],
            display_name="Service Desk",
            description="Supports customer enquiries.",
        )
        for index in range(55):
            _user(
                f"person{index:02d}@example.com",
                [role] if index % 2 == 0 else [],
                active=index % 3 != 0,
            )
    _login(client, actor)

    first_page = client.get("/admin/users")
    assert first_page.status_code == 200
    body = first_page.get_data(as_text=True)
    assert "Page 1 of 2" in body
    assert "Service Desk" in body
    assert "Supports customer enquiries." not in body
    assert "Last login" in body

    second_page = client.get("/admin/users?page=2")
    assert second_page.status_code == 200
    assert "Page 2 of 2" in second_page.get_data(as_text=True)

    searched = client.get("/admin/users?q=person54")
    assert "person54@example.com" in searched.get_data(as_text=True)
    assert "person53@example.com" not in searched.get_data(as_text=True)

    inactive = client.get("/admin/users?active=inactive")
    assert "person00@example.com" in inactive.get_data(as_text=True)
    role_filtered = client.get("/admin/users?role=service_desk")
    assert "person00@example.com" in role_filtered.get_data(as_text=True)
    assert "person01@example.com" not in role_filtered.get_data(as_text=True)

    create_form = client.get("/admin/users/new").get_data(as_text=True)
    assert "Service Desk" in create_form
    assert "Supports customer enquiries." in create_form
    assert "data-role-permissions" in create_form
    assert "Active account" in create_form


def test_admin_user_activation_safeguards_self_and_last_legacy_admin(
    client,
    app,
):
    with app.app_context():
        actor = _access_actor("security.users.manage")
        legacy_admin_role = _role("admin")
        last_admin = _user("last-admin@example.com", [legacy_admin_role])
        regular = _user("regular@example.com")
    _login(client, actor)

    response = client.post(
        "/admin/users/bulk-status",
        data={
            "action": "deactivate",
            "user_ids": [str(actor.id), str(last_admin.id), str(regular.id)],
        },
    )
    assert response.status_code == 302
    actor.reload()
    last_admin.reload()
    regular.reload()
    assert actor.active is True
    assert last_admin.active is True
    assert regular.active is False
    assert AuditLog.objects(
        action="admin.user.deactivate",
        resource="regular@example.com",
    ).count() == 1

    activated = client.post(
        "/admin/users/bulk-status",
        data={"action": "activate", "user_ids": [str(regular.id)]},
    )
    assert activated.status_code == 302
    regular.reload()
    assert regular.active is True
    assert AuditLog.objects(
        action="admin.user.activate",
        resource="regular@example.com",
    ).count() == 1


def test_permission_test_setup_is_hidden_and_denied_by_default(client, app):
    app.config["ALLOW_PERMISSION_TEST_DATA"] = False
    with app.app_context():
        actor = _access_actor(
            "security.roles.read",
            *REQUIRED_TEST_SETUP_PERMISSIONS,
        )
    _login(client, actor)

    body = client.get("/admin/roles/").get_data(as_text=True)
    assert "Permission test setup" in body
    assert "Create permission test environment</button>" not in body
    assert client.post("/admin/roles/permission-test/seed").status_code == 403
    assert client.post("/admin/roles/permission-test/reset").status_code == 403


@pytest.mark.parametrize("missing", REQUIRED_TEST_SETUP_PERMISSIONS)
def test_permission_test_setup_requires_every_permission(client, app, missing):
    with app.app_context():
        actor = _access_actor(
            *(permission for permission in REQUIRED_TEST_SETUP_PERMISSIONS if permission != missing)
        )
    app.config["ALLOW_PERMISSION_TEST_DATA"] = True
    _login(client, actor)

    assert client.post("/admin/roles/permission-test/seed").status_code == 403
    assert client.post("/admin/roles/permission-test/reset").status_code == 403


def test_permission_test_seed_uses_only_curated_canonical_matrix(client, app, tmp_path):
    app.instance_path = str(tmp_path)
    app.config["ALLOW_PERMISSION_TEST_DATA"] = True
    app.config["PERMISSION_TEST_DATA_DOMAIN"] = "test.example.com"
    with app.app_context():
        actor = _access_actor(
            "security.roles.read",
            *REQUIRED_TEST_SETUP_PERMISSIONS,
        )
    _login(client, actor)

    seeded = client.post("/admin/roles/permission-test/seed")

    assert seeded.status_code == 200
    assert seeded.headers["Cache-Control"] == "no-store"
    body = seeded.get_data(as_text=True)
    assert "Copy all" in body
    assert "Credentials are shown only in this immediate response" in body
    assert "permtest.security_administrator@test.example.com" in body
    with app.app_context():
        test_users = list(
            User.objects(email__regex=r"^permtest\..+@test\.example\.com$")
        )
        assert len(test_users) == len(PERMISSION_TEST_ROLE_SCENARIOS)
        assert {
            user.email.split("@", 1)[0].removeprefix("permtest.")
            for user in test_users
        } == set(PERMISSION_TEST_ROLE_SCENARIOS)
        assert {
            role.name
            for user in test_users
            for role in (user.roles or [])
        } <= set(STANDARD_ROLES)
        assert not Role.objects(
            name__in=["viewer", "operator", "customer_viewer", "supplier_viewer"]
        )
        assert ApiToken.objects(user_id__in=[user.id for user in test_users]).count() == 0
        production = User.objects.get(
            email="permtest.workshop@test.example.com"
        )
        assert Job.objects(
            job_number="DEMO-JOB-A1",
            participants=production,
        ).count() == 1
        customer_portal = User.objects.get(
            email="permtest.customer@test.example.com"
        )
        supplier_portal = User.objects.get(
            email="permtest.supplier@test.example.com"
        )
        assert Customer.objects(code="DEMO-CUST-A", users=customer_portal).count() == 1
        assert Supplier.objects(code="DEMO-SUP-X", users=supplier_portal).count() == 1
        assert Customer.objects(code__startswith="DEMO-CUST-").count() == 3
        assert Supplier.objects(code__startswith="DEMO-SUP-").count() == 3
        assert Part.objects(part_number="DEMO-ASM-1", revision="A").count() == 1
        assert Part.objects(part_number="DEMO-ASM-1", revision="B").count() == 1
        assert BOMLink.objects(parent_pn="DEMO-ASM-1").count() > 0
    assert not list(tmp_path.iterdir())
    refreshed = client.get("/admin/roles/").get_data(as_text=True)
    assert "permtest.security_administrator@test.example.com" not in refreshed
    assert "Credentials are shown only in this immediate response" not in refreshed


def test_permission_test_seed_is_idempotent_and_reset_is_namespace_limited(
    app,
    tmp_path,
):
    app.instance_path = str(tmp_path)
    with app.app_context():
        real_user = _user("real.person@example.com")
        real_customer = Customer(code="REAL-CUST", name="Real Customer").save()
        real_supplier = Supplier(code="REAL-SUP", name="Real Supplier").save()
        real_job = Job(job_number="REAL-JOB").save()
        real_order = Order(order_number="REAL-ORDER").save()
        real_part = Part(part_number="REAL-PART", revision="A").save()

        first = seed_permission_test_environment("seed.example.com")
        first_emails = {row["email"] for row in first["users"]}
        first_passwords = {row["password"] for row in first["users"]}
        second = seed_permission_test_environment("seed.example.com")
        assert first["counts"]["users_created"] == len(PERMISSION_TEST_ROLE_SCENARIOS)
        assert second["counts"]["users_created"] == 0
        assert second["counts"]["users_updated"] == len(PERMISSION_TEST_ROLE_SCENARIOS)
        assert {row["email"] for row in second["users"]} == first_emails
        assert {row["password"] for row in second["users"]}.isdisjoint(
            first_passwords
        )
        for key in ("customers", "suppliers", "jobs", "orders", "parts", "bom_links"):
            assert second["counts"][key] == 0

        test_user = User.objects(email__in=list(first_emails)).first()
        ApiToken(
            user_id=test_user,
            token_hash=f"hash-{uuid.uuid4().hex}",
            label="old test token",
        ).save()
        removed = reset_permission_test_environment("seed.example.com")
        assert removed["users"] == len(PERMISSION_TEST_ROLE_SCENARIOS)
        assert removed["tokens"] == 1
        assert User.objects(email__regex=r"^permtest\.").count() == 0
        assert Customer.objects(code__startswith="DEMO-").count() == 0
        assert Supplier.objects(code__startswith="DEMO-").count() == 0
        assert Job.objects(job_number__startswith="DEMO-").count() == 0
        assert Order.objects(order_number__startswith="DEMO-").count() == 0
        assert Part.objects(part_number__startswith="DEMO-").count() == 0
        assert BOMLink.objects(
            __raw__={
                "$or": [
                    {"parent_pn": {"$regex": "^DEMO-"}},
                    {"child_pn": {"$regex": "^DEMO-"}},
                ]
            }
        ).count() == 0
        assert User.objects(id=real_user.id).count() == 1
        assert Customer.objects(id=real_customer.id).count() == 1
        assert Supplier.objects(id=real_supplier.id).count() == 1
        assert Job.objects(id=real_job.id).count() == 1
        assert Order.objects(id=real_order.id).count() == 1
        assert Part.objects(id=real_part.id).count() == 1
        assert set(Role.objects.distinct("name")) >= set(STANDARD_ROLES)
    assert not list(tmp_path.iterdir())

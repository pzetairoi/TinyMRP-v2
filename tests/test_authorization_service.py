from types import SimpleNamespace
import uuid

import pytest

from app.models.audit import AuditLog
from app.models.auth import Role, User
from app.models.customer import Customer
from app.models.job import Job, JobBOMLine
from app.models.order import Order
from app.models.part import Part
from app.models.supplier import Supplier
from app.services import authorization
from app.services.authorization import (
    AuthorizationScopeError,
    authorise,
    authorised_get,
    authorise_part_access,
    check_transaction_conflict,
    effective_permissions,
    filter_response_fields,
    has_all_permissions,
    has_any_permission,
    has_permission,
    scope_queryset,
)
from app.services.acl import permissions_required


class FakeUser:
    is_authenticated = True

    def __init__(self, roles):
        self.roles = roles


class AnonymousUser:
    is_authenticated = False
    roles = ()


def _role(name, permissions=()):
    return Role(name=name, permissions=list(permissions)).save()


def _user(email, roles=()):
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


def test_effective_permissions_no_roles_and_unauthenticated():
    assert effective_permissions(FakeUser([])) == frozenset()
    assert effective_permissions(AnonymousUser()) == frozenset()
    assert not has_permission(AnonymousUser(), "parts.read")


def test_effective_permissions_union_duplicates_and_immutable_result():
    first = SimpleNamespace(
        name="first",
        permissions=["parts.read", "jobs.read", "parts.read"],
    )
    second = SimpleNamespace(name="second", permissions=["orders.read", "jobs.read"])
    user = FakeUser([first, second])

    permissions = effective_permissions(user)

    assert permissions == frozenset({"parts.read", "jobs.read", "orders.read"})
    assert isinstance(permissions, frozenset)
    assert has_all_permissions(user, ["parts.read", "orders.read"])
    assert has_any_permission(user, ["customers.read", "jobs.read"])


def test_legacy_expansion_is_non_mutating_and_can_be_disabled():
    stored = ["items.view"]
    user = FakeUser([SimpleNamespace(name="legacy", permissions=stored)])

    expanded = effective_permissions(user)

    assert "items.view" in expanded
    assert "parts.read" in expanded
    assert effective_permissions(user, include_legacy=False) == frozenset({"items.view"})
    assert has_permission(user, "parts.read")
    assert not has_permission(user, "parts.read", include_legacy=False)
    assert stored == ["items.view"]


def test_unknown_and_malformed_role_data_never_grants_authority():
    valid_plus_unknown = SimpleNamespace(
        name="custom",
        permissions=["parts.read", "unknown.permission"],
    )
    malformed = SimpleNamespace(name="broken", permissions="orders.read")
    inactive = SimpleNamespace(name="inactive", permissions=["orders.read"], active=False)
    user = FakeUser([None, valid_plus_unknown, malformed, inactive])

    assert effective_permissions(user) == frozenset({"parts.read"})
    assert not has_permission(user, "unknown.permission")
    assert not has_permission(user, "orders.read")


def test_permission_calculation_exception_denies(monkeypatch):
    user = FakeUser([])

    monkeypatch.setattr(
        authorization,
        "_build_permission_snapshot",
        lambda _user: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert effective_permissions(user) == frozenset()
    assert not has_permission(user, "parts.read")


def test_request_cache_traverses_roles_once(app):
    class CountingUser:
        is_authenticated = True

        def __init__(self):
            self.reads = 0
            self._roles = [SimpleNamespace(name="reader", permissions=["parts.read"])]

        @property
        def roles(self):
            self.reads += 1
            return self._roles

    user = CountingUser()
    with app.test_request_context("/cache"):
        assert effective_permissions(user) == frozenset({"parts.read"})
        assert effective_permissions(user) == frozenset({"parts.read"})
        assert has_permission(user, "parts.read")
    assert user.reads == 1


@pytest.mark.parametrize(
    "role_name",
    [
        "planner",
        "operator",
        "manager",
        "security_administrator",
        "system_administrator",
        "break_glass_administrator",
    ],
)
def test_ordinary_role_names_do_not_bypass_permissions(app, role_name):
    with app.app_context():
        user = FakeUser([SimpleNamespace(name=role_name, permissions=[])])
        assert not has_permission(user, "parts.read")
        assert not authorise(user, "jobs.read").allowed


def test_legacy_admin_bypass_is_exact_and_configurable(app):
    admin = FakeUser([SimpleNamespace(name="admin", permissions=[])])
    admin_like = FakeUser([SimpleNamespace(name="admin_helper", permissions=[])])
    portal_admin_like = FakeUser(
        [
            SimpleNamespace(name="customer_portal", permissions=[]),
            SimpleNamespace(name="administrator", permissions=[]),
        ]
    )

    with app.app_context():
        app.config["LEGACY_ADMIN_BYPASS_ENABLED"] = True
        decision = authorise(admin, "parts.read")
        assert decision.allowed
        assert decision.used_legacy_admin_bypass
        assert not has_permission(admin_like, "parts.read")
        assert not has_permission(portal_admin_like, "parts.read")
        assert not has_permission(admin, "unknown.permission")

        app.config["LEGACY_ADMIN_BYPASS_ENABLED"] = False
        assert not has_permission(admin, "parts.read")


def test_malformed_admin_role_object_does_not_activate_bypass(app):
    malformed_admin = FakeUser(
        [SimpleNamespace(name="admin", permissions="not-a-permission-list")]
    )

    with app.app_context():
        app.config["LEGACY_ADMIN_BYPASS_ENABLED"] = True
        assert not has_permission(malformed_admin, "parts.read")


def test_canonical_and_missing_permission_decisions():
    user = FakeUser([SimpleNamespace(name="reader", permissions=["parts.read"])])

    allowed = authorise(user, "parts.read")
    denied = authorise(user, "orders.read")
    invalid = authorise(user, "not.registered")

    assert allowed.allowed and allowed.reason_code == "allowed"
    assert not allowed.used_legacy_expansion
    assert not denied.allowed and denied.reason_code == "missing_permission"
    assert not invalid.allowed and invalid.reason_code == "invalid_permission"


def test_legacy_decision_records_expansion():
    user = FakeUser([SimpleNamespace(name="legacy", permissions=["items.view"])])

    decision = authorise(user, "parts.read")

    assert decision.allowed
    assert decision.used_legacy_expansion
    assert not decision.used_legacy_admin_bypass


def test_customer_scope_and_authoritative_lookup_cannot_cross_organisation(app):
    with app.app_context():
        role = _role("customer_portal", ["customers.read", "jobs.read"])
        user = _user("customer-scope@example.com", [role])
        own = Customer(name="Own Customer", users=[user]).save()
        other = Customer(name="Other Customer").save()
        own_job = Job(job_number="OWN-JOB", customer=own).save()
        Job(job_number="OTHER-JOB", customer=other).save()

        customers = list(scope_queryset(Customer.objects, user, "customers"))
        jobs = list(scope_queryset(Job.objects, user, "jobs"))

        assert [customer.name for customer in customers] == ["Own Customer"]
        assert [job.job_number for job in jobs] == ["OWN-JOB"]
        assert (
            authorised_get(
                Job.objects,
                user,
                own_job.id,
                resource_type="jobs",
            )
            == own_job
        )
        assert (
            authorised_get(
                Job.objects,
                user,
                "not-an-object-id",
                resource_type="jobs",
            )
            is None
        )
        other_job = Job.objects.get(job_number="OTHER-JOB")
        assert (
            authorised_get(
                Job.objects,
                user,
                other_job.id,
                resource_type="jobs",
            )
            is None
        )


def test_supplier_and_participant_scopes(app):
    with app.app_context():
        supplier_role = _role("supplier_portal", ["suppliers.read", "orders.read"])
        supplier_user = _user("supplier-scope@example.com", [supplier_role])
        own_supplier = Supplier(name="Own Supplier", users=[supplier_user]).save()
        other_supplier = Supplier(name="Other Supplier").save()
        Order(order_number="OWN-ORDER", supplier=own_supplier).save()
        Order(order_number="OTHER-ORDER", supplier=other_supplier).save()

        assert [item.name for item in scope_queryset(
            Supplier.objects, supplier_user, "suppliers"
        )] == ["Own Supplier"]
        assert [item.order_number for item in scope_queryset(
            Order.objects, supplier_user, "orders"
        )] == ["OWN-ORDER"]

        production_role = _role("production_operator", ["jobs.read"])
        production_user = _user("production-scope@example.com", [production_role])
        assigned = Job(job_number="ASSIGNED", participants=[production_user]).save()
        Job(job_number="UNASSIGNED").save()

        assert [item.job_number for item in scope_queryset(
            Job.objects, production_user, "jobs"
        )] == [assigned.job_number]


def test_external_role_with_no_relationship_scope_is_deny_all(app):
    with app.app_context():
        role = _role("customer_portal", ["jobs.read"])
        user = _user("unlinked-portal@example.com", [role])
        Job(job_number="HIDDEN").save()

        assert list(scope_queryset(Job.objects, user, "jobs")) == []


def test_scope_exception_is_deny_all(app, monkeypatch):
    with app.app_context():
        role = _role("reader", ["jobs.read"])
        user = _user("scope-error@example.com", [role])
        Job(job_number="HIDDEN-ERROR").save()
        monkeypatch.setattr(
            authorization,
            "_build_scope_context",
            lambda _user: (_ for _ in ()).throw(RuntimeError("scope failed")),
        )

        assert list(scope_queryset(Job.objects, user, "jobs")) == []


def test_unsupported_resource_type_never_returns_unrestricted(app):
    with app.app_context():
        role = _role("reader", ["jobs.read"])
        user = _user("unsupported@example.com", [role])

        with pytest.raises(AuthorizationScopeError):
            scope_queryset(Job.objects, user, "unsupported")
        with pytest.raises(AuthorizationScopeError):
            authorised_get(
                Job.objects,
                user,
                "anything",
                resource_type="unsupported",
            )


def test_planner_permission_contribution_remains_global_despite_relationship(app):
    with app.app_context():
        role = _role("planner", ["jobs.read"])
        user = _user("scoped-planner@example.com", [role])
        own_customer = Customer(name="Planner Customer", users=[user]).save()
        other_customer = Customer(name="Other Planner Customer").save()
        Job(job_number="PLANNER-OWN", customer=own_customer).save()
        Job(job_number="PLANNER-OTHER", customer=other_customer).save()

        assert [item.job_number for item in scope_queryset(
            Job.objects, user, "jobs"
        )] == ["PLANNER-OWN", "PLANNER-OTHER"]


def test_part_access_uses_exact_revision_and_case_normalisation(app):
    with app.app_context():
        role = _role("customer_portal", ["parts.read"])
        user = _user("part-scope@example.com", [role])
        customer = Customer(name="Part Customer", users=[user]).save()
        Part(
            part_number="PART-1",
            revision="A",
            description="Allowed",
            attrs={"approvedby": "QA Person"},
        ).save()
        Part(
            part_number="PART-1",
            revision="B",
            description="Wrong revision",
            attrs={"approvedby": "QA Person"},
        ).save()
        Job(
            job_number="PART-JOB",
            customer=customer,
            bom=[JobBOMLine(pn="PART-1", rev="A", qty=1)],
        ).save()

        assert authorise_part_access(user, "part-1", "a").allowed
        wrong = authorise_part_access(user, "PART-1", "B")
        assert not wrong.allowed
        assert wrong.reason_code == "resource_out_of_scope"
        missing = authorise_part_access(user, "MISSING", "A")
        assert not missing.allowed


def test_blank_revision_is_exact_not_family_wildcard(app, monkeypatch):
    with app.app_context():
        role = _role("customer_portal", ["parts.read"])
        user = _user("blank-rev@example.com", [role])
        customer = Customer(name="Blank Rev Customer", users=[user]).save()
        Part(
            part_number="BLANK-1",
            revision="",
            description="Blank",
            attrs={"approvedby": "QA Person"},
        ).save()
        Part(
            part_number="BLANK-1",
            revision="A",
            description="A",
            attrs={"approvedby": "QA Person"},
        ).save()
        Job(
            job_number="BLANK-JOB",
            customer=customer,
            bom=[JobBOMLine(pn="BLANK-1", rev="", qty=1)],
        ).save()
        monkeypatch.setattr(
            "app.services.acl.allowed_parts_for",
            lambda _user: {("BLANK-1", "")},
        )

        assert authorise_part_access(user, "BLANK-1", "").allowed
        assert not authorise_part_access(user, "BLANK-1", "A").allowed
        assert authorise_part_access(
            user,
            "BLANK-1",
            "",
            allow_part_family=True,
        ).allowed


def test_part_acl_calculation_exception_denies(app, monkeypatch):
    with app.app_context():
        role = _role("customer_portal", ["parts.read"])
        user = _user("part-error@example.com", [role])
        Customer(name="Error Customer", users=[user]).save()
        Part(part_number="ERROR-1", revision="A").save()
        monkeypatch.setattr(
            "app.services.acl.allowed_parts_for",
            lambda _user: (_ for _ in ()).throw(RuntimeError("ACL failed")),
        )

        assert not authorise_part_access(user, "ERROR-1", "A").allowed


def test_field_filtering_copies_and_removes_external_properties(app):
    with app.app_context():
        role = _role("customer_portal", ["parts.read"])
        user = _user("field-external@example.com", [role])
        Customer(name="Field Customer", users=[user]).save()
        payload = {
            "part_number": "PART-1",
            "revision": "A",
            "description": "Part",
            "internal_cost": 99,
            "nested": {"secret": True},
        }
        original_nested = payload["nested"]

        filtered = filter_response_fields("parts", user, payload)

        assert filtered == {
            "part_number": "PART-1",
            "revision": "A",
            "description": "Part",
        }
        assert payload["internal_cost"] == 99
        assert payload["nested"] is original_nested


def test_field_filtering_unsupported_external_policy_fails_safely(app):
    with app.app_context():
        role = _role("customer_portal", ["parts.read"])
        user = _user("field-unsupported@example.com", [role])

        assert filter_response_fields(
            "unsupported",
            user,
            {"secret": "hidden"},
        ) == {}


def test_field_filtering_internal_policy_is_an_explicit_allowlist(app):
    with app.app_context():
        role = _role("engineering_data_steward", ["parts.read"])
        user = _user("field-internal@example.com", [role])
        payload = {"part_number": "PART-2", "internal_cost": 15}

        filtered = filter_response_fields("parts", user, payload)

        assert filtered == {"part_number": "PART-2"}
        assert filtered is not payload


def test_transaction_conflict_hook_decisions(monkeypatch):
    user = FakeUser([])

    no_conflict = check_transaction_conflict(user, "order_self_approval")
    assert no_conflict.allowed
    assert no_conflict.reason_code == "no_conflict"

    monkeypatch.setitem(
        authorization._TRANSACTION_CONFLICT_RULES,
        "order_self_approval",
        lambda _user, _resource, _context: "order_self_approval",
    )
    conflict = check_transaction_conflict(user, "order_self_approval")
    assert not conflict.allowed
    assert conflict.conflict_code == "order_self_approval"
    assert conflict.reason_code == "transaction_conflict"


def test_transaction_conflict_exception_and_unknown_action_deny(monkeypatch):
    user = FakeUser([])
    monkeypatch.setitem(
        authorization._TRANSACTION_CONFLICT_RULES,
        "design_self_approval",
        lambda _user, _resource, _context: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    error = check_transaction_conflict(user, "design_self_approval")
    unknown = check_transaction_conflict(user, "unregistered_sensitive_action")

    assert not error.allowed and error.conflict_code == "conflict_check_error"
    assert not unknown.allowed and unknown.conflict_code == "unknown_transaction_action"


def test_authorise_applies_registered_conflict(monkeypatch):
    user = FakeUser([SimpleNamespace(name="approver", permissions=["orders.approve"])])
    monkeypatch.setitem(
        authorization._TRANSACTION_CONFLICT_RULES,
        "order_self_approval",
        lambda _user, _resource, _context: "order_self_approval",
    )

    decision = authorise(
        user,
        "orders.approve",
        context={"conflict_action": "order_self_approval", "resource_id": "ORDER-1"},
    )

    assert not decision.allowed
    assert decision.reason_code == "transaction_conflict"
    assert decision.conflict_code == "order_self_approval"


def test_denial_audit_is_structured_and_deduplicated(app):
    user = FakeUser([SimpleNamespace(name="reader", permissions=[])])
    with app.test_request_context("/stage2-denial", method="POST"):
        first = authorise(user, "parts.read")
        second = authorise(user, "parts.read")

    assert not first.allowed and not second.allowed
    logs = list(AuditLog.objects(action="authorization.denied"))
    assert len(logs) == 1
    assert logs[0].extra["permission"] == "parts.read"
    assert logs[0].extra["reason_code"] == "missing_permission"
    assert logs[0].extra["method"] == "POST"
    assert "password" not in logs[0].extra


def test_permissions_required_preserves_http_and_all_required_semantics(client, app):
    @app.get("/_stage2/all")
    @permissions_required("parts.read", "bom.read")
    def stage2_all():
        return {"ok": True}

    assert client.get("/_stage2/all").status_code == 401

    with app.app_context():
        one_role = _role("one-permission", ["parts.read"])
        user = _user("one-permission@example.com", [one_role])
    _login(client, user)
    assert client.get("/_stage2/all").status_code == 403

    with app.app_context():
        both_role = _role("both-permissions", ["parts.read", "bom.read"])
        user.roles = [both_role]
        user.save()
    assert client.get("/_stage2/all").status_code == 200


def test_permissions_required_uses_central_admin_setting(client, app):
    @app.get("/_stage2/admin")
    @permissions_required("parts.read")
    def stage2_admin():
        return {"ok": True}

    with app.app_context():
        admin_role = _role("admin")
        admin_user = _user("legacy-admin@example.com", [admin_role])
    _login(client, admin_user)

    app.config["LEGACY_ADMIN_BYPASS_ENABLED"] = True
    assert client.get("/_stage2/admin").status_code == 200
    app.config["LEGACY_ADMIN_BYPASS_ENABLED"] = False
    assert client.get("/_stage2/admin").status_code == 403

import uuid

from app.models.auth import Role, User
from app.models.bom import BOMLink
from app.models.customer import Customer
from app.models.job import Job, JobBOMLine
from app.models.numbering import NumberingCounter, NumberingScheme
from app.models.order import Order, OrderLine
from app.models.part import Part
from app.models.supplier import Supplier
from app.services.authorization import (
    authorise_part_access,
    has_permission,
    scope_queryset,
)
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


def _released(part_number, revision, description="Released"):
    return Part(
        part_number=part_number,
        revision=revision,
        description=description,
        attrs={"approvedby": "QA Person"},
    ).save()


def _draft(part_number, revision, description="Draft"):
    return Part(
        part_number=part_number,
        revision=revision,
        description=description,
    ).save()


def _scheme(name="Stage3B1"):
    return NumberingScheme(
        name=name,
        pattern_segments=[
            {"kind": "literal", "value": "SEC"},
            {"kind": "seq", "padding": 3, "base": 10},
        ],
        separator="-",
        scope_mode="global",
        seq={"padding": 3, "base": 10, "start_at": 1, "reset_policy": "never"},
        revision={"policy": "alpha", "start": "A"},
        validation_rules={
            "max_length": 32,
            "allowed_charset": "A-Z0-9-",
            "require_seq_segment": True,
        },
    ).save()


def test_released_visibility_and_read_only_permissions(client):
    viewer = _user("viewer@stage3b1.test", _standard_role("internal_viewer"))
    released = _released("VIS-100", "A")
    draft = _draft("VIS-200", "A")
    _login(client, viewer)

    response = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {}},
    )
    assert response.status_code == 200
    assert {row["part_number"] for row in response.get_json()["data"]} == {
        released.part_number
    }
    assert client.get(
        f"/api/part_detail?pn={draft.part_number}&rev={draft.revision}"
    ).status_code == 404
    assert not has_permission(viewer, "parts.create")
    assert not has_permission(viewer, "parts.update")
    assert not has_permission(viewer, "bom.update")
    assert not has_permission(viewer, "numbering.allocate")
    assert not has_permission(viewer, "parts.archive")
    assert not has_permission(viewer, "parts.restore")


def test_engineering_reads_unreleased_revises_and_does_not_inherit_approval(client):
    engineer = _user(
        "engineer@stage3b1.test",
        _standard_role("engineering_data_steward"),
    )
    source = _released("REV-100", "A")
    source.docs = ["released/drawing.pdf"]
    source.attrs["released_by"] = "QA Person"
    source.save()
    _login(client, engineer)

    assert {
        (part.part_number, part.revision)
        for part in scope_queryset(Part.objects, engineer, "parts")
    } == {("REV-100", "A")}
    response = client.post(
        f"/api/numbering/parts/{source.part_number}/revise",
        json={"change_note": "Design update"},
    )
    assert response.status_code == 200
    revised = Part.objects.get(part_number="REV-100", revision="B")
    assert revised.docs == []
    assert not revised.canonical.get("approved")
    assert not revised.attrs.get("approved_by")
    assert not revised.attrs.get("approvedby")
    assert not revised.attrs.get("released_by")
    assert not has_permission(engineer, "parts.release.approve")
    assert not has_permission(engineer, "parts.purge")
    assert has_permission(engineer, "parts.archive")
    assert has_permission(engineer, "parts.restore")
    assert has_permission(engineer, "bom.update")


def test_quality_and_auditor_have_unreleased_read_without_design_write():
    draft = _draft("QA-100", "A")
    for role_name in ("quality_reviewer", "auditor"):
        user = _user(
            f"{role_name}@stage3b1.test",
            _standard_role(role_name),
        )
        assert authorise_part_access(user, draft.part_number, draft.revision).allowed
        assert not has_permission(user, "parts.update")
        assert not has_permission(user, "bom.update")
        assert not has_permission(user, "numbering.allocate")
        assert not has_permission(user, "parts.purge")
        assert not has_permission(user, "files.replace")

    quality = User.objects.get(email="quality_reviewer@stage3b1.test")
    assert has_permission(quality, "parts.release.approve")
    # Stage 6 will add the creator/approver transaction-conflict check.


def test_portal_and_production_scopes_are_exact_and_released_only(client):
    part_a = _released("SCOPE-100", "A")
    part_b = _released("SCOPE-100", "B")
    draft = _draft("SCOPE-200", "A")

    customer_user = _user(
        "customer@stage3b1.test",
        _standard_role("customer_portal"),
    )
    customer = Customer(name="Scoped Customer", users=[customer_user]).save()
    Job(
        job_number="CUSTOMER-PARTS",
        customer=customer,
        bom=[
            JobBOMLine(pn=part_a.part_number, rev=part_a.revision, qty=1),
            JobBOMLine(pn=draft.part_number, rev=draft.revision, qty=1),
        ],
    ).save()
    assert authorise_part_access(
        customer_user,
        part_a.part_number,
        part_a.revision,
    ).allowed
    assert not authorise_part_access(
        customer_user,
        part_b.part_number,
        part_b.revision,
    ).allowed
    assert not authorise_part_access(
        customer_user,
        draft.part_number,
        draft.revision,
    ).allowed
    _login(client, customer_user)
    assert client.get("/api/part_detail?pn=SCOPE-100&rev=B").status_code == 404
    latest_allowed = client.get("/api/part_detail?pn=SCOPE-100")
    assert latest_allowed.status_code == 200
    assert latest_allowed.get_json()["part"]["revision"] == "A"
    assert latest_allowed.get_json()["other_versions"] == []
    listing = client.post(
        "/api/parts_lazy",
        json={"first": 0, "rows": 25, "filters": {}},
    ).get_json()
    assert listing["totalRecords"] == 1

    operator = _user(
        "operator@stage3b1.test",
        _standard_role("production_operator"),
    )
    Job(
        job_number="PRODUCTION-PARTS",
        participants=[operator],
        bom=[JobBOMLine(pn=part_a.part_number, rev=part_a.revision, qty=1)],
    ).save()
    assert authorise_part_access(operator, "SCOPE-100", "A").allowed
    assert not authorise_part_access(operator, "SCOPE-100", "B").allowed
    assert not has_permission(operator, "parts.update")
    assert not has_permission(operator, "bom.update")


def test_supplier_portal_scope_is_exact():
    part_a = _released("SUP-100", "A")
    _released("SUP-100", "B")
    supplier_user = _user(
        "supplier@stage3b1.test",
        _standard_role("supplier_portal"),
    )
    supplier = Supplier(name="Scoped Supplier", users=[supplier_user]).save()
    Order(
        order_number="PO-SUP-SCOPE",
        supplier=supplier,
        lines=[OrderLine(pn=part_a.part_number, rev=part_a.revision, qty=1)],
    ).save()

    assert authorise_part_access(supplier_user, "SUP-100", "A").allowed
    assert not authorise_part_access(supplier_user, "SUP-100", "B").allowed
    assert not has_permission(supplier_user, "parts.update")
    assert not has_permission(supplier_user, "bom.update")


def test_bom_reads_deny_inaccessible_descendants_and_scope_where_used(client):
    parent = _released("BOM-100", "A")
    child = _draft("BOM-200", "A")
    unrelated_parent = _released("BOM-300", "A")
    BOMLink(
        parent_pn=parent.part_number,
        parent_rev=parent.revision,
        child_pn=child.part_number,
        child_rev=child.revision,
        qty=1,
    ).save()
    BOMLink(
        parent_pn=unrelated_parent.part_number,
        parent_rev=unrelated_parent.revision,
        child_pn=parent.part_number,
        child_rev=parent.revision,
        qty=2,
    ).save()

    portal = _user("bom-portal@stage3b1.test", _standard_role("customer_portal"))
    customer = Customer(name="BOM Customer", users=[portal]).save()
    Job(
        job_number="BOM-SCOPE",
        customer=customer,
        bom=[JobBOMLine(pn=parent.part_number, rev=parent.revision, qty=1)],
    ).save()
    _login(client, portal)

    assert client.get(
        f"/api/bom_tree?pn={parent.part_number}&rev={parent.revision}"
    ).status_code == 403
    assert client.get(
        f"/api/bom_flat?pn={parent.part_number}&rev={parent.revision}"
    ).status_code == 403
    where_used = client.post(
        "/api/whereused_lazy",
        json={
            "pn": parent.part_number,
            "rev": parent.revision,
            "first": 0,
            "rows": 25,
        },
    )
    assert where_used.status_code == 200
    assert where_used.get_json()["totalRecords"] == 0


def test_authorised_bom_read_keeps_exact_child_revision(client):
    parent = _draft("BOM-EXACT-P", "A")
    _draft("BOM-EXACT-C", "A")
    child_b = _draft("BOM-EXACT-C", "B")
    BOMLink(
        parent_pn=parent.part_number,
        parent_rev=parent.revision,
        child_pn=child_b.part_number,
        child_rev=child_b.revision,
        qty=2,
    ).save()
    engineer = _user(
        "bom-engineer@stage3b1.test",
        _standard_role("engineering_data_steward"),
    )
    _login(client, engineer)

    children = client.get(
        f"/api/bom_tree?parent={parent.part_number}&parent_rev={parent.revision}"
    )
    assert children.status_code == 200
    assert {
        (row["data"]["part_number"], row["data"]["revision"])
        for row in children.get_json()
    } == {(child_b.part_number, "B")}
    flat = client.get(
        f"/api/bom_flat?pn={parent.part_number}&rev={parent.revision}"
    )
    assert flat.status_code == 200
    assert {
        (row["part_number"], row["revision"]) for row in flat.get_json()
    } == {(child_b.part_number, "B")}


def test_numbering_permissions_preview_side_effects_and_manager_shortcut(client):
    scheme = _scheme()
    manager = _user("manager@stage3b1.test", _role("manager", []))
    _login(client, manager)
    before = NumberingCounter.objects.count()
    assert client.get("/api/numbering/schemes").status_code == 403
    assert client.post(
        "/api/numbering/preview",
        json={"scheme_id": str(scheme.id), "context": {}},
    ).status_code == 403
    assert NumberingCounter.objects.count() == before

    planner = _user("planner@stage3b1.test", _standard_role("planner"))
    _login(client, planner)
    preview = client.post(
        "/api/numbering/preview",
        json={"scheme_id": str(scheme.id), "context": {}},
    )
    assert preview.status_code == 200
    assert NumberingCounter.objects.count() == before
    assert client.post(
        "/api/numbering/allocate",
        json={
            "scheme_id": str(scheme.id),
            "context": {},
            "create_part_if_missing": True,
            "requested_revision_action": "new_part",
        },
    ).status_code == 403
    allocation = client.post(
        "/api/numbering/allocate",
        json={
            "scheme_id": str(scheme.id),
            "context": {},
            "create_part_if_missing": False,
            "requested_revision_action": "new_part",
        },
    )
    assert allocation.status_code == 200
    assert not has_permission(planner, "parts.update")
    assert not has_permission(planner, "parts.purge")


def test_purge_requires_canonical_or_exact_legacy_admin(client, app):
    for role_name in ("engineering_data_steward", "planner", "quality_reviewer"):
        part = _released(f"PURGE-{role_name}", "A")
        user = _user(f"{role_name}-purge@stage3b1.test", _standard_role(role_name))
        _login(client, user)
        assert client.post(
            "/api/part_delete",
            json={"pn": part.part_number, "rev": part.revision},
        ).status_code == 403

    legacy_admin = _user("legacy-admin@stage3b1.test", _role("admin", []))
    legacy_part = _released("PURGE-ADMIN", "A")
    _login(client, legacy_admin)
    app.config["LEGACY_ADMIN_BYPASS_ENABLED"] = True
    assert client.post(
        "/api/part_delete",
        json={"pn": legacy_part.part_number, "rev": legacy_part.revision},
    ).status_code == 200

    disabled_part = _released("PURGE-DISABLED", "A")
    app.config["LEGACY_ADMIN_BYPASS_ENABLED"] = False
    assert client.post(
        "/api/part_delete",
        json={"pn": disabled_part.part_number, "rev": disabled_part.revision},
    ).status_code == 403

    purge_user = _user(
        "canonical-purge@stage3b1.test",
        _role("canonical_purge", ["parts.purge"]),
    )
    _login(client, purge_user)
    assert client.post(
        "/api/part_delete",
        json={"pn": disabled_part.part_number, "rev": disabled_part.revision},
    ).status_code == 200


def test_non_part_administrators_do_not_gain_part_or_numbering_authority():
    for role_name in ("security_administrator", "system_administrator"):
        user = _user(f"{role_name}@stage3b1.test", _standard_role(role_name))
        for permission in (
            "parts.read",
            "bom.read",
            "numbering.allocate",
            "numbering.manage",
            "parts.purge",
        ):
            assert not has_permission(user, permission)


def test_multiple_roles_combine_only_contributing_part_scopes():
    released = _released("MULTI-100", "A")
    draft = _draft("MULTI-200", "A")
    portal = _standard_role("customer_portal")
    internal = _standard_role("internal_viewer")
    user = _user("multi@stage3b1.test", portal, internal)
    Customer(name="Multi Customer", users=[user]).save()

    assert authorise_part_access(user, released.part_number, released.revision).allowed

    security_portal = _user(
        "security-portal@stage3b1.test",
        _standard_role("security_administrator"),
        _standard_role("customer_portal"),
    )
    Customer(name="Security Portal Customer", users=[security_portal]).save()
    assert not authorise_part_access(
        security_portal,
        released.part_number,
        released.revision,
    ).allowed

    engineer_quality = _user(
        "engineer-quality@stage3b1.test",
        _standard_role("engineering_data_steward"),
        _standard_role("quality_reviewer"),
    )
    assert authorise_part_access(
        engineer_quality,
        draft.part_number,
        draft.revision,
    ).allowed
    assert has_permission(engineer_quality, "parts.update")
    assert has_permission(engineer_quality, "parts.release.approve")
    # Deliberately allowed until the Stage 6 self-approval conflict is activated.

    planner_operator = _user(
        "planner-operator@stage3b1.test",
        _standard_role("planner"),
        _standard_role("production_operator"),
    )
    assert authorise_part_access(
        planner_operator,
        released.part_number,
        released.revision,
    ).allowed
    assert not authorise_part_access(
        planner_operator,
        draft.part_number,
        draft.revision,
    ).allowed

    custom_role = _role(
        "custom_internal_parts",
        ["parts.read", "parts.read_unreleased"],
    )
    linked_internal = _user("linked-internal@stage3b1.test", custom_role)
    Customer(name="Linked Internal Customer", users=[linked_internal]).save()
    assert authorise_part_access(
        linked_internal,
        draft.part_number,
        draft.revision,
    ).allowed

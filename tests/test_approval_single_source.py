"""Approval is resolved once on write and read from one field everywhere.

Aliases and blank-ish values are interpreted by the import/save resolver only.
Every read surface -- inventory rows, part detail, filters and portal scope --
must agree with ``Part.canonical.approved`` for every role, so the badge can
never disagree with the filters.
"""

from __future__ import annotations

import pytest

from app.models.auth import Role, User
from app.models.part import Part
from app.services.attrs import approval_filter_raw, normalize_record_attrs
from app.services.authorization import part_is_released
from app.services.part_materialized import sync_part_materialized_fields


def _part(pn: str, rev: str, attrs: dict) -> Part:
    part = Part(part_number=pn, revision=rev, attrs=normalize_record_attrs(attrs))
    sync_part_materialized_fields(part)
    return part.save()


def _user(email: str, permissions: list[str]) -> User:
    role = Role(name=f"role_{email.split('@')[0]}", permissions=permissions).save()
    return User(
        email=email, password="x", active=True, roles=[role], fs_uniquifier=email
    ).save()


@pytest.mark.parametrize(
    "attrs,expected",
    [
        ({"approved_by": "Jane Approver"}, True),
        ({"approved": "yes"}, True),
        ({"approved": True}, True),
        ({"released": "Y"}, True),
        ({}, False),
        ({"approved": ""}, False),
        ({"approved": "no"}, False),
        ({"approved": "pending"}, False),
        # A placeholder is not an approver identity.
        ({"approved_by": "approved by"}, False),
    ],
)
def test_import_resolves_aliases_into_one_boolean(app, attrs, expected):
    with app.app_context():
        part = _part("RES-1", "A", attrs)

        assert bool((part.canonical or {}).get("approved")) is expected
        # The same answer every reader gets.
        assert part_is_released(part) is expected


def test_the_stored_boolean_is_what_queries_match(app):
    with app.app_context():
        approved = _part("Q-APPROVED", "A", {"approved_by": "Jane Approver"})
        draft = _part("Q-DRAFT", "A", {"approved": "pending"})
        blank = _part("Q-BLANK", "A", {})

        matched = {
            p.part_number for p in Part.objects(__raw__=approval_filter_raw(approved=True))
        }
        unmatched = {
            p.part_number for p in Part.objects(__raw__=approval_filter_raw(approved=False))
        }

        assert matched == {approved.part_number}
        assert unmatched == {draft.part_number, blank.part_number}
        # Every part falls on exactly one side; nothing is invisible to both.
        assert matched | unmatched == {p.part_number for p in Part.objects}


def test_a_part_never_written_by_the_resolver_is_not_approved(app):
    """Fail closed: an absent boolean must not read as approved.

    ``Part.save()`` always syncs the boolean, so this state only arises for
    documents written before the field existed. Such a row must read as
    unapproved rather than inheriting approval from its raw attrs.
    """

    with app.app_context():
        Part._get_collection().insert_one(
            {"part_number": "LEGACY-1", "revision": "A", "attrs": {"approved": "yes"}}
        )
        stale = Part.objects(part_number="LEGACY-1").first()

        assert "approved" not in (stale.canonical or {})
        assert part_is_released(stale) is False
        assert Part.objects(__raw__=approval_filter_raw(approved=True)).count() == 0
        assert Part.objects(__raw__=approval_filter_raw(approved=False)).count() == 1


def test_every_reading_role_sees_the_same_approval_state(app, client):
    """The badge must not depend on review or audit permissions."""

    with app.app_context():
        _part("ROLE-1", "A", {"approved_by": "Jane Approver"})
        users = {
            "reviewer": _user("rev@example.com", ["parts.read", "reviews.approve"]),
            "plain_reader": _user("plain@example.com", ["parts.read"]),
            "workshop": _user("shop@example.com", ["parts.read", "bom.read"]),
        }
        uniquifiers = {name: str(u.fs_uniquifier) for name, u in users.items()}

    seen = {}
    for name, uniquifier in uniquifiers.items():
        with client.session_transaction() as session:
            session["_user_id"] = uniquifier
            session["_fresh"] = True
        response = client.get("/api/part_detail?pn=ROLE-1&rev=A")
        assert response.status_code == 200, name
        seen[name] = (response.get_json().get("part") or {}).get("approved")

    assert seen == {"reviewer": True, "plain_reader": True, "workshop": True}


def test_unreleased_scope_follows_the_same_boolean(app, client):
    """Readers without parts.read_unreleased only see approved parts."""

    with app.app_context():
        _part("SCOPE-YES", "A", {"approved_by": "Jane Approver"})
        _part("SCOPE-NO", "A", {"approved": "pending"})
        user = _user("scoped@example.com", ["parts.read"])
        uniquifier = str(user.fs_uniquifier)

    with client.session_transaction() as session:
        session["_user_id"] = uniquifier
        session["_fresh"] = True

    rows = client.post("/api/parts_lazy", json={"first": 0, "rows": 50}).get_json()["data"]

    assert {row["part_number"] for row in rows} == {"SCOPE-YES"}
    assert client.get("/api/part_detail?pn=SCOPE-NO&rev=A").status_code == 404


def test_inventory_rows_carry_the_same_boolean_as_detail(app, client):
    with app.app_context():
        _part("LIST-YES", "A", {"approved_by": "Jane Approver"})
        _part("LIST-NO", "A", {"approved": "pending"})
        # parts.read alone is scoped to approved parts, so an unreleased row
        # would never reach the list to be compared.
        user = _user("lister@example.com", ["parts.read", "parts.read_unreleased"])
        uniquifier = str(user.fs_uniquifier)

    with client.session_transaction() as session:
        session["_user_id"] = uniquifier
        session["_fresh"] = True

    rows = client.post("/api/parts_lazy", json={"first": 0, "rows": 50}).get_json()["data"]
    by_pn = {row["part_number"]: row.get("approved") for row in rows}

    assert by_pn == {"LIST-YES": True, "LIST-NO": False}
    for pn, expected in by_pn.items():
        detail = client.get(f"/api/part_detail?pn={pn}&rev=A").get_json()
        assert (detail.get("part") or {}).get("approved") is expected

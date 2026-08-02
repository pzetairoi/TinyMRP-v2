"""Process is resolved once on write and queried from one indexed field.

Aliases (process2, secondprocess, ...) are collapsed by the import/save
resolver into ``Part.processes``. Every read surface and every filter uses that
canonical list, so the inventory filter, the BOM and the docpack icons can
never disagree.
"""

from __future__ import annotations

import pytest

from app.models.auth import Role, User
from app.models.part import Part
from app.services.attrs import normalize_record_attrs
from app.services.canonical_fields import (
    canonical_process_label_for_part,
    canonical_processes_for_part,
)
from app.services.field_config import get_field_config, primary_query_path


def _part(pn: str, attrs: dict, **kwargs) -> Part:
    return Part(
        part_number=pn, revision="A", attrs=normalize_record_attrs(attrs), **kwargs
    ).save()


def _reader(email: str) -> str:
    # parts.read alone is scoped to approved parts; these fixtures are drafts,
    # so the reader also needs the unreleased scope to see them at all.
    role = Role(
        name=f"r_{email.split('@')[0]}",
        permissions=["parts.read", "parts.read_unreleased"],
    ).save()
    user = User(
        email=email, password="x", active=True, roles=[role], fs_uniquifier=email
    ).save()
    return str(user.fs_uniquifier)


@pytest.mark.parametrize(
    "attrs,expected",
    [
        ({"process": "lasercut"}, ["lasercut"]),
        # Aliases collapse into the one ordered list.
        ({"process": "lasercut", "process2": "machine"}, ["lasercut", "machine"]),
        ({"process": "lasercut", "secondprocess": "machine"}, ["lasercut", "machine"]),
        ({"processes": ["welding", "paint"]}, ["welding", "paint"]),
        ({}, []),
        ({"process": ""}, []),
    ],
)
def test_import_collapses_process_aliases_into_one_list(app, attrs, expected):
    with app.app_context():
        part = _part("PROC-1", attrs)

        assert list(part.processes) == expected
        # Every reader returns that same list.
        assert canonical_processes_for_part(part) == expected
        assert canonical_process_label_for_part(part) == ", ".join(expected)


def test_the_process_filter_queries_the_indexed_field(app):
    with app.app_context():
        assert primary_query_path("process", get_field_config()) == "processes"


def test_process_filter_matches_any_process_of_a_part(app, client):
    with app.app_context():
        _part("MULTI-1", {"process": "lasercut", "process2": "machine"})
        _part("SINGLE-1", {"process": "machine"})
        _part("OTHER-1", {"process": "welding"})
        _part("NONE-1", {})
        uniquifier = _reader("proc@example.com")

    with client.session_transaction() as session:
        session["_user_id"] = uniquifier
        session["_fresh"] = True

    def search(value, mode="contains"):
        body = {"first": 0, "rows": 50, "filters": {"process": {"value": value, "matchMode": mode}}}
        rows = client.post("/api/parts_lazy", json=body).get_json()["data"]
        return {row["part_number"] for row in rows}

    # A part is matched by any process it carries, not only the first.
    assert search("machine") == {"MULTI-1", "SINGLE-1"}
    assert search("lasercut") == {"MULTI-1"}
    assert search("welding") == {"OTHER-1"}
    # Case-insensitive, and a multi-select matches any of the chosen values.
    assert search("MACHINE") == {"MULTI-1", "SINGLE-1"}
    assert search(["lasercut", "welding"], "in") == {"MULTI-1", "OTHER-1"}


def test_process_empty_filters_account_for_every_part(app, client):
    with app.app_context():
        _part("HAS-1", {"process": "machine"})
        _part("EMPTY-1", {})
        uniquifier = _reader("procempty@example.com")

    with client.session_transaction() as session:
        session["_user_id"] = uniquifier
        session["_fresh"] = True

    def search(mode):
        body = {"first": 0, "rows": 50, "filters": {"process": {"value": "", "matchMode": mode}}}
        rows = client.post("/api/parts_lazy", json=body).get_json()["data"]
        return {row["part_number"] for row in rows}

    # An empty list must count as empty, not as "has a value".
    assert search("isEmpty") == {"EMPTY-1"}
    assert search("isNotEmpty") == {"HAS-1"}


def test_negated_text_filters_do_not_error(app, client):
    """notEquals/notContains are offered in the UI, so they must not 500."""

    with app.app_context():
        _part("NEG-1", {"process": "machine"})
        _part("NEG-2", {"process": "welding"})
        uniquifier = _reader("procneg@example.com")

    with client.session_transaction() as session:
        session["_user_id"] = uniquifier
        session["_fresh"] = True

    for mode in ("notEquals", "notContains"):
        body = {"first": 0, "rows": 50, "filters": {"process": {"value": "machine", "matchMode": mode}}}
        response = client.post("/api/parts_lazy", json=body)

        assert response.status_code == 200, mode
        assert {row["part_number"] for row in response.get_json()["data"]} == {"NEG-2"}


def test_hardware_grouping_reads_the_canonical_list(app):
    """Docpack icons and BOM ordering key off the same list."""

    from app.views.bom_tree import _is_hardware_node

    with app.app_context():
        part = _part("HW-1", {"process": "hardware"})

        assert "hardware" in part.processes
        label = canonical_process_label_for_part(part)
        assert _is_hardware_node({"data": {"process": label}}) is True
        # A process merely containing the word is not hardware.
        assert _is_hardware_node({"data": {"process": "hardware coating"}}) is False

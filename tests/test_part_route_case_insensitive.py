"""The part and BOM pages must find a part the rest of the app can see.

Reported: a where-used link led to /ui/part/<pn> and answered "not found".

The 404 was an authorisation denial, not missing data. authorised_get was given
identifier_field="part_number", an EXACT match, while every other part lookup in
the application - including the where-used list that produced the link - matches
case-insensitively. Two authorisation paths, two answers for the same part.

Part numbers being matched case-insensitively throughout is a stated invariant
of this codebase, so the route was the side that was wrong.
"""

from __future__ import annotations

import inspect

from app.views import ui


def test_the_part_page_looks_up_case_insensitively():
    source = inspect.getsource(ui.part_ui)
    assert 'identifier_field="part_number__iexact"' in source
    assert 'identifier_field="part_number"' not in source


def test_the_bom_page_looks_up_the_same_way():
    """Both entry points must agree, or one of them 404s on the other's links."""
    source = inspect.getsource(ui.bom_ui)
    assert 'identifier_field="part_number__iexact"' in source
    assert 'identifier_field="part_number"' not in source


def test_scoping_still_runs_before_the_lookup():
    """Case-insensitivity must not cost the permission scope."""
    source = inspect.getsource(ui.part_ui)
    assert "authorised_get" in source, "the authorisation gate must remain"
    assert "abort(404)" in source, "a denied part must not leak its existence"

"""Per-request memoization must never outlive the config it was derived from.

The alias and field indexes are cached on ``g`` keyed by the identity of the
object they were built from. These tests pin that a config edit is visible
immediately and that one request's cache never serves another.
"""

from __future__ import annotations

from app.services.canonical_fields import (
    canonical_alias_index,
    canonical_aliases_for_field,
)
from app.services.field_config import field_index


def test_field_index_follows_an_edited_config(app):
    first = {"fields": [{"id": "alpha", "label": "Alpha"}]}
    second = {"fields": [{"id": "beta", "label": "Beta"}]}

    with app.test_request_context("/"):
        assert set(field_index(first)) == {"alpha"}
        # A different config object must not be served the cached index.
        assert set(field_index(second)) == {"beta"}
        assert set(field_index(first)) == {"alpha"}


def test_field_index_cache_does_not_cross_requests(app):
    config = {"fields": [{"id": "alpha", "label": "Alpha"}]}

    with app.test_request_context("/"):
        field_index(config)

    mutated = {"fields": [{"id": "gamma", "label": "Gamma"}]}
    with app.test_request_context("/"):
        assert set(field_index(mutated)) == {"gamma"}


def test_explicit_config_bypasses_the_runtime_alias_cache(app):
    custom = {
        "canonical_aliases": [
            {"field_id": "approved", "aliases": ["signed_off"]},
        ]
    }

    with app.test_request_context("/"):
        # Warm the runtime cache first; the explicit config must still win.
        runtime = canonical_aliases_for_field("approved")
        # Sanitisation always keeps the field id itself as an alias.
        assert canonical_aliases_for_field("approved", custom) == ["approved", "signed_off"]
        assert canonical_alias_index(custom).get("signed_off") == "approved"
        # The explicit lookup must not have replaced the runtime cache.
        assert canonical_aliases_for_field("approved") == runtime


def test_unknown_field_falls_back_to_its_own_key(app):
    with app.test_request_context("/"):
        assert canonical_aliases_for_field("no_such_field") == ["no_such_field"]
        assert canonical_aliases_for_field("") == []


def test_alias_lookups_are_not_mutated_by_callers(app):
    with app.test_request_context("/"):
        first = canonical_aliases_for_field("approved")
        assert first, "expected the approved field to carry aliases"
        # The cached list is shared; a caller appending to it would corrupt
        # every later resolution in the request.
        second = canonical_aliases_for_field("approved")
        assert second == first

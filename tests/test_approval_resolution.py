from app.models.app_settings import AppSettings
from app.models.part import Part
from app.services.attrs import approval_field_values, normalize_record_attrs
from app.services.canonical_fields import extract_canonical_fields, get_runtime_canonical_aliases
from app.services.field_config import save_field_config


def test_approval_status_vocabulary_is_consistent(app):
    with app.app_context():
        assert approval_field_values({"approved": "Approved"}) == {
            "approved": True,
            "approved_by": "",
            "approved_date": "",
        }
        assert approval_field_values({"approved": "Not Approved"})["approved"] is False
        assert approval_field_values({"approved": "no"})["approved"] is False
        assert approval_field_values({"approved": "-"})["approved"] is False
        assert approval_field_values({"approved": "--"})["approved"] is False
        assert approval_field_values({"approvedby": "Approver"}) == {
            "approved": False,
            "approved_by": "",
            "approved_date": "",
        }
        assert approval_field_values({"approvedby": "QA Person"}) == {
            "approved": True,
            "approved_by": "QA Person",
            "approved_date": "",
        }


def test_custom_approval_rules_apply_to_status_and_approver_values(app):
    with app.app_context():
        save_field_config(
            {
                "approval_rules": {
                    "approved_values": ["release complete"],
                    "unapproved_values": ["quality hold"],
                    "identity_placeholders": ["approver", "generic signoff"],
                }
            }
        )

        assert approval_field_values({"approved": "Release Complete"})["approved"] is True
        assert approval_field_values({"approved": "Quality-Hold"})["approved"] is False
        assert approval_field_values({"approvedby": "Generic Signoff"})["approved"] is False
        assert approval_field_values({"approvedby": "Alice Smith"}) == {
            "approved": True,
            "approved_by": "Alice Smith",
            "approved_date": "",
        }


def test_approval_normalization_preserves_source_for_future_rule_changes(app):
    with app.app_context():
        attrs = normalize_record_attrs({"approvedby": "Generic Signoff"})
        assert attrs == {"approved": True, "approved_by": "Generic Signoff"}
        assert approval_field_values(attrs)["approved"] is True

        save_field_config(
            {
                "approval_rules": {
                    "identity_placeholders": ["approver", "generic signoff"],
                }
            }
        )
        assert approval_field_values(attrs)["approved"] is False


def test_generic_identity_overrides_legacy_derived_approved_flag(app):
    with app.app_context():
        save_field_config(
            {
                "approval_rules": {
                    "identity_placeholders": ["approver", "generic signoff"],
                }
            }
        )
        result = approval_field_values({"approved": True, "approved_by": "Generic Signoff"})
        assert result["approved"] is False
        assert result["approved_by"] == ""


def test_custom_approved_by_alias_populates_canonical_and_detail_payload(app):
    with app.app_context():
        save_field_config(
            {
                "canonical_aliases": [
                    {
                        "field_id": "approved_by",
                        "aliases": ["approved_by", "approvedby", "EngineeringApproval"],
                    }
                ]
            }
        )
        attrs = {"EngineeringApproval": "QA Person", "approveddate": "2026-07-13"}
        canonical = extract_canonical_fields(attrs)
        assert canonical["approved"] is True
        assert canonical["approved_by"] == "QA Person"
        assert canonical["approved_date"] == "2026-07-13"
        assert approval_field_values(attrs) == {
            "approved": True,
            "approved_by": "QA Person",
            "approved_date": "2026-07-13",
        }

        part = Part(part_number="APR-CUSTOM", revision="A", attrs=attrs).save()
        part.reload()
        assert part.canonical["approved"] is True
        assert part.canonical["approved_by"] == "QA Person"


def test_custom_approval_status_alias_supports_approved_text(app):
    with app.app_context():
        save_field_config(
            {
                "canonical_aliases": [
                    {
                        "field_id": "approved",
                        "aliases": ["approved", "EngineeringApprovalStatus"],
                    }
                ]
            }
        )
        attrs = {"EngineeringApprovalStatus": "Approved"}
        assert approval_field_values(attrs)["approved"] is True
        assert extract_canonical_fields(attrs)["approved"] is True


def test_alias_cache_refreshes_between_app_contexts(app):
    with app.app_context():
        initial = get_runtime_canonical_aliases()
        assert not any(
            "engineeringapproval" in (entry.get("aliases") or [])
            for entry in initial
            if entry.get("field_id") == "approved_by"
        )

    with app.app_context():
        save_field_config(
            {
                "canonical_aliases": [
                    {
                        "field_id": "approved_by",
                        "aliases": ["approved_by", "approvedby", "EngineeringApproval"],
                    }
                ]
            }
        )

    # Simulates a later request handled by the same or another worker. It must
    # read the persisted configuration rather than an indefinite app cache.
    with app.app_context():
        refreshed = get_runtime_canonical_aliases()
        assert any(
            "engineeringapproval" in (entry.get("aliases") or [])
            for entry in refreshed
            if entry.get("field_id") == "approved_by"
        )


def test_field_config_save_updates_settings_timestamp(app):
    with app.app_context():
        settings = AppSettings(field_config={}, updated_at=None).save()
        save_field_config({"canonical_aliases": []})
        settings.reload()
        assert settings.updated_at is not None


def test_field_config_save_synchronizes_legacy_duplicate_settings_documents(app):
    with app.app_context():
        first = AppSettings(field_config={}).save()
        second = AppSettings(field_config={}).save()
        save_field_config(
            {
                "canonical_aliases": [
                    {
                        "field_id": "approved_by",
                        "aliases": ["approved_by", "approvedby", "EngineeringApproval"],
                    }
                ]
            }
        )
        first.reload()
        second.reload()
        for settings in (first, second):
            entries = settings.field_config.get("canonical_aliases") or []
            approved_by = next(item for item in entries if item.get("field_id") == "approved_by")
            assert "engineeringapproval" in approved_by.get("aliases", [])

import io
import json
import zipfile

from app.models.part import Part
from app.services.import_zip import import_bom_zip
from app.services.field_config import save_field_config
from app.services.part_annotations import annotation_payload


def _make_zip(flat_rows):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("OVR_FLATBOM.txt", "\n".join(json.dumps(row) for row in flat_rows))
        zf.writestr("OVR_TREEBOM.txt", "ITEM NO.\tPART NUMBER\tRevision\tQTY.\n1\tOVR-ROOT\t\t1\n")
    return buf.getvalue()


def test_import_preserve_mode_keeps_existing_values(app):
    Part(
        part_number="OVR-100",
        revision="",
        description="Existing Description",
        attrs={"material": "Steel", "notes": "Keep this note"},
    ).save()

    zip_bytes = _make_zip(
        [
            {
                "partnumber": "OVR-100",
                "revision": "",
                "description": "Incoming Description",
                "material": "Aluminium",
                "notes": "Incoming note",
            }
        ]
    )

    with app.app_context():
        import_bom_zip(
            zip_bytes,
            "override.zip",
            seed_tag="test",
            scan_artifacts=False,
            generate_thumbs=False,
            override_mode="preserve",
        )

    part = Part.objects(part_number="OVR-100", revision="").first()
    assert part is not None
    assert part.description == "Existing Description"
    assert part.attrs.get("material") == "Steel"
    assert part.attrs.get("notes") == "Keep this note"


def test_import_override_modes_upgrade_approved_and_preserve_notes(app):
    Part(
        part_number="OVR-200",
        revision="",
        description="Draft Description",
        attrs={"material": "Steel", "notes": "Operator note", "comments": [{"text": "Keep me"}]},
    ).save()

    zip_bytes = _make_zip(
        [
            {
                "partnumber": "OVR-200",
                "revision": "",
                "description": "Released Description",
                "material": "Stainless",
                "approvedby": "QA",
                "approveddate": "2026-01-15",
            }
        ]
    )

    with app.app_context():
        import_bom_zip(
            zip_bytes,
            "approved-only.zip",
            seed_tag="test",
            scan_artifacts=False,
            generate_thumbs=False,
            override_mode="approved_only",
        )

    part = Part.objects(part_number="OVR-200", revision="").first()
    assert part is not None
    assert part.description == "Released Description"
    assert part.attrs.get("material") == "Stainless"
    assert part.attrs.get("approved_by") == "QA"
    assert part.attrs.get("approved_date") == "2026-01-15"
    assert part.attrs.get("approvedby") is None
    assert part.attrs.get("approved") is True
    payload = annotation_payload(part)
    assert payload.get("notes") == "Operator note"
    assert [row.get("text") for row in (payload.get("comments") or [])] == ["Keep me"]


def test_import_default_mode_overrides_unapproved_parts(app):
    Part(
        part_number="OVR-300",
        revision="",
        description="Old Description",
        attrs={"material": "Steel"},
    ).save()

    zip_bytes = _make_zip(
        [
            {
                "partnumber": "OVR-300",
                "revision": "",
                "description": "New Description",
                "material": "Aluminium",
            }
        ]
    )

    with app.app_context():
        report = import_bom_zip(
            zip_bytes,
            "default-mode.zip",
            seed_tag="test",
            scan_artifacts=False,
            generate_thumbs=False,
        )

    part = Part.objects(part_number="OVR-300", revision="").first()
    assert part is not None
    assert report["override_mode"] == "unless_existing_approved"
    assert part.description == "New Description"
    assert part.attrs.get("material") == "Aluminium"


def test_import_default_mode_preserves_existing_approved_parts(app):
    Part(
        part_number="OVR-301",
        revision="",
        description="Approved Description",
        attrs={"material": "Titanium", "approvedby": "QA"},
    ).save()

    zip_bytes = _make_zip(
        [
            {
                "partnumber": "OVR-301",
                "revision": "",
                "description": "Incoming Description",
                "material": "Plastic",
            }
        ]
    )

    with app.app_context():
        import_bom_zip(
            zip_bytes,
            "default-approved.zip",
            seed_tag="test",
            scan_artifacts=False,
            generate_thumbs=False,
        )

    part = Part.objects(part_number="OVR-301", revision="").first()
    assert part is not None
    assert part.description == "Approved Description"
    assert part.attrs.get("material") == "Titanium"
    assert part.attrs.get("approved_by") == "QA"


def test_import_modes_honor_custom_approval_aliases(app):
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
        Part(
            part_number="OVR-CUSTOM-EXISTING",
            revision="",
            description="Released Description",
            attrs={"material": "Titanium", "EngineeringApproval": "QA Person"},
        ).save()

        import_bom_zip(
            _make_zip(
                [
                    {
                        "partnumber": "OVR-CUSTOM-EXISTING",
                        "revision": "",
                        "description": "Incoming Draft",
                        "material": "Plastic",
                    }
                ]
            ),
            "custom-existing.zip",
            scan_artifacts=False,
            generate_thumbs=False,
        )
        existing = Part.objects(part_number="OVR-CUSTOM-EXISTING", revision="").first()
        assert existing.description == "Released Description"
        assert existing.attrs.get("material") == "Titanium"

        Part(
            part_number="OVR-CUSTOM-INCOMING",
            revision="",
            description="Draft Description",
            attrs={"material": "Steel"},
        ).save()
        import_bom_zip(
            _make_zip(
                [
                    {
                        "partnumber": "OVR-CUSTOM-INCOMING",
                        "revision": "",
                        "description": "Released Description",
                        "material": "Stainless",
                        "EngineeringApproval": "QA Person",
                    }
                ]
            ),
            "custom-incoming.zip",
            scan_artifacts=False,
            generate_thumbs=False,
            override_mode="approved_only",
        )
        incoming = Part.objects(part_number="OVR-CUSTOM-INCOMING", revision="").first()
        assert incoming.description == "Released Description"
        assert incoming.attrs.get("material") == "Stainless"
        assert incoming.canonical.get("approved") is True
        assert incoming.canonical.get("approved_by") == "QA Person"


def test_import_reports_conflicting_approval_statuses(app):
    with app.app_context():
        report = import_bom_zip(
            _make_zip(
                [
                    {
                        "partnumber": "OVR-APPROVAL-CONFLICT",
                        "revision": "",
                        "description": "Conflicting Approval",
                        "approved": "Approved",
                        "is_approved": "Not Approved",
                    }
                ]
            ),
            "approval-conflict.zip",
            scan_artifacts=False,
            generate_thumbs=False,
        )
        part = Part.objects(part_number="OVR-APPROVAL-CONFLICT", revision="").first()
        assert part is not None
        assert part.canonical.get("approved") is False
        assert report["approval_integrity_warnings"] == 1
        assert any(issue.get("stage") == "flatbom.approval" for issue in report["warnings"])

"""End-to-end policy semantics for the single upload-pack import pipeline."""

import io
import json
import zipfile

from app.models.bom import BOMLink
from app.models.part import Part
from app.services.field_config import save_field_config
from app.services.part_annotations import annotation_payload
from app.services.upload_pack import import_upload_pack


def _make_zip(flat_rows, tree_lines=None):
    buf = io.BytesIO()
    root = flat_rows[0]
    tree_lines = tree_lines or [
        "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
        f"1\t{root['partnumber']}\t{root.get('revision', '')}\t1",
    ]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("OVR_FLATBOM.txt", "\n".join(json.dumps(row) for row in flat_rows))
        zf.writestr("OVR_TREEBOM.txt", "\n".join(tree_lines))
    return buf.getvalue()


def _apply(zip_bytes, filename="policy.zip", **options):
    return import_upload_pack(
        zip_bytes,
        filename,
        dry_run=False,
        allow_extra=False,
        seed_tag="test",
        generate_thumbs=False,
        **options,
    )


def test_fill_policies_keep_existing_values(app):
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
        _apply(zip_bytes, data_mode="fill_blanks")

    part = Part.objects(part_number="OVR-100", revision="").first()
    assert part is not None
    assert part.description == "Existing Description"
    assert part.attrs.get("material") == "Steel"
    assert part.attrs.get("notes") == "Keep this note"


def test_fill_if_empty_keeps_existing_bom(app):
    Part(part_number="OVR-BOM", revision="A", description="Existing").save()
    Part(part_number="OVR-OLD-CHILD", revision="A").save()
    BOMLink(
        parent_pn="OVR-BOM",
        parent_rev="A",
        child_pn="OVR-OLD-CHILD",
        child_rev="A",
        qty=7,
    ).save()
    zip_bytes = _make_zip(
        [
            {"partnumber": "OVR-BOM", "revision": "A"},
            {"partnumber": "OVR-NEW-CHILD", "revision": "A"},
        ],
        [
            "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
            "1\tOVR-BOM\tA\t1",
            "1.1\tOVR-NEW-CHILD\tA\t2",
        ],
    )

    with app.app_context():
        _apply(zip_bytes, bom_mode="fill_if_empty")

    links = list(BOMLink.objects(parent_pn="OVR-BOM", parent_rev="A"))
    assert [(link.child_pn, link.child_rev, link.qty) for link in links] == [
        ("OVR-OLD-CHILD", "A", 7),
    ]


def test_replace_unapproved_updates_draft_and_normalises_approval_aliases(app):
    Part(
        part_number="OVR-200",
        revision="",
        description="Draft Description",
        attrs={
            "material": "Steel",
            "notes": "Operator note",
            "comments": [{"text": "Keep me"}],
        },
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
        _apply(
            zip_bytes,
            data_mode="replace_unapproved",
            approval_mode="import_unapproved",
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


def test_replace_unapproved_preserves_existing_approved_parts(app):
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
        _apply(zip_bytes, data_mode="replace_unapproved")

    part = Part.objects(part_number="OVR-301", revision="").first()
    assert part is not None
    assert part.description == "Approved Description"
    assert part.attrs.get("material") == "Titanium"
    assert part.attrs.get("approved_by") == "QA"


def test_policies_honor_configured_approval_aliases(app):
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

        _apply(
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
            data_mode="replace_unapproved",
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
        _apply(
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
            data_mode="replace_unapproved",
            approval_mode="import_unapproved",
        )
        incoming = Part.objects(part_number="OVR-CUSTOM-INCOMING", revision="").first()
        assert incoming.description == "Released Description"
        assert incoming.attrs.get("material") == "Stainless"
        assert incoming.canonical.get("approved") is True
        assert incoming.canonical.get("approved_by") == "QA Person"


def test_conflicting_approval_statuses_are_conservative_and_reported(app):
    with app.app_context():
        result = _apply(
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
            approval_mode="replace_all",
        )
        part = Part.objects(part_number="OVR-APPROVAL-CONFLICT", revision="").first()
        assert part is not None
        assert part.canonical.get("approved") is False
        assert result["plan"]["approval_integrity_warnings"] == 1
        entry = result["plan"]["parts"][0]
        assert all(item["action"] == "blocked" for item in entry["approval"])
        assert any(
            issue.get("stage") == "flatbom.approval" for issue in result["warnings"]
        )

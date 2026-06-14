import io
import json
import zipfile

from app.models.part import Part
from app.services.import_zip import import_bom_zip


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
    assert part.attrs.get("approvedby") == "QA"
    assert part.attrs.get("notes") == "Operator note"
    assert part.attrs.get("comments") == [{"text": "Keep me"}]


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
    assert part.attrs.get("approvedby") == "QA"

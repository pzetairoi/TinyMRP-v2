import io
import json
import zipfile

from app.models.bom import BOMLink
from app.models.part import Part
from app.services.import_zip import import_bom_zip


def _make_zip(flat_txt: str, tree_txt: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("TEST_FLATBOM.txt", flat_txt)
        zf.writestr("TEST_TREEBOM.txt", tree_txt)
    return buf.getvalue()


def test_import_bom_zip_best_effort_collects_errors_and_continues(app):
    flat_lines = [
        json.dumps({"partnumber": "ASM-ERR", "revision": "A", "description": "Root"}),
        "{'partnumber': 'P-GOOD', 'revision': '', 'description': 'Good'}",
        "{'PartNumber': 'P-CASE', 'Revision': 'B', 'Description': 'Case Keys'}",
        "['not', 'a', 'dict']",
        "{'partnumber': 'BROKEN'",
    ]
    tree_lines = [
        "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
        "1\tASM-ERR\tA\t1",
        "1.1\t\tA\t2",  # blank part number -> warning + skip
        "1.2\tP-GOOD\t\tnope",  # bad qty -> error + skip
        "1.3\tP-GOOD\t\t3",  # valid -> should still link
    ]
    zip_bytes = _make_zip("\n".join(flat_lines), "\n".join(tree_lines))

    with app.app_context():
        report = import_bom_zip(zip_bytes, "test.zip", seed_tag="test")

        assert report["flat_lines_failed_parse"] == 1
        assert report["flat_lines_skipped_not_dict"] == 1
        assert report["rows_skipped_blank_part"] == 1
        assert report["tree_rows_failed_qty"] == 1

        assert len(report.get("errors") or []) >= 2
        assert len(report.get("warnings") or []) >= 2

        assert Part.objects(part_number="ASM-ERR", revision="A").first() is not None
        assert Part.objects(part_number="P-GOOD", revision="").first() is not None
        assert Part.objects(part_number="P-CASE", revision="B").first() is not None

        link = BOMLink.objects(
            parent_pn="ASM-ERR", parent_rev="A", child_pn="P-GOOD", child_rev=""
        ).first()
        assert link is not None
        assert link.qty == 3


def test_import_bom_zip_modified_parts_report_includes_data_and_bom_changes(app):
    Part(
        part_number="ASM-CHG",
        revision="A",
        description="Original Assembly",
        attrs={"material": "Steel"},
    ).save()
    Part(part_number="LEGACY-1", revision="", description="Legacy child").save()
    BOMLink(parent_pn="ASM-CHG", parent_rev="A", child_pn="LEGACY-1", child_rev="", qty=1).save()

    flat_lines = [
        json.dumps({"partnumber": "ASM-CHG", "revision": "A", "description": "Updated Assembly", "material": "Aluminium"}),
        json.dumps({"partnumber": "NEW-1", "revision": "", "description": "New child"}),
    ]
    tree_lines = [
        "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
        "1\tASM-CHG\tA\t1",
        "1.1\tNEW-1\t\t2",
    ]
    zip_bytes = _make_zip("\n".join(flat_lines), "\n".join(tree_lines))

    with app.app_context():
        report = import_bom_zip(
            zip_bytes,
            "modified-report.zip",
            seed_tag="test",
            scan_artifacts=False,
            generate_thumbs=False,
            override_mode="always",
        )

    modified_parts = report.get("modified_parts") or []
    root_entry = next((item for item in modified_parts if item.get("part_number") == "ASM-CHG" and item.get("revision") == "A"), None)
    assert root_entry is not None
    assert any(change.get("field") == "description" for change in root_entry.get("data_changes") or [])
    assert any(change.get("field") == "material" for change in root_entry.get("data_changes") or [])
    bom_changes = root_entry.get("bom_changes") or {}
    assert any(item.get("part_number") == "NEW-1" for item in bom_changes.get("added") or [])
    assert any(item.get("part_number") == "LEGACY-1" for item in bom_changes.get("removed") or [])


def test_import_bom_zip_artifact_scan_no_longer_queries_removed_props_field(app):
    zip_bytes = _make_zip(
        json.dumps({"partnumber": "SCAN-1", "revision": "A", "description": "Scan target"}),
        "ITEM NO.\tPART NUMBER\tRevision\tQTY.\n1\tSCAN-1\tA\t1",
    )

    with app.app_context():
        report = import_bom_zip(
            zip_bytes,
            "artifact-scan.zip",
            seed_tag="test",
            scan_artifacts=True,
            generate_thumbs=False,
        )

    warning_messages = [str(item.get("exception_message") or item.get("message") or "") for item in (report.get("warnings") or [])]
    assert all('Cannot resolve field "props"' not in message for message in warning_messages)

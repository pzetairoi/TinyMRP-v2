import io
import json
import zipfile

from app.models.bom import BOMLink
from app.models.part import Part
from app.services.upload_pack import import_upload_pack


def _make_zip(flat_txt: str, tree_txt: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("TEST_FLATBOM.txt", flat_txt)
        zf.writestr("TEST_TREEBOM.txt", tree_txt)
    return buf.getvalue()


def _apply(zip_bytes, filename="test.zip"):
    return import_upload_pack(
        zip_bytes,
        filename,
        dry_run=False,
        allow_extra=False,
        seed_tag="test",
        generate_thumbs=False,
        data_mode="replace_unapproved",
        bom_mode="replace_unapproved",
    )


def test_import_best_effort_collects_errors_and_continues(app):
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
        result = _apply(zip_bytes)

        diagnostics = result["diagnostics"]
        assert diagnostics["flat_lines_failed_parse"] == 1
        assert diagnostics["flat_lines_skipped_not_dict"] == 1
        assert diagnostics["rows_skipped_blank_part"] == 1
        assert diagnostics["tree_rows_failed_qty"] == 1

        assert len(result.get("errors") or []) >= 2
        assert len(result.get("warnings") or []) >= 2

        assert Part.objects(part_number="ASM-ERR", revision="A").first() is not None
        assert Part.objects(part_number="P-GOOD", revision="").first() is not None
        assert Part.objects(part_number="P-CASE", revision="B").first() is not None

        link = BOMLink.objects(
            parent_pn="ASM-ERR", parent_rev="A", child_pn="P-GOOD", child_rev=""
        ).first()
        assert link is not None
        assert link.qty == 3


def test_import_redline_includes_data_and_bom_changes(app):
    Part(
        part_number="ASM-CHG",
        revision="A",
        description="Original Assembly",
        attrs={"material": "Steel"},
    ).save()
    Part(part_number="LEGACY-1", revision="", description="Legacy child").save()
    BOMLink(parent_pn="ASM-CHG", parent_rev="A", child_pn="LEGACY-1", child_rev="", qty=1).save()

    flat_lines = [
        json.dumps(
            {
                "partnumber": "ASM-CHG",
                "revision": "A",
                "description": "Updated Assembly",
                "material": "Aluminium",
            }
        ),
        json.dumps({"partnumber": "NEW-1", "revision": "", "description": "New child"}),
    ]
    tree_lines = [
        "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
        "1\tASM-CHG\tA\t1",
        "1.1\tNEW-1\t\t2",
    ]
    zip_bytes = _make_zip("\n".join(flat_lines), "\n".join(tree_lines))

    with app.app_context():
        result = _apply(zip_bytes, "modified-report.zip")

    entry = next(
        (
            item
            for item in result["plan"]["parts"]
            if item["part_number"] == "ASM-CHG" and item["revision"] == "A"
        ),
        None,
    )
    assert entry is not None
    changed_fields = {
        item["field_id"]
        for item in entry["properties"]
        if item["action"] in {"add", "replace"}
    }
    assert {"description", "material"} <= changed_fields
    bom_actions = {
        (item["part_number"], item["action"]) for item in entry["bom"]["changes"]
    }
    assert ("NEW-1", "add") in bom_actions
    assert ("LEGACY-1", "remove") in bom_actions
    assert entry["bom"]["action"] == "replace"

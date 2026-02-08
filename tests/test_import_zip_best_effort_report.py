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


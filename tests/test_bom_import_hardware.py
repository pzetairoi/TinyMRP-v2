# tests/test_bom_import_hardware.py
import io
import zipfile

from app.models.part import Part
from app.services.import_zip import import_bom_zip


def _make_zip(flat_txt: str, tree_txt: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("TEST_FLATBOM.txt", flat_txt)
        zf.writestr("TEST_TREEBOM.txt", tree_txt)
    return buf.getvalue()


def test_import_bom_flags_hardware_from_folder(app):
    flat_rows = [
        {"partnumber": "BOLT-1", "revision": "", "description": "Bolt", "folder": r"C:\CAD\fasteners\bolts", "process": "purchase"},
        {"partnumber": "PLATE-1", "revision": "A", "description": "Plate", "folder": r"C:\CAD\\plates", "process": "lasercut"},
        {"partnumber": "RIVET-1", "revision": "", "description": "Rivet", "process": "fasteners"},
    ]
    flat_txt = "\n".join(repr(r) for r in flat_rows)
    tree_txt = "\n".join(
        [
            "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
            "1\tASM-1\tA\t1",
            "1.1\tBOLT-1\t\t4",
            "1.2\tPLATE-1\tA\t1",
            "1.3\tRIVET-1\t\t6",
        ]
    )
    zip_bytes = _make_zip(flat_txt, tree_txt)

    with app.app_context():
        import_bom_zip(zip_bytes, "test.zip", seed_tag="test")

        bolt = Part.objects(part_number="BOLT-1", revision="").first()
        rivet = Part.objects(part_number="RIVET-1", revision="").first()
        plate = Part.objects(part_number="PLATE-1", revision="A").first()

        assert bolt is not None
        assert rivet is not None
        assert plate is not None

        assert "hardware" in (bolt.processes or [])
        assert "hardware" in (rivet.processes or [])
        assert bolt.attrs.get("process") == "hardware"
        assert rivet.attrs.get("process") == "hardware"
        assert "hardware" not in (plate.processes or [])

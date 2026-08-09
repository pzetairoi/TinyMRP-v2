# tests/test_bom_import_hardware.py
import io
import zipfile
from pathlib import Path
from collections import Counter
import pytest

from app.models.part import Part
from app.models.bom import BOMLink
from app.services.docpacks import _flatten_bom
from app.services.field_config import save_field_config
from app.services.upload_pack import import_upload_pack


SAMPLE_BOM = (
    Path(__file__).resolve().parents[1]
    / "sample_data"
    / "cv03_tr_a01_rev_a"
    / "managed"
    / "bom"
    / "CV03-TR-A01_REV_A_2026_07_11_16_41_58.zip"
)


def import_bom_zip(zip_bytes: bytes, filename: str, seed_tag: str = "test") -> dict:
    """Apply an import with draft-replacement policies; flatten diagnostics."""
    result = import_upload_pack(
        zip_bytes,
        filename,
        dry_run=False,
        allow_extra=False,
        seed_tag=seed_tag,
        generate_thumbs=False,
        data_mode="replace_unapproved",
        bom_mode="replace_unapproved",
        file_mode="replace_unapproved",
        approval_mode="preserve",
    )
    return {
        **result["diagnostics"],
        "warnings": result["warnings"],
        "errors": result["errors"],
    }


def _make_zip(flat_txt: str, tree_txt: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("TEST_FLATBOM.txt", flat_txt)
        zf.writestr("TEST_TREEBOM.txt", tree_txt)
    return buf.getvalue()


def _make_zip_with_bom(flat_txt: str, tree_txt: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        flat_bytes = b"\xef\xbb\xbf" + flat_txt.encode("utf-8")
        zf.writestr("TEST_FLATBOM.txt", flat_bytes)
        zf.writestr("TEST_TREEBOM.txt", tree_txt)
    return buf.getvalue()


def test_import_bom_flags_hardware_from_folder(app):
    app.config["HARDWARE_FOLDERS"] = ["FASTENERS"]
    flat_rows = [
        {"partnumber": "BOLT-1", "revision": "", "description": "Bolt", "folder": r"C:\CAD\FastenerLib\bolts", "process": "purchase"},
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
        assert bolt.attrs.get("process") == "purchase"
        assert rivet.attrs.get("process") == "fasteners"
        assert (bolt.canonical or {}).get("processes") == ["hardware"]
        assert (rivet.canonical or {}).get("processes") == ["hardware"]
        assert "hardware" not in (plate.processes or [])


def test_import_bom_aggregates_duplicate_links(app):
    flat_rows = [
        {"partnumber": "ASM-2", "revision": "A", "description": "Assembly"},
        {"partnumber": "CH-2", "revision": "A", "description": "Child"},
    ]
    flat_txt = "\n".join(repr(r) for r in flat_rows)
    tree_txt = "\n".join(
        [
            "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
            "1\tASM-2\tA\t1",
            "1.1\tCH-2\tA\t2",
            "1.2\tCH-2\tA\t3",
        ]
    )
    zip_bytes = _make_zip(flat_txt, tree_txt)

    with app.app_context():
        import_bom_zip(zip_bytes, "test.zip", seed_tag="test")

        links = list(
            BOMLink.objects(parent_pn="ASM-2", parent_rev="A", child_pn="CH-2", child_rev="A")
        )
        assert len(links) == 1
        assert links[0].qty == 5
        occs = links[0].occurrences or []
        assert len(occs) == 2
        assert {o.get("seq") for o in occs} == {1, 2}
        assert sum(float(o.get("qty") or 0) for o in occs) == 5


def test_import_bom_canonicalizes_repeated_subassembly_definitions(app):
    """Expanded copies of the same subassembly must not multiply its children."""
    flat_rows = [
        {"partnumber": "ASM-REPEAT", "revision": "A", "description": "Root"},
        {"partnumber": "SUB-REPEAT", "revision": "A", "description": "Repeated subassembly"},
        {"partnumber": "CH-REPEAT", "revision": "A", "description": "Child"},
    ]
    tree_txt = "\n".join(
        [
            "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
            "1\tASM-REPEAT\tA\t1",
            "1.1\tSUB-REPEAT\tA\t1",
            "1.1.1\tCH-REPEAT\tA\t2",
            "1.2\tSUB-REPEAT\tA\t1",
            "1.2.1\tCH-REPEAT\tA\t2",
        ]
    )

    with app.app_context():
        report = import_bom_zip(_make_zip("\n".join(repr(r) for r in flat_rows), tree_txt), "repeat.zip")

        root_link = BOMLink.objects(
            parent_pn="ASM-REPEAT", parent_rev="A", child_pn="SUB-REPEAT", child_rev="A"
        ).first()
        child_link = BOMLink.objects(
            parent_pn="SUB-REPEAT", parent_rev="A", child_pn="CH-REPEAT", child_rev="A"
        ).first()

        assert root_link is not None
        assert root_link.qty == 2
        assert len(root_link.occurrences or []) == 2
        assert child_link is not None
        assert child_link.qty == 2
        assert len(child_link.occurrences or []) == 1

        flattened = {(pn, rev): qty for pn, rev, qty in _flatten_bom("ASM-REPEAT", "A", full=True)}
        assert flattened[("SUB-REPEAT", "A")] == 2
        assert flattened[("CH-REPEAT", "A")] == 4

        assert report["bom_integrity_status"] == "warning"
        assert report["bom_repeated_subassemblies"] == 1
        assert report["bom_repeated_subassembly_copies_collapsed"] == 1
        assert report["bom_definition_conflicts"] == 0
        assert any(issue.get("stage") == "treebom.integrity" for issue in report["warnings"])


def test_import_bom_conflicting_repeated_subassembly_preserves_existing_definition(app):
    """Ambiguous repeated definitions must be reported and never silently overwrite data."""
    with app.app_context():
        Part(part_number="SUB-CONFLICT", revision="A", description="Existing subassembly").save()
        Part(part_number="OLD-CHILD", revision="A", description="Existing child").save()
        BOMLink(
            parent_pn="SUB-CONFLICT",
            parent_rev="A",
            child_pn="OLD-CHILD",
            child_rev="A",
            qty=7,
        ).save()

        flat_rows = [
            {"partnumber": "ASM-CONFLICT", "revision": "A", "description": "Root"},
            {"partnumber": "SUB-CONFLICT", "revision": "A", "description": "Repeated subassembly"},
            {"partnumber": "NEW-CHILD", "revision": "A", "description": "New child"},
        ]
        tree_txt = "\n".join(
            [
                "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
                "1\tASM-CONFLICT\tA\t1",
                "1.1\tSUB-CONFLICT\tA\t1",
                "1.1.1\tNEW-CHILD\tA\t2",
                "1.2\tSUB-CONFLICT\tA\t1",
                "1.2.1\tNEW-CHILD\tA\t3",
            ]
        )

        report = import_bom_zip(_make_zip("\n".join(repr(r) for r in flat_rows), tree_txt), "conflict.zip")

        root_link = BOMLink.objects(
            parent_pn="ASM-CONFLICT", parent_rev="A", child_pn="SUB-CONFLICT", child_rev="A"
        ).first()
        assert root_link is not None
        assert root_link.qty == 2

        preserved = BOMLink.objects(
            parent_pn="SUB-CONFLICT", parent_rev="A", child_pn="OLD-CHILD", child_rev="A"
        ).first()
        assert preserved is not None
        assert preserved.qty == 7
        assert not BOMLink.objects(
            parent_pn="SUB-CONFLICT", parent_rev="A", child_pn="NEW-CHILD", child_rev="A"
        ).first()

        assert report["bom_integrity_status"] == "conflict"
        assert report["bom_definition_conflicts"] == 1
        assert report["tree_links_skipped_integrity"] == 2
        assert any(
            issue.get("stage") == "treebom.integrity" and issue.get("part_number") == "SUB-CONFLICT"
            for issue in report["errors"]
        )


def test_import_bom_no_duplicate_links_sample(app):
    zip_path = SAMPLE_BOM
    if not zip_path.exists():
        pytest.skip("sample BOM zip not found")
    with zip_path.open("rb") as fh:
        data = fh.read()
    with app.app_context():
        import_bom_zip(data, zip_path.name, seed_tag="test")
        keys = [
            (l.parent_pn, l.parent_rev or "", l.child_pn, l.child_rev or "")
            for l in BOMLink.objects.only("parent_pn", "parent_rev", "child_pn", "child_rev")
        ]
        dups = [k for k, v in Counter(keys).items() if v > 1]
        assert not dups


def test_import_bom_clears_existing_duplicates_sample(app):
    zip_path = SAMPLE_BOM
    if not zip_path.exists():
        pytest.skip("sample BOM zip not found")
    with zip_path.open("rb") as fh:
        data = fh.read()
    with app.app_context():
        import_bom_zip(data, zip_path.name, seed_tag="test")
        link = BOMLink.objects.first()
        assert link is not None
        BOMLink(
            parent_pn=f"  {link.parent_pn}  ",
            parent_rev=link.parent_rev,
            child_pn=f"{link.child_pn} ",
            child_rev=link.child_rev,
            qty=link.qty,
            uom=link.uom or "EA",
        ).save()
        import_bom_zip(data, zip_path.name, seed_tag="test")
        keys = [
            (l.parent_pn, l.parent_rev or "", l.child_pn, l.child_rev or "")
            for l in BOMLink.objects.only("parent_pn", "parent_rev", "child_pn", "child_rev")
        ]
        dups = [k for k, v in Counter(keys).items() if v > 1]
        assert not dups


def test_import_bom_flatbom_utf8_bom_is_ok(app):
    flat_rows = [
        {"partnumber": "BOM-B1", "revision": "A", "description": "Bom Part"},
    ]
    flat_txt = "\n".join(repr(r) for r in flat_rows)
    tree_txt = "\n".join(
        [
            "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
            "1\tBOM-B1\tA\t1",
        ]
    )
    zip_bytes = _make_zip_with_bom(flat_txt, tree_txt)

    with app.app_context():
        import_bom_zip(zip_bytes, "test.zip", seed_tag="test")

        part = Part.objects(part_number="BOM-B1", revision="A").first()
        assert part is not None


def test_import_bom_can_map_comments_to_canonical_process_with_admin_aliases(app):
    flat_rows = [
        {
            "partnumber": "PROC-100",
            "revision": "A",
            "description": "Mapped Process Part",
            "comments": "LASERCUT",
            "secondprocess": "MACHINE",
            "process": "",
            "process2": "",
            "process3": "",
        },
    ]
    flat_txt = "\n".join(repr(r) for r in flat_rows)
    tree_txt = "\n".join(
        [
            "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
            "1\tPROC-100\tA\t1",
        ]
    )
    zip_bytes = _make_zip(flat_txt, tree_txt)

    with app.app_context():
        save_field_config(
            {
                "canonical_aliases": [
                    {
                        "field_id": "process",
                        "aliases": ["process", "processes", "comments", "secondprocess", "thirdprocess"],
                    }
                ]
            }
        )
        import_bom_zip(zip_bytes, "test.zip", seed_tag="test")

        part = Part.objects(part_number="PROC-100", revision="A").first()
        assert part is not None
        assert part.attrs.get("comments") == "LASERCUT"
        assert part.attrs.get("secondprocess") == "MACHINE"
        assert (part.canonical or {}).get("processes") == ["lasercut", "machine"]
        assert (part.processes or []) == ["lasercut", "machine"]

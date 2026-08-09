import io
import zipfile
from pathlib import Path

from app.models.bom import BOMLink
from app.models.part import Part
from app.services.sample_dataset import (
    ensure_sample_engineering_records,
    install_sample_deliverables,
    load_sample_manifest,
    verify_sample_fixture,
)
from app.services.docpacks import DocPackOptions, build_docpack
from app.services.rls_demo import seed_permission_test_environment


def test_sample_fixture_manifest_and_non_overwriting_installer(tmp_path: Path):
    verified = verify_sample_fixture()
    manifest = load_sample_manifest()

    assert verified == {"files": 494, "bytes": 135_500_125}
    assert manifest["part_number"] == "CV03-TR-A01"
    assert manifest["revision"] == "A"

    first = install_sample_deliverables(tmp_path)
    second = install_sample_deliverables(tmp_path)
    assert first == {"copied": 494, "skipped": 0, "bytes": 135_500_125}
    assert second == {"copied": 0, "skipped": 494, "bytes": 0}
    assert (tmp_path / "pdf" / "CV03-TR-A01_REV_A.pdf").is_file()
    assert (tmp_path / "step" / "CV03-TR-A01_REV_A.step").is_file()
    assert (tmp_path / "png" / "CV03-TR-A01_REV_A_DWG.png").is_file()


def test_sample_bom_metadata_seed_is_complete_idempotent_and_released(app):
    with app.app_context():
        first = ensure_sample_engineering_records()
        second = ensure_sample_engineering_records()

        assert first["parts"] == first["parts_total"]
        assert first["bom_links"] == first["bom_links_total"]
        assert first["parts_total"] >= 50
        assert first["bom_links_total"] >= 40
        assert second["parts"] == 0
        assert second["bom_links"] == 0
        assert second["approvals_updated"] == 0
        assert second["part_files"] == 0

        root = Part.objects(part_number="CV03-TR-A01", revision="A").get()
        assert root.description == "CELLV03 Trailer"
        assert root.canonical["approved"] is True
        assert root.canonical["approved_by"] == "TinyManager"
        assert {"3mf", "edr", "pdf", "ply", "png", "step"} <= set(
            root.file_groups
        )
        assert BOMLink.objects(
            parent_pn="CV03-TR-A01",
            parent_rev="A",
            child_pn="CV03-F02",
            child_rev="B",
        ).count() == 1
        held_frame = Part.objects(part_number="CV03-F02", revision="B").get()
        assert held_frame.canonical["approved"] is False
        assert not held_frame.canonical.get("approved_by")
        held_lamp = Part.objects(part_number="ADR-LED-IND", revision="").get()
        assert held_lamp.canonical["approved"] is False
        child = Part.objects(part_number="CV03-TR-11", revision="B").get()
        assert child.canonical["approved"] is True
        assert child.canonical["approved_by"] == "TinyManager"
        assert {"3mf", "dxf", "edr", "pdf", "ply", "png", "step"} <= set(
            child.file_groups
        )


def test_sample_fixture_builds_a_real_root_and_child_docpack(app):
    with app.test_request_context("/"):
        ensure_sample_engineering_records()
        name, payload, mimetype = build_docpack(
            DocPackOptions(
                root_pn="CV03-TR-A01",
                root_rev="A",
                depth="top",
                include_consumed=True,
                file_types=["pdf", "step"],
                want_selected_files=True,
                want_pdf_binder=False,
            )
        )

    assert name.endswith(".zip")
    assert mimetype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = {item.casefold() for item in archive.namelist()}
    assert any("cv03-tr-a01_rev_a.pdf" in item for item in names)
    assert any("cv03-tr-a01_rev_a.step" in item for item in names)
    assert any("cv03-f02_rev_b.pdf" in item for item in names)
    assert any("cv03-f02_rev_b.step" in item for item in names)


def test_seeded_markup_review_exports_as_a_docpack_pdf(app):
    with app.test_request_context("/"):
        seed_permission_test_environment("review.example.com")
        name, payload, mimetype = build_docpack(
            DocPackOptions(
                root_pn="CV03-TR-A01",
                root_rev="A",
                depth="top",
                want_selected_files=False,
                want_markup_files=True,
                want_pdf_binder=False,
            )
        )

    assert name.endswith(".zip")
    assert mimetype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        markup_names = [
            item for item in archive.namelist() if item.startswith("markups/")
        ]
        assert len(markup_names) == 1
        assert archive.read(markup_names[0]).startswith(b"%PDF")

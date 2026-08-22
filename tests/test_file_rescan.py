from pathlib import Path

from app.models.artifact import PartFile
from app.models.part import Part
from app.services import file_rescan


def _touch(path: Path, content: bytes = b"test") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _seed(pn: str, rev: str = "A", **attrs) -> Part:
    return Part(part_number=pn, revision=rev, description="", uom="EA", attrs=attrs).save()


def test_rescan_registers_storage_files_for_every_part(app, tmp_path):
    with app.app_context():
        Part.objects.delete()
        PartFile.objects.delete()
        app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path), "url_prefix": "/d"}]
        _seed("RS-ONE")
        _seed("RS-TWO")
        _touch(tmp_path / "pdf" / "RS-ONE_REV_A.pdf")
        _touch(tmp_path / "step" / "RS-TWO_REV_A.step")

        progress = file_rescan.run_now()

        assert progress["status"] == "done"
        assert progress["total"] == 2
        assert progress["processed"] == 2
        assert PartFile.objects(part_number="RS-ONE", ext_group="pdf").count() == 1
        assert PartFile.objects(part_number="RS-TWO", ext_group="step").count() == 1


def test_rescan_unifies_case_variant_parts_onto_one_record(app, tmp_path):
    """The estate holds case-variant duplicates; a rescan must not double-write.

    Both spellings resolve to the same file on disk, so the scan has to fold
    them onto a single record rather than colliding on unique ``path``.
    """
    with app.app_context():
        Part.objects.delete()
        PartFile.objects.delete()
        app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path), "url_prefix": "/d"}]
        _seed("M12X1.75 X 35 G8", rev="")
        _seed("M12x1.75 x 35 g8", rev="")
        _touch(tmp_path / "png" / "M12X1.75 X 35 G8_REV_.png")

        progress = file_rescan.run_now()

        assert progress["status"] == "done"
        assert PartFile.objects.count() == 1


def test_rescan_reports_progress_and_can_be_cancelled(app, tmp_path):
    with app.app_context():
        Part.objects.delete()
        PartFile.objects.delete()
        app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path), "url_prefix": "/d"}]
        _seed("RS-IDLE")

        assert file_rescan.run_now()["status"] == "done"

        # Cancelling an idle scan is a no-op rather than an error.
        assert file_rescan.cancel()["status"] == "done"


def test_rescan_route_requires_maintenance_permission(app, client):
    response = client.get("/admin/rescan-files")
    assert response.status_code in (302, 401, 403)

    progress = client.get("/admin/rescan-files/progress")
    assert progress.status_code in (302, 401, 403)


def _png(path: Path) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (400, 300), (180, 40, 40)).save(path)


def test_rescan_renders_thumbnails_for_the_images_it_relinks(app, tmp_path):
    """Issue #97 backfill.

    The per-part refresh has always rendered thumbnails; the bulk rescan did
    not, so every image it relinked stayed pictureless and there was no way to
    fix a whole estate short of refreshing each part by hand.
    """
    with app.app_context():
        Part.objects.delete()
        PartFile.objects.delete()
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        _seed("RESCAN-IMG", "A")
        _png(tmp_path / "png" / "RESCAN-IMG_REV_A.png")

        report = file_rescan.run_now()

        assert report["status"] == "done"
        assert report.get("thumbs", 0) >= 1
        record = PartFile.objects(part_number="RESCAN-IMG", ext_group="png").first()
        assert record is not None
        assert record.thumb_rel_path
        assert (tmp_path / record.thumb_rel_path).is_file()

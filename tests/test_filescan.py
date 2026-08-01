from pathlib import Path

from app.services.filescan import discover_part_files


def _touch(path: Path, content: bytes = b"test") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_discover_part_files_includes_ply_and_stl(app, tmp_path):
    with app.app_context():
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        app.config["FILES_URL_PREFIX"] = "http://files.local/deliverables"

        pn = "ABC-01"
        rev = "A"
        base = f"{pn}_REV_{rev}"

        _touch(tmp_path / "ply" / f"{base}.ply")
        _touch(tmp_path / "stl" / f"{base}.stl")

        found = discover_part_files(pn, rev)

        ply = found.get(("ply", False))
        stl = found.get(("stl", False))

        assert ply is not None
        assert ply["ext"] == "ply"
        assert ply["rel_path"] == f"ply/{base}.ply"

        assert stl is not None
        assert stl["ext"] == "stl"
        assert stl["rel_path"] == f"stl/{base}.stl"


def test_discover_part_files_prefers_source_scope(app, tmp_path):
    with app.app_context():
        wip_root = tmp_path / "wip"
        rel_root = tmp_path / "released"
        app.config["FILE_SOURCES"] = [
            {
                "id": "wip",
                "label": "WIP",
                "local_root": str(wip_root),
                "url_prefix": "http://wip.local/files",
                "priority": 1,
                "use_for_approved": False,
                "use_for_unapproved": True,
                "active": True,
            },
            {
                "id": "released",
                "label": "Released",
                "local_root": str(rel_root),
                "url_prefix": "http://released.local/files",
                "priority": 2,
                "use_for_approved": True,
                "use_for_unapproved": False,
                "active": True,
            },
        ]

        pn = "SRC-01"
        rev = "A"
        base = f"{pn}_REV_{rev}"
        _touch(wip_root / "pdf" / f"{base}.pdf", b"wip")
        _touch(rel_root / "pdf" / f"{base}.pdf", b"released")

        unapproved = discover_part_files(pn, rev, approved=False)
        approved = discover_part_files(pn, rev, approved=True)

        assert unapproved[("pdf", False)]["abs_path"].startswith(str(wip_root))
        assert unapproved[("pdf", False)]["http_url"].startswith("http://wip.local/files/")
        assert approved[("pdf", False)]["abs_path"].startswith(str(rel_root))
        assert approved[("pdf", False)]["http_url"].startswith("http://released.local/files/")


def test_discover_part_files_still_finds_convention_named_datasheet(app, tmp_path):
    with app.app_context():
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)

        pn = "DS-BASE"
        rev = "A"
        base = f"{pn}_REV_{rev}"
        _touch(tmp_path / "datasheet" / f"{base}.pdf")

        found = discover_part_files(pn, rev)

        datasheet = found.get(("datasheet", False))
        assert datasheet is not None
        assert datasheet["rel_path"] == f"datasheet/{base}.pdf"


def test_discover_part_files_prefers_attr_named_datasheet(app, tmp_path):
    with app.app_context():
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)

        pn = "DS-ATTR"
        rev = "A"
        base = f"{pn}_REV_{rev}"
        _touch(tmp_path / "datasheet" / f"{base}.pdf", b"generic")
        _touch(tmp_path / "datasheet" / "vendor-file.pdf", b"vendor")

        found = discover_part_files(pn, rev, attrs={"datasheet": "vendor-file.pdf"})

        datasheet = found.get(("datasheet", False))
        assert datasheet is not None
        assert datasheet["rel_path"] == "datasheet/vendor-file.pdf"


def test_discover_part_files_supports_attr_datasheet_relative_path(app, tmp_path):
    with app.app_context():
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)

        pn = "DS-REL"
        rev = "A"
        _touch(tmp_path / "DataSheet" / "Vendor-File.PDF", b"vendor")

        found = discover_part_files(pn, rev, attrs={"datasheet": "datasheet/vendor-file.pdf"})

        datasheet = found.get(("datasheet", False))
        assert datasheet is not None
        assert datasheet["rel_path"].casefold() == "datasheet/vendor-file.pdf"


def test_upsert_skips_paths_already_claimed_in_the_same_batch(app, tmp_path):
    """A shared file must not fail the batch on the unique ``path`` index.

    Blank-revision hardware repeated across subassemblies resolves to one file
    on disk for several identities; the first claims it and the rest are
    skipped instead of raising E11000.
    """
    from app.models.artifact import PartFile
    from app.services.filescan import upsert_part_files_detailed

    shared = tmp_path / "png" / "M12X1.75 X 35 G8_REV_.png"
    _touch(shared)
    record = {
        "ext_group": "png",
        "ext": "png",
        "is_dwg": False,
        "rel_path": "png/M12X1.75 X 35 G8_REV_.png",
        "abs_path": str(shared),
    }

    with app.app_context():
        PartFile.objects.delete()
        result = upsert_part_files_detailed(
            [
                {"part_number": "M12X1.75 X 35 G8", "revision": "", **record},
                {"part_number": "OTHER-PART", "revision": "", **record},
            ]
        )

        assert result["count"] == 1
        assert PartFile.objects(path=str(shared)).count() == 1
        assert PartFile.objects.first().part_number == "M12X1.75 X 35 G8"

        # Re-running keeps the original owner and still does not raise.
        again = upsert_part_files_detailed(
            [{"part_number": "M12X1.75 X 35 G8", "revision": "", **record}]
        )
        assert again["count"] == 1
        assert PartFile.objects(path=str(shared)).count() == 1

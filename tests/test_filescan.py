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


def test_upsert_matches_identity_case_insensitively(app, tmp_path):
    """Case-variant spellings are one artifact, not two.

    Storage lookup is case-insensitive on Windows and the app reads parts with
    ``__iexact`` everywhere, so a variant spelling must update the existing
    record instead of inserting a second one that collides on unique ``path``.
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
                {"part_number": "M12x1.75 x 35 g8", "revision": "", **record},
            ]
        )

        assert result["count"] == 2
        assert PartFile.objects.count() == 1
        # The first-seen spelling stays canonical across later variants.
        assert PartFile.objects.first().part_number == "M12X1.75 X 35 G8"

    # Revision case is unified the same way.
    other = tmp_path / "pdf" / "WIDGET_REV_A.pdf"
    _touch(other)
    pdf = {
        "ext_group": "pdf",
        "ext": "pdf",
        "is_dwg": False,
        "rel_path": "pdf/WIDGET_REV_A.pdf",
        "abs_path": str(other),
    }
    with app.app_context():
        upsert_part_files_detailed([{"part_number": "WIDGET", "revision": "A", **pdf}])
        upsert_part_files_detailed([{"part_number": "widget", "revision": "a", **pdf}])
        assert PartFile.objects(ext_group="pdf").count() == 1


def test_discovery_is_case_insensitive_for_dirs_and_filenames(app, tmp_path):
    """Storage laid out on Linux must resolve identically on Windows.

    Directory and filename casing both vary in real trees, so discovery folds
    case at every path segment rather than relying on the host filesystem.
    """
    with app.app_context():
        app.config["FILE_SOURCES"] = [
            {"local_root": str(tmp_path), "url_prefix": "/deliverables"}
        ]
        # Upper-case directory, mixed-case stem, upper-case extension.
        _touch(tmp_path / "PNG" / "widget-01_rev_a.PNG")
        _touch(tmp_path / "pdf" / "WIDGET-01_REV_A.pdf")

        found = discover_part_files("Widget-01", "A")

        assert found[("png", False)]["rel_path"] == "PNG/widget-01_rev_a.PNG"
        assert found[("pdf", False)]["rel_path"] == "pdf/WIDGET-01_REV_A.pdf"

        # A different query casing resolves to the same files.
        assert discover_part_files("WIDGET-01", "a").keys() == found.keys()


def test_scan_cache_reuses_directory_listings(app, tmp_path, monkeypatch):
    """The bulk-scan cache must not re-list a directory per candidate."""
    from app.services import filescan

    with app.app_context():
        app.config["FILE_SOURCES"] = [
            {"local_root": str(tmp_path), "url_prefix": "/deliverables"}
        ]
        for i in range(3):
            _touch(tmp_path / "png" / f"PART-{i}_REV_A.png")

        calls = {"n": 0}
        real_iterdir = Path.iterdir

        def counting_iterdir(self):
            calls["n"] += 1
            return real_iterdir(self)

        monkeypatch.setattr(Path, "iterdir", counting_iterdir)

        with filescan.scan_cache():
            for i in range(3):
                discover_part_files(f"part-{i}", "A")
            cached = calls["n"]

        # Without the cache the same work re-lists directories many more times.
        calls["n"] = 0
        for i in range(3):
            discover_part_files(f"part-{i}", "A")
        uncached = calls["n"]

        assert cached < uncached


def test_upsert_collapses_case_variant_rows_split_across_storage_roots(app, tmp_path):
    """Rows written before identity matching existed must converge, not collide.

    Two case-variant spellings can each own a record pointing at a different
    storage root. Re-pointing one at the other's path would violate the unique
    ``path`` index, so the loser is removed and a single record survives.
    """
    from app.models.artifact import PartFile
    from app.services.filescan import upsert_part_files_detailed

    old_root = tmp_path / "cadexport"
    new_root = tmp_path / "deliverables"
    name = "AS 1111.1 - M10 X 35 X 35-NNZP_REV_.png"
    _touch(new_root / "png" / name)

    with app.app_context():
        PartFile.objects.delete()
        # Pre-existing split: same identity ignoring case, different roots.
        PartFile(
            part_number="AS 1111.1 - M10 X 35 X 35-NNZP",
            revision="",
            ext_group="png",
            ext="png",
            is_dwg=False,
            rel_path=f"png/{name}",
            path=str(old_root / "png" / name),
        ).save()
        PartFile(
            part_number="AS 1111.1 - M10 x 35 x 35-NNZP",
            revision="",
            ext_group="png",
            ext="png",
            is_dwg=False,
            rel_path=f"png/{name}",
            path=str(new_root / "png" / name),
        ).save()
        assert PartFile.objects.count() == 2

        result = upsert_part_files_detailed(
            [
                {
                    "part_number": "AS 1111.1 - M10 X 35 X 35-NNZP",
                    "revision": "",
                    "ext_group": "png",
                    "ext": "png",
                    "is_dwg": False,
                    "rel_path": f"png/{name}",
                    "abs_path": str(new_root / "png" / name),
                }
            ]
        )

        assert result["count"] == 1
        assert PartFile.objects.count() == 1
        survivor = PartFile.objects.first()
        assert survivor.path == str(new_root / "png" / name)


def test_drop_legacy_unique_path_index_lets_one_file_serve_two_parts(app):
    """Existing databases still carry the index; the drop is what retires it."""
    from app.models.artifact import PartFile
    from app.services.filescan import (
        _LEGACY_UNIQUE_PATH_INDEX,
        drop_legacy_unique_path_index,
        upsert_part_files_detailed,
    )

    with app.app_context():
        collection = PartFile._get_collection()
        collection.create_index("path", name=_LEGACY_UNIQUE_PATH_INDEX, unique=True)

        assert drop_legacy_unique_path_index() is True
        assert _LEGACY_UNIQUE_PATH_INDEX not in collection.index_information()
        # Idempotent: a database that never had it, or has already been
        # migrated, is left alone.
        assert drop_legacy_unique_path_index() is False

        shared = {
            "ext": "pdf",
            "ext_group": "datasheet",
            "rel_path": "datasheet/catalog.pdf",
            "abs_path": "/storage/datasheet/catalog.pdf",
        }
        upsert_part_files_detailed([
            {"part_number": "IDX-1", "revision": "A", **shared},
            {"part_number": "IDX-2", "revision": "A", **shared},
        ])
        assert PartFile.objects(path="/storage/datasheet/catalog.pdf").count() == 2

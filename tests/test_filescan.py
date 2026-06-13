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

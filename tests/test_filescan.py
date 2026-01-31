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

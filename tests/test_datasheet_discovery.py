import io
import json
import zipfile
from pathlib import Path

from app.models.artifact import PartFile
from app.models.auth import Role
from app.models.bom import BOMLink
from app.models.part import Part
from app.services.field_config import get_field_config
from app.services.upload_pack import import_upload_pack


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _touch(path: Path, content: bytes = b"test") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _make_bom_zip(flat_rows: list[dict], tree_rows: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("TEST_FLATBOM.txt", "\n".join(json.dumps(row) for row in flat_rows))
        zf.writestr("TEST_TREEBOM.txt", "\n".join(tree_rows))
    return buf.getvalue()


def test_bom_only_import_discovers_attr_named_datasheet_from_storage(app, tmp_path):
    pn = "IMP-DS"
    rev = "A"
    _touch(tmp_path / "datasheet" / "vendor-file.pdf", b"datasheet")
    zip_bytes = _make_bom_zip(
        [
            {
                "partnumber": pn,
                "revision": rev,
                "description": "Imported part",
                "datasheet": "vendor-file.pdf",
            }
        ],
        [
            "ITEM NO.\tPART NUMBER\tRevision\tQTY.",
            f"1\t{pn}\t{rev}\t1",
        ],
    )

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        import_upload_pack(
            zip_bytes,
            "datasheet-import.zip",
            seed_tag="test",
            allow_extra=False,
            generate_thumbs=False,
        )

        # A properties+BOM package carries no files; the import reconciles
        # file records from storage for every imported part.
        assert Part.objects(part_number=pn, revision=rev).first() is not None
        assert (
            PartFile.objects(part_number=pn, revision=rev, ext_group="datasheet").count()
            == 1
        )


def test_refresh_files_recursive_discovers_attr_named_datasheets(client, app, user, tmp_path):
    role = Role(
        name="datasheet_editor",
        permissions=[
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
            "bom.update",
            "comments.write",
            "files.add",
            "files.replace",
            "markups.write",
            "numbering.allocate",
            "parts.create",
            "parts.revise",
            "parts.update",
            "parts.read_unreleased",
        ],
    ).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    parent_pn = "ASM-DS"
    child_pn = "CH-DS"
    parent_rev = "A"
    child_rev = "B"

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        Part(part_number=parent_pn, revision=parent_rev, attrs={"datasheet": "parent-sheet.pdf"}).save()
        Part(part_number=child_pn, revision=child_rev, attrs={"oem_data_sheet": "child-sheet.pdf"}).save()
        BOMLink(parent_pn=parent_pn, parent_rev=parent_rev, child_pn=child_pn, child_rev=child_rev, qty=1).save()
        _touch(tmp_path / "datasheet" / "parent-sheet.pdf", b"parent")
        _touch(tmp_path / "datasheet" / "child-sheet.pdf", b"child")

    resp = client.post(
        f"/api/parts/{parent_pn}/refresh_files",
        json={"rev": parent_rev, "recursive": True},
    )
    assert resp.status_code == 200

    payload = resp.get_json() or {}
    assert payload.get("ok") is True
    assert payload.get("parts_refreshed") == 2
    assert payload.get("files_found", 0) >= 2

    parent_datasheet = PartFile.objects(
        part_number=parent_pn,
        revision=parent_rev,
        ext_group="datasheet",
        rel_path="datasheet/parent-sheet.pdf",
    ).first()
    child_datasheet = PartFile.objects(
        part_number=child_pn,
        revision=child_rev,
        ext_group="datasheet",
        rel_path="datasheet/child-sheet.pdf",
    ).first()
    assert parent_datasheet is not None
    assert child_datasheet is not None


def test_part_detail_uses_protected_datasheet_metadata_only(client, app, user, tmp_path):
    role = Role(name="datasheet_viewer", permissions=[
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
        ]).save()
    user.roles = [role]
    user.save()
    _login(client, user)

    pn = "DET-DS"
    rev = "A"
    local_path = tmp_path / "datasheet" / "vendor-file.pdf"
    _touch(local_path, b"datasheet")

    with app.app_context():
        app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
        app.config["FILES_LOCAL_ROOT"] = str(tmp_path)
        Part(
            part_number=pn,
            revision=rev,
            description="Detail part",
                attrs={
                    "datasheet": "https://example.com/file.pdf",
                    "approvedby": "QA Person",
                },
        ).save()
        PartFile(
            part_number=pn,
            revision=rev,
            ext_group="datasheet",
            ext="pdf",
            rel_path="datasheet/vendor-file.pdf",
            path=str(local_path),
            source="scan",
        ).save()

    resp = client.get(f"/api/part_detail?pn={pn}&rev={rev}")
    assert resp.status_code == 200

    payload = resp.get_json() or {}
    datasheets = payload.get("files", {}).get("datasheet")
    assert isinstance(datasheets, list)
    local_item = next(
        (item for item in datasheets if item.get("name") == "vendor-file.pdf"),
        None,
    )
    assert local_item is not None
    assert "/files/view/" in (local_item.get("url") or "")
    assert "rel" not in local_item
    assert not any(
        item.get("url") == "https://example.com/file.pdf"
        for item in datasheets
    )
    assert payload["part"]["field_values"]["datasheet"] == local_item["url"]

    local_preview = client.get(local_item["url"])
    assert local_preview.status_code == 200
    assert "X-Frame-Options" not in local_preview.headers
    assert "Content-Security-Policy" not in local_preview.headers

    with app.app_context():
        config = get_field_config()
    datasheet_field = next(field for field in config["fields"] if field["id"] == "datasheet")
    assert datasheet_field["data_type"] == "link"

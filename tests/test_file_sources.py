from app.models.artifact import PartFile
from app.models.auth import Role
from app.models.part import Part
from app.services.files_access import file_token_for


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def test_fileserve_allows_secondary_source_absolute_paths(client, app, user, tmp_path):
    secondary_root = tmp_path / "released"
    file_path = secondary_root / "pdf" / "SRC-200_REV_A.pdf"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"secondary-source")

    with app.app_context():
        user.roles = [
            Role(
                name="file_source_reader",
                permissions=["parts.read", "files.read"],
            ).save()
        ]
        user.save()
        Part(
            part_number="SRC-200",
            revision="A",
            attrs={"approvedby": "QA"},
        ).save()
        app.config["FILE_SOURCES"] = [
            {
                "id": "released",
                "label": "Released",
                "local_root": str(secondary_root),
                "url_prefix": "",
                "priority": 1,
                "use_for_approved": True,
                "use_for_unapproved": True,
                "active": True,
            }
        ]
        pf = PartFile(
            part_number="SRC-200",
            revision="A",
            ext_group="pdf",
            ext="pdf",
            rel_path="pdf/SRC-200_REV_A.pdf",
            path=str(file_path),
            source="released",
        ).save()
        token = file_token_for(pf)

    _login(client, user)
    resp = client.get(f"/files/view/{token}")
    assert resp.status_code == 200
    assert resp.data == b"secondary-source"


def test_fileserve_thumb_kind_serves_thumbnail_not_original(client, app, user, tmp_path):
    root = tmp_path / "root"
    orig_path = root / "png" / "SRC-201_REV_A.png"
    thumb_path = root / "thumbs" / "png" / "SRC-201_REV_A.png"
    orig_path.parent.mkdir(parents=True, exist_ok=True)
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    orig_path.write_bytes(b"full-size-original")
    thumb_path.write_bytes(b"small-thumb")

    with app.app_context():
        user.roles = [
            Role(
                name="thumbnail_reader",
                permissions=["parts.read", "files.read"],
            ).save()
        ]
        user.save()
        Part(
            part_number="SRC-201",
            revision="A",
            attrs={"approvedby": "QA"},
        ).save()
        app.config["FILE_ROOT_LOCAL"] = str(root)
        app.config["FILE_SOURCES"] = []
        pf = PartFile(
            part_number="SRC-201",
            revision="A",
            ext_group="png",
            ext="png",
            rel_path="png/SRC-201_REV_A.png",
            path=str(orig_path),
            thumb_rel_path="thumbs/png/SRC-201_REV_A.png",
        ).save()
        thumb_token = file_token_for(pf, kind="thumb")
        file_token = file_token_for(pf, kind="file")

    _login(client, user)

    thumb_resp = client.get(f"/files/view/{thumb_token}")
    assert thumb_resp.status_code == 200
    assert thumb_resp.data == b"small-thumb"

    file_resp = client.get(f"/files/view/{file_token}")
    assert file_resp.status_code == 200
    assert file_resp.data == b"full-size-original"

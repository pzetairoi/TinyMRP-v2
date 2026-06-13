from app.models.artifact import PartFile
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

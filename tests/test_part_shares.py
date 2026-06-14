import uuid
from urllib.parse import urlsplit

from app.models.artifact import PartFile
from app.models.auth import Role, User
from app.models.part import Part


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _make_user(email: str, *, roles=None):
    user = User(
        email=email,
        password="test-password-123",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=roles or [],
    )
    user.save()
    return user


def test_admin_can_create_public_share_and_revoke_it(client, app, tmp_path):
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["FILE_SOURCES"] = [{"local_root": str(tmp_path)}]

    admin_role = Role(name="admin").save()
    admin = _make_user("admin-share@example.com", roles=[admin_role])
    part = Part(part_number="PN-SHARE", revision="A", description="Shared Part", attrs={"material": "Steel"}).save()

    rel_path = "shared/PN-SHARE/A/part.pdf"
    abs_path = tmp_path / "shared" / "PN-SHARE" / "A" / "part.pdf"
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(b"pdf-bytes")
    PartFile(
        part_number=part.part_number,
        revision=part.revision,
        ext_group="pdf",
        ext="pdf",
        rel_path=rel_path,
        path=str(abs_path),
        content_type="application/pdf",
    ).save()

    _login(client, admin)

    create_resp = client.post(
        f"/api/parts/{part.part_number}/shares",
        json={"rev": part.revision, "expires_in_days": 30},
    )
    assert create_resp.status_code == 200
    create_payload = create_resp.get_json()
    assert create_payload["ok"] is True
    assert create_payload["share"]["status"] == "active"
    assert "/share/part/" in create_payload["url"]

    list_resp = client.get(f"/api/parts/{part.part_number}/shares?rev={part.revision}")
    assert list_resp.status_code == 200
    listed = list_resp.get_json()["shares"]
    assert len(listed) == 1
    assert listed[0]["access_count"] == 0

    share_id = create_payload["share_id"]
    share_token = create_payload["share_token"]
    public_client = app.test_client()

    detail_resp = public_client.get(
        f"/api/share/part/{share_id}/{share_token}/part_detail?pn={part.part_number}&rev={part.revision}"
    )
    assert detail_resp.status_code == 200
    detail_payload = detail_resp.get_json()
    assert detail_payload["part"]["part_number"] == part.part_number
    assert detail_payload["can_parts_edit"] is False
    assert detail_payload["public_share"]["share_id"] == share_id

    pdf_url = detail_payload["files"]["pdf"][0]["url"]
    pdf_path = urlsplit(pdf_url).path
    file_resp = public_client.get(pdf_path)
    assert file_resp.status_code == 200
    assert file_resp.data == b"pdf-bytes"
    assert "no-store" in file_resp.headers.get("Cache-Control", "")

    list_after_access = client.get(f"/api/parts/{part.part_number}/shares?rev={part.revision}")
    assert list_after_access.status_code == 200
    accessed_row = list_after_access.get_json()["shares"][0]
    assert accessed_row["access_count"] >= 1
    assert accessed_row["last_accessed_at"]

    revoke_resp = client.delete(f"/api/parts/{part.part_number}/shares/{share_id}")
    assert revoke_resp.status_code == 200

    revoked_detail = public_client.get(
        f"/api/share/part/{share_id}/{share_token}/part_detail?pn={part.part_number}&rev={part.revision}"
    )
    assert revoked_detail.status_code == 410


def test_non_admin_cannot_create_public_share(client):
    viewer_role = Role(name="viewer", permissions=["items.view"]).save()
    viewer = _make_user("viewer-share@example.com", roles=[viewer_role])
    Part(part_number="PN-NO-SHARE", revision="A", description="No Share").save()

    _login(client, viewer)
    resp = client.post("/api/parts/PN-NO-SHARE/shares", json={"rev": "A", "expires_in_days": 30})
    assert resp.status_code == 403

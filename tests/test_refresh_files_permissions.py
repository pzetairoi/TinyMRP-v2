from app.models.auth import Role, User
from app.models.part import Part


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _make_user(email: str):
    user = User(email=email, password="test", active=True, fs_uniquifier=email)
    user.save()
    return user


def test_refresh_files_permissions(client, user):
    viewer_role = Role(name="viewer", permissions=[
            "bom.read",
            "comments.read",
            "files.read",
            "markups.read",
            "parts.read",
        ]).save()
    editor_role = Role(
        name="editor",
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

    part = Part(part_number="PN-901", revision="A", description="Refresh Part").save()

    user.roles = [viewer_role]
    user.save()
    _login(client, user)
    resp = client.post(f"/api/parts/{part.part_number}/refresh_files", json={"rev": part.revision})
    assert resp.status_code == 404

    editor = _make_user("editor2@example.com")
    editor.roles = [editor_role]
    editor.save()
    _login(client, editor)
    resp2 = client.post(f"/api/parts/{part.part_number}/refresh_files", json={"rev": part.revision})
    assert resp2.status_code == 200
    data = resp2.get_json() or {}
    assert data.get("ok") is True

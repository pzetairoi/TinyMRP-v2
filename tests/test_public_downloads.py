import uuid

from app.models.auth import Role, User


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def test_downloads_require_login(client):
    resp = client.get("/downloads/macro")
    assert resp.status_code in (302, 401)

    resp = client.get("/downloads/addin")
    assert resp.status_code in (302, 401)


def test_downloads_available_to_logged_in_tools_user(client):
    role = Role(name=f"tools-{uuid.uuid4()}", permissions=["exports.run"]).save()
    user = User(
        email="tools-user@example.com",
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=[role],
    ).save()
    _login(client, user)

    resp = client.get("/downloads/macro")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("Content-Disposition", "").lower()

    resp = client.get("/downloads/addin")
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("Content-Disposition", "").lower()

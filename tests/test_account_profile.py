import uuid

from flask_security.utils import hash_password, verify_password

from app.models.auth import Role, User
from app.models.part import Part
from app.models.user_settings import UserSettings
from app.services.user_settings import get_or_create_settings


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _make_user(app, email: str, password: str, roles=None):
    with app.app_context():
        user = User(
            email=email,
            password=hash_password(password),
            active=True,
            fs_uniquifier=str(uuid.uuid4()),
            roles=roles or [],
        )
        user.save()
    return user


def test_account_home_shows_permissions_and_security_summary(client, app):
    viewer = Role(name="account_viewer", permissions=["items.view", "jobs.view"]).save()
    user = _make_user(app, "account@example.com", "current-password-123", [viewer])
    with app.app_context():
        settings = get_or_create_settings(user)
        settings.profile = {
            "display_name": "Account Owner",
            "avatar_color": "#0f766e",
            "avatar_shape": "rounded",
        }
        settings.save()

    _login(client, user)
    resp = client.get("/app")
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    assert "My Account" in body
    assert "Account Owner" in body
    assert "items.view" in body
    assert "jobs.view" in body
    assert "Security Summary" in body
    assert "Change Password" in body


def test_account_profile_update_persists_avatar_preferences(client, app):
    user = _make_user(app, "profile@example.com", "current-password-123")
    _login(client, user)

    resp = client.post(
        "/app/profile",
        data={
            "display_name": "Profile Owner",
            "avatar_color": "#be123c",
            "avatar_shape": "square",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    settings = UserSettings.objects(user_id=user).first()
    assert settings is not None
    assert settings.profile["display_name"] == "Profile Owner"
    assert settings.profile["avatar_color"] == "#be123c"
    assert settings.profile["avatar_shape"] == "square"


def test_account_password_change_updates_password_hash(client, app):
    user = _make_user(app, "password@example.com", "current-password-123")
    old_hash = user.password
    _login(client, user)

    resp = client.post(
        "/app/password",
        data={
            "current_password": "current-password-123",
            "new_password": "new-password-4567",
            "confirm_password": "new-password-4567",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    user.reload()
    assert user.password != old_hash
    with app.app_context():
        assert verify_password("new-password-4567", user.password)
        assert not verify_password("current-password-123", user.password)


def test_part_detail_exposes_resolved_identity_profiles(client, app):
    viewer = Role(name="identity_viewer", permissions=["items.view"]).save()
    viewer_user = _make_user(app, "viewer@example.com", "viewer-password-123", [viewer])
    owner_user = _make_user(app, "owner@example.com", "owner-password-123")
    with app.app_context():
        owner_settings = get_or_create_settings(owner_user)
        owner_settings.profile = {
            "display_name": "Drawing Owner",
            "avatar_color": "#166534",
            "avatar_shape": "rounded",
        }
        owner_settings.save()

    part = Part(
        part_number="PN-IDENTITY",
        revision="A",
        description="Identity Part",
        attrs={
            "uploaded_by": "owner@example.com",
            "comments": [
                {
                    "author": "owner@example.com",
                    "text": "Released for manufacturing",
                    "ts": "2026-06-14T10:00:00",
                }
            ],
        },
    ).save()

    _login(client, viewer_user)
    resp = client.get(f"/api/part_detail?pn={part.part_number}&rev={part.revision}")
    assert resp.status_code == 200

    payload = resp.get_json()
    assert payload["uploader_profile"]["label"] == "Drawing Owner"
    assert payload["uploader_profile"]["avatar_shape"] == "rounded"
    assert payload["comments"][0]["author_display"] == "Drawing Owner"
    assert payload["comments"][0]["author_profile"]["avatar_color"] == "#166534"

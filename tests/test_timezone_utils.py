from datetime import datetime

from app.models.app_settings import AppSettings
from app.models.auth import Role, User
from app.services.timezone_utils import clear_timezone_cache, format_display_ts, parse_user_datetime
from app.services.permissions import PERMISSION_REGISTRY


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _admin_user():
    role = Role.objects(name="administrator").first() or Role(name="administrator", permissions=sorted(PERMISSION_REGISTRY)).save()
    return User(
        email="admin-timezone@example.com",
        password="test",
        active=True,
        fs_uniquifier="admin-timezone-user",
        roles=[role],
    ).save()


def test_parse_user_datetime_interprets_naive_input_in_app_timezone(app):
    with app.app_context():
        AppSettings.objects.delete()
        AppSettings(timezone="Australia/Sydney").save()

        with app.test_request_context("/"):
            clear_timezone_cache()
            parsed = parse_user_datetime("2024-01-01T10:30")

        assert parsed == datetime(2023, 12, 31, 23, 30, 0)


def test_format_display_ts_treats_naive_db_values_as_utc(app):
    with app.app_context():
        AppSettings.objects.delete()
        AppSettings(timezone="Australia/Sydney").save()

        with app.test_request_context("/"):
            clear_timezone_cache()
            text = format_display_ts(datetime(2024, 1, 1, 0, 0, 0), fmt="%Y-%m-%d %H:%M:%S %Z")

        assert text == "2024-01-01 11:00:00 AEDT"


def test_admin_settings_timezone_select_round_trip_and_invalid_fallback(client):
    admin = _admin_user()
    _login(client, admin)

    resp = client.post("/admin/settings", data={"timezone": "Australia/Sydney"})
    assert resp.status_code == 302

    settings = AppSettings.objects().order_by("-updated_at").first()
    assert settings is not None
    assert settings.timezone == "Australia/Sydney"

    page = client.get("/admin/settings")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'name="timezone"' in body
    assert 'value="Australia/Sydney"' in body

    invalid = client.post("/admin/settings", data={"timezone": "Mars/Olympus"})
    assert invalid.status_code == 302

    settings = AppSettings.objects().order_by("-updated_at").first()
    assert settings is not None
    assert settings.timezone == "UTC"


def test_admin_settings_hides_legacy_file_source_editor_without_erasing_sources(client):
    admin = _admin_user()
    _login(client, admin)
    settings = AppSettings(
        timezone="UTC",
        file_sources=[{"label": "Legacy", "local_root": "C:/parts", "priority": 1}],
    ).save()

    page = client.get("/admin/settings")
    body = page.get_data(as_text=True)
    assert page.status_code == 200
    assert 'name="source_local_root"' not in body
    assert 'name="process_icon_upload"' in body
    assert 'type="color"' in body
    assert body.index("Process Library") < body.index("Arena Export")

    response = client.post("/admin/settings", data={"timezone": "UTC"})
    assert response.status_code == 302
    settings.reload()
    assert settings.file_sources == [{"label": "Legacy", "local_root": "C:/parts", "priority": 1}]

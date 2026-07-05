import uuid

from flask import url_for
from flask_security.utils import hash_password, verify_password

from app.models.auth import Role, User
from app.models.customer import Customer
from app.models.job import Job
from app.models.order import Order
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
    viewer = Role(
        name="account_viewer",
        permissions=["items.view", "jobs.view", "orders.view", "tools.view", "import.bom"],
    ).save()
    user = _make_user(app, "account@example.com", "current-password-123", [viewer])
    with app.app_context():
        settings = get_or_create_settings(user)
        settings.profile = {
            "display_name": "Account Owner",
            "avatar_color": "#0f766e",
            "avatar_shape": "rounded",
        }
        settings.save()
        customer = Customer(name="Account Customer").save()
        part = Part(part_number="ACC-100", revision="A", description="Account Part").save()
        job = Job(job_number="JOB-ACC-1", title="Assembly run", customer=customer, status="released").save()
        order = Order(order_number="ORD-ACC-1", description="Customer order", customer=customer, status="submitted").save()
    with app.app_context(), app.test_request_context():
        part_href = url_for("ui.part_ui", pn=part.part_number, rev=part.revision)
        job_href = url_for("admin_jobs.jobs_view", job_id=str(job.id))
        order_href = url_for("admin_orders.orders_view", order_id=str(order.id))

    _login(client, user)
    resp = client.get("/app")
    assert resp.status_code == 200

    body = resp.get_data(as_text=True)
    assert "Home" in body
    assert "My Account" in body
    assert "Account Owner" in body
    assert "Quick Actions" in body
    assert "Recent Parts" in body
    assert "Recent Jobs" in body
    assert "Recent Orders" in body
    assert "Items Needing Attention" in body
    assert "ACC-100" in body
    assert "JOB-ACC-1" in body
    assert "ORD-ACC-1" in body
    assert f'href="{part_href}"' in body
    assert f'href="{job_href}"' in body
    assert f'href="{order_href}"' in body
    assert "items.view" in body
    assert "jobs.view" in body
    assert "Security Summary" in body
    assert "Change Password" in body


def test_account_home_requires_authentication(client):
    resp = client.get("/app", follow_redirects=False)
    assert resp.status_code in (302, 401)
    if resp.status_code == 302:
        assert "/login" in (resp.headers.get("Location") or "")


def test_account_home_shows_dashboard_empty_states(client, app):
    viewer = Role(
        name="account_empty_viewer",
        permissions=["items.view", "jobs.view", "orders.view", "import.bom"],
    ).save()
    user = _make_user(app, "empty-home@example.com", "current-password-123", [viewer])

    _login(client, user)
    resp = client.get("/app")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "No recent parts yet" in body
    assert "No recent jobs yet" in body
    assert "No recent orders yet" in body
    assert "History not available yet" in body
    assert "Nothing obvious needs attention" in body


def test_account_home_respects_dashboard_permissions_and_links(client, app):
    role = Role(
        name="account_tools_importor",
        permissions=["items.view", "tools.view", "import.bom", "jobs.manage", "orders.manage", "customers.view", "suppliers.view"],
    ).save()
    user = _make_user(app, "actions@example.com", "current-password-123", [role])

    with app.app_context(), app.test_request_context():
        expected_hrefs = {
            url_for("ui.parts_ui"),
            url_for("ui.upload_pack_ui"),
            url_for("admin_jobs.jobs_new"),
            url_for("admin_orders.orders_new"),
            url_for("admin_customers.customers_list"),
            url_for("admin_suppliers.suppliers_list"),
            url_for("tools.tools_index"),
        }

    _login(client, user)
    resp = client.get("/app")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    for href in expected_hrefs:
        assert f'href="{href}"' in body
    assert "Recent Parts" in body
    assert "Recent Jobs" in body
    assert "Recent Orders" in body
    assert "Open Import" in body


def test_account_home_hides_dashboard_sections_without_permissions(client, app):
    role = Role(name="account_jobs_only", permissions=["jobs.view"]).save()
    user = _make_user(app, "jobs-only@example.com", "current-password-123", [role])
    Job(job_number="JOB-ONLY-1", title="Visible job").save()

    _login(client, user)
    resp = client.get("/app")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Recent Jobs" in body
    assert "JOB-ONLY-1" in body
    assert "Recent Parts" not in body
    assert "Recent Orders" not in body
    assert "Find Parts" not in body
    assert "Upload Pack" not in body
    assert "Tools" not in body


def test_account_home_handles_optional_fields_missing(client, app):
    role = Role(name="account_optional_viewer", permissions=["jobs.view", "orders.view"]).save()
    user = _make_user(app, "optional@example.com", "current-password-123", [role])
    Job(job_number="JOB-OPT-1").save()
    Order(order_number="ORD-OPT-1").save()

    _login(client, user)
    resp = client.get("/app")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "JOB-OPT-1" in body
    assert "ORD-OPT-1" in body
    assert "No title recorded" in body
    assert "No description recorded" in body


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

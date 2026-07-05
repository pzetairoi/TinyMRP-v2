from flask import render_template, render_template_string

from app.models.auth import Role, User


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _admin_user():
    role = Role.objects(name="admin").first() or Role(name="admin").save()
    return User(
        email="ui-admin@example.com",
        password="test",
        active=True,
        fs_uniquifier="ui-admin-user",
        roles=[role],
    ).save()


def test_login_page_renders(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Sign in to TinyMRP" in body
    assert 'data-bs-target="#navbarMain"' in body
    assert ">Login<" in body


def test_logout_returns_to_login(client):
    admin = _admin_user()
    _login(client, admin)

    resp = client.post("/logout", follow_redirects=True)
    assert resp.status_code == 200
    assert "Sign in to TinyMRP" in resp.get_data(as_text=True)


def test_base_layout_authenticated_render_shows_nav_and_logout(client):
    admin = _admin_user()
    _login(client, admin)

    resp = client.get("/admin/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'data-bs-target="#navbarMain"' in body
    assert "Logout" in body
    assert "Admin Dashboard" in body


def test_shared_macros_render_without_empty_action_wrappers(app):
    with app.app_context(), app.test_request_context("/"):
        html = render_template_string(
            """
            {% from "ui/_components.html" import page_header, action_bar, card_header, empty_state, error_state, danger_block %}
            {{ page_header("Title", "Subtitle", "Eyebrow") }}
            {% call action_bar("Helper text") %}<button type="button">Action</button>{% endcall %}
            {{ card_header("Card title", "Card subtitle") }}
            {{ empty_state("Empty", "Nothing here") }}
            {{ error_state("Error", "Something failed") }}
            {{ danger_block("Danger", "Be careful") }}
            """
        )
    assert "tm-page-header" in html
    assert "tm-toolbar" in html
    assert "tm-card-header" in html
    assert "tm-state--empty" in html
    assert "tm-state--error" in html
    assert "tm-danger-block" in html
    assert "tm-page-header__actions" not in html
    assert "tm-card-header__actions" not in html


def test_csrf_error_and_import_result_templates_render(app):
    result = {
        "zip": "sample.zip",
        "root": "ASM-100",
        "parts_created": 1,
        "parts_updated": 2,
        "modified_parts_count": 0,
        "parts_seeded": 0,
        "links_created": 3,
        "links_skipped": 0,
        "parts_with_props": 1,
        "artifacts_added": 4,
        "thumbnails_generated": 1,
        "errors": [],
        "warnings": [],
        "parts_seeded_list": [],
        "artifacts_found_by_type": {},
        "modified_parts": [],
    }
    with app.app_context(), app.test_request_context("/import"):
        csrf_html = render_template("csrf_error.html", reason="Token missing")
        import_html = render_template("import/result.html", result=result)
    assert "CSRF check failed" in csrf_html
    assert "Token missing" in csrf_html
    assert "Import Result" in import_html
    assert "Open BOM UI" in import_html
    assert "Nothing else to review" in import_html


def test_stage1_empty_states_and_warning_pages_render(client, app, tmp_path):
    admin = _admin_user()
    _login(client, admin)
    app.config["HELP_STATIC_DIR"] = str(tmp_path)

    expectations = {
        "/admin/jobs/": "No jobs found",
        "/admin/orders/": "No orders found",
        "/admin/suppliers/": "No suppliers found",
        "/admin/customers/": "No customers found",
        "/admin/audit/": "No audit entries found",
        "/admin/purge-parts": "This action permanently deletes data.",
        "/help": "Help content not generated yet",
    }

    for url, needle in expectations.items():
        resp = client.get(url)
        assert resp.status_code == 200, url
        assert needle in resp.get_data(as_text=True), url


def test_stage1_server_rendered_pages_and_shell_routes_render(client, app, tmp_path):
    admin = _admin_user()
    _login(client, admin)
    app.config["HELP_STATIC_DIR"] = str(tmp_path)
    csrf_pages = {
        "/admin/settings",
        "/admin/users",
        "/admin/users/new",
        "/admin/roles/new",
        "/admin/jobs/new",
        "/admin/orders/new",
        "/admin/suppliers/new",
        "/admin/customers/new",
        "/admin/purge-parts",
        "/tools/excelcompile",
    }

    server_pages = {
        "/admin/": "Admin Dashboard",
        "/admin/settings": "Admin Settings",
        "/admin/users": "Users",
        "/admin/users/new": "Create User",
        "/admin/purge-parts": "Delete all parts / BOM / files",
        "/admin/roles/": "Roles",
        "/admin/roles/new": "Create Role",
        "/admin/audit/": "Audit Log",
        "/admin/metrics": "Admin Metrics",
        "/admin/jobs/": "Jobs",
        "/admin/jobs/new": "Job number",
        "/admin/orders/": "Orders",
        "/admin/orders/new": "Order number",
        "/admin/suppliers/": "Suppliers",
        "/admin/suppliers/new": "Supplier Details",
        "/admin/customers/": "Customers",
        "/admin/customers/new": "Customer Details",
        "/help": "Help",
        "/tools/": "SolidWorks Setup",
        "/tools/excelcompile": "Upload Workbook",
    }

    for url, needle in server_pages.items():
        resp = client.get(url)
        assert resp.status_code == 200, url
        body = resp.get_data(as_text=True)
        assert needle in body, url
        if url in csrf_pages:
            assert 'csrf_token' in body, url

    shell_pages = [
        "/ui/parts",
        "/ui/part/TEST-100?rev=A",
        "/ui/upload-pack",
        "/ui/admin/addin",
        "/ui/admin/fields",
        "/ui/addin/tokens",
        "/import/",
    ]

    for url in shell_pages:
        resp = client.get(url, follow_redirects=True)
        assert resp.status_code == 200, url
        body = resp.get_data(as_text=True)
        assert 'id="root"' in body, url

import re
import uuid

from flask import render_template, render_template_string, url_for

from app.models.auth import Role, User


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = user.get_id()
        sess["_fresh"] = True


def _make_role(name, permissions=None):
    return Role(name=f"{name}-{uuid.uuid4()}", permissions=permissions or []).save()


def _make_user(email, roles=None):
    return User(
        email=email,
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
        roles=roles or [],
    ).save()


def _admin_user():
    role = Role.objects(name="admin").first() or Role(name="admin").save()
    return User(
        email="ui-admin@example.com",
        password="test",
        active=True,
        fs_uniquifier="ui-admin-user",
        roles=[role],
    ).save()


def _menu_html(body, menu_id):
    match = re.search(rf'<ul[^>]*aria-labelledby="{menu_id}"[^>]*>(.*?)</ul>', body, re.S)
    assert match, menu_id
    return match.group(1)


def test_login_page_renders(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Sign in to TinyMRP" in body
    assert 'data-bs-target="#navbarMain"' in body
    assert ">Login<" in body
    assert ">Parts<" not in body
    assert "Search parts..." not in body
    assert 'id="navAdmin"' not in body
    assert 'id="navUser"' not in body


def test_logout_returns_to_login(client):
    admin = _admin_user()
    _login(client, admin)

    resp = client.post("/logout", follow_redirects=True)
    assert resp.status_code == 200
    assert "Sign in to TinyMRP" in resp.get_data(as_text=True)


def test_base_layout_authenticated_render_shows_account_nav_without_admin_clutter(client):
    user = _make_user("ui-basic@example.com")
    _login(client, user)

    resp = client.get("/app")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'data-bs-target="#navbarMain"' in body
    assert ">Parts<" in body
    assert "Logout" in body
    assert 'id="navAdmin"' not in body
    user_menu = _menu_html(body, "navUser")
    assert "My Account" in user_menu
    assert "Tokens" in user_menu
    assert "Help" in user_menu
    assert "Admin Dashboard" not in user_menu
    assert "Purge Parts Data" not in user_menu
    assert 'action="/logout"' in user_menu
    assert 'csrf_token' in user_menu
    assert "Home" in body
    assert "Quick Actions" in body


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


def test_navigation_permission_groupings_and_active_states(client, app):
    tools_import_role = _make_role("nav_tools_import", ["tools.view", "import.bom"])
    jobs_role = _make_role("nav_jobs", ["jobs.view", "jobs.manage"])
    orders_role = _make_role("nav_orders", ["orders.view", "orders.manage"])
    companies_role = _make_role(
        "nav_companies",
        ["customers.view", "customers.manage", "suppliers.view", "suppliers.manage"],
    )

    tools_import_user = _make_user("ui-tools-import@example.com", [tools_import_role])
    jobs_user = _make_user("ui-jobs@example.com", [jobs_role])
    orders_user = _make_user("ui-orders@example.com", [orders_role])
    companies_user = _make_user("ui-companies@example.com", [companies_role])

    with app.test_request_context():
        tools_href = url_for("tools.tools_index")
        import_href = url_for("ui.upload_pack_ui")
        jobs_list_href = url_for("admin_jobs.jobs_list")
        jobs_new_href = url_for("admin_jobs.jobs_new")
        orders_list_href = url_for("admin_orders.orders_list")
        orders_new_href = url_for("admin_orders.orders_new")
        customers_list_href = url_for("admin_customers.customers_list")
        customers_new_href = url_for("admin_customers.customers_new")
        suppliers_list_href = url_for("admin_suppliers.suppliers_list")
        suppliers_new_href = url_for("admin_suppliers.suppliers_new")

    _login(client, tools_import_user)
    resp = client.get("/app")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'href="/ui/parts"' in body
    assert f'href="{tools_href}"' in body
    assert f'href="{import_href}"' in body
    assert ">Jobs<" not in body
    assert ">Orders<" not in body
    assert ">Companies<" not in body
    assert 'id="navAdmin"' not in body

    _login(client, jobs_user)
    resp = client.get("/admin/jobs/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="navJobs"' in body
    assert 'id="navJobs" role="button"' in body
    assert f'href="{jobs_list_href}"' in body
    assert f'href="{jobs_new_href}"' in body
    assert 'nav-link dropdown-toggle active' in body

    _login(client, orders_user)
    resp = client.get("/admin/orders/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="navOrders"' in body
    assert f'href="{orders_list_href}"' in body
    assert f'href="{orders_new_href}"' in body
    assert 'nav-link dropdown-toggle active' in body

    _login(client, companies_user)
    resp = client.get("/admin/customers/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="navCompanies"' in body
    assert "Customers" in body
    assert "Suppliers" in body
    assert f'href="{customers_list_href}"' in body
    assert f'href="{customers_new_href}"' in body
    assert f'href="{suppliers_list_href}"' in body
    assert f'href="{suppliers_new_href}"' in body
    assert 'nav-link dropdown-toggle active' in body


def test_admin_navigation_moves_operational_links_out_of_account_menu(client, app, tmp_path):
    admin = _admin_user()
    _login(client, admin)
    app.config["HELP_STATIC_DIR"] = str(tmp_path)

    with app.test_request_context():
        admin_href = url_for("admin.admin_index")
        fields_href = url_for("ui.admin_fields_ui")
        settings_href = url_for("admin.admin_settings")
        users_href = url_for("admin.users_list")
        roles_href = url_for("admin_roles.roles_list")
        audit_href = url_for("admin_audit.audit_list")
        purge_href = url_for("admin.purge_parts")

    resp = client.get("/admin/settings")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="navAdmin"' in body
    admin_menu = _menu_html(body, "navAdmin")
    user_menu = _menu_html(body, "navUser")
    assert f'href="{admin_href}"' in admin_menu
    assert f'href="{fields_href}"' in admin_menu
    assert f'href="{settings_href}"' in admin_menu
    assert f'href="{users_href}"' in admin_menu
    assert f'href="{roles_href}"' in admin_menu
    assert f'href="{audit_href}"' in admin_menu
    assert f'href="{purge_href}"' in admin_menu
    assert "Danger Zone" in admin_menu
    assert "Purge Parts Data" in admin_menu
    assert "Admin Dashboard" not in user_menu
    assert "Field Configuration" not in user_menu
    assert "App Settings" not in user_menu
    assert "Users" not in user_menu
    assert "Roles" not in user_menu
    assert "Audit Log" not in user_menu
    assert "Purge Parts Data" not in user_menu
    assert "My Account" in user_menu
    assert "Tokens" in user_menu
    assert "Help" in user_menu

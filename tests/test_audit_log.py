# tests/test_audit_log.py
import ast
from pathlib import Path

from app.models.audit import AuditLog
from app.services.audit import log_action
from app.models.auth import Role, User
from app.services.permissions import PERMISSION_REGISTRY


def test_audit_log_captures_ip_method_endpoint(app):
    with app.test_request_context(
        "/downloads/macro?foo=bar",
        headers={
            "X-Forwarded-For": "203.0.113.10, 10.0.0.1",
            "User-Agent": "AuditTest/1.0",
            "X-Request-Id": "req-123",
        },
        method="GET",
    ):
        log_action("test.audit", resource_type="download", resource="macro.swp")

    entry = AuditLog.objects(action="test.audit").first()
    assert entry is not None
    assert entry.ip == "203.0.113.10"
    assert entry.method == "GET"
    assert entry.endpoint == "/downloads/macro"
    assert "AuditTest/1.0" in (entry.ua or "")


def test_audit_log_captures_the_calling_ui_page_and_redacts_share_tokens(app):
    with app.test_request_context(
        "/api/part_detail?pn=PART-100&rev=A",
        headers={"X-TinyMRP-Page": "/ui/part/PART-100?rev=A&search=private"},
    ):
        log_action("part.notes.update", resource_type="part", resource="PART-100:A")

    entry = AuditLog.objects(action="part.notes.update").first()
    assert entry.extra["page_path"] == "/ui/part/PART-100?rev=A"

    with app.test_request_context(
        "/api/share/part/share-id/secret-token/part_detail",
        headers={"X-TinyMRP-Page": "/share/part/share-id/secret-token?rev=B"},
    ):
        log_action("part.share.docpack.build", resource_type="part", resource="PART-200:B")

    shared = AuditLog.objects(action="part.share.docpack.build").first()
    assert shared.extra["page_path"] == "/share/part/[redacted]?rev=B"
    assert "secret-token" not in shared.extra["page_path"]


def test_visible_pages_are_audited_without_background_request_noise(client):
    user = User(
        email="page-visitor@example.com",
        password="test",
        active=True,
        fs_uniquifier="page-visitor",
    ).save()
    with client.session_transaction() as session:
        session["_user_id"] = user.get_id()
        session["_fresh"] = True

    response = client.post(
        "/ui/activity/page-view",
        json={"path": "/ui/part/CV03-TR-A01?rev=A&search=ignored"},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 204
    page_event = AuditLog.objects(action="page.view").get()
    assert page_event.resource == "/ui/part/CV03-TR-A01?rev=A"
    assert page_event.extra["page_path"] == page_event.resource

    # A server-rendered page is captured by the HTML response hook as well.
    assert client.get("/app").status_code == 200
    assert AuditLog.objects(action="page.view", resource="/app").count() == 1

    action_response = client.post(
        "/app/home-prefs",
        data={"show_parts": "on", "items_limit": "5"},
        headers={"Origin": "http://localhost", "Referer": "http://localhost/app"},
    )
    assert action_response.status_code == 302
    action_event = AuditLog.objects(action="page.action").get()
    assert action_event.extra["page_path"] == "/app"
    assert action_event.extra["summary"] == "Saved changes"
    assert action_event.endpoint == "/app/home-prefs"


def test_background_read_handlers_have_no_audit_writes():
    noisy_actions = {
        "bom.view",
        "docpack.options",
        "file.list",
        "file.view",
        "job.view",
        "order.view",
        "part.files.view",
        "part.view",
        "parts.list",
        "whereused.view",
        "part.share.docpack.options",
    }
    found = []
    for path in Path("app/views").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "log_action":
                continue
            candidates = list(node.args)
            candidates.extend(
                keyword.value for keyword in node.keywords if keyword.arg == "action"
            )
            for candidate in candidates:
                if isinstance(candidate, ast.Constant) and candidate.value in noisy_actions:
                    found.append(f"{path}:{node.lineno}:{candidate.value}")
    assert found == []


def test_admin_activity_can_filter_by_calling_ui_page(client):
    admin_role = Role(name="administrator", permissions=sorted(PERMISSION_REGISTRY)).save()
    admin = User(email="page-audit-admin@example.com", password="test", active=True, fs_uniquifier="page-audit-admin", roles=[admin_role]).save()
    AuditLog(
        email="parts-user@example.com",
        action="page.view",
        resource_type="page",
        resource="/ui/parts",
        endpoint="/ui/activity/page-view",
        extra={"page_path": "/ui/parts"},
    ).save()
    AuditLog(
        email="upload-user@example.com",
        action="upload.pack",
        endpoint="/api/upload/pack",
        extra={"page_path": "/ui/upload-pack"},
    ).save()
    with client.session_transaction() as session:
        session["_user_id"] = admin.get_id()
        session["_fresh"] = True

    response = client.get("/admin/audit/?page=/ui/parts")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "parts-user@example.com" in body
    assert "upload-user@example.com" not in body
    assert "Page / location" in body


def test_admin_activity_view_groups_actions_and_keeps_technical_detail(client):
    admin_role = Role(name="administrator", permissions=sorted(PERMISSION_REGISTRY)).save()
    admin = User(email="audit-admin@example.com", password="test", active=True, fs_uniquifier="audit-admin", roles=[admin_role]).save()
    target = User(email="worker@example.com", password="test", active=True, fs_uniquifier="audit-worker").save()
    AuditLog(
        user_id=str(target.id),
        email=target.email,
        action="part.view",
        resource_type="part",
        resource="PART-100:A",
        method="GET",
        endpoint="/api/part_detail",
        ip="203.0.113.4",
    ).save()
    AuditLog(
        user_id=str(target.id),
        email=target.email,
        action="upload.pack",
        resource_type="import",
        resource="parts.zip",
        method="POST",
        endpoint="/api/upload/pack",
        extra={"parts_imported": 12, "files_uploaded": 4},
    ).save()
    with client.session_transaction() as session:
        session["_user_id"] = admin.get_id()
        session["_fresh"] = True

    response = client.get(f"/admin/audit/?user_id={target.id}&include_background=1")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "worker@example.com" in body
    assert "Opened a part" in body
    assert "Uploaded a BOM pack" in body
    assert "12" in body
    assert "Technical details" in body
    assert "/api/part_detail" in body

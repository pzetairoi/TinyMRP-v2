# tests/test_audit_log.py
from app.models.audit import AuditLog
from app.services.audit import log_action
from app.models.auth import Role, User


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


def test_admin_activity_view_groups_actions_and_keeps_technical_detail(client):
    admin_role = Role(name="admin").save()
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

    response = client.get(f"/admin/audit/?user_id={target.id}")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "worker@example.com" in body
    assert "Opened a part" in body
    assert "Uploaded a BOM pack" in body
    assert "12" in body
    assert "Technical details" in body
    assert "/api/part_detail" in body

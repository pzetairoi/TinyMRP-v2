# tests/test_audit_log.py
from app.models.audit import AuditLog
from app.services.audit import log_action


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

"""The environment panel must never echo a usable secret."""
import os

from app.services.diagnostics import _redact, config_rows, environment_report


def test_secrets_are_never_rendered_verbatim(app):
    with app.app_context():
        assert _redact("SECRET_KEY", "super-secret-value") == "set (18 chars)"
        assert _redact("SECURITY_PASSWORD_SALT", "abc") == "set (3 chars)"
        assert _redact("API_TOKEN", "tok") == "set (3 chars)"
        # Unset stays empty rather than claiming a value exists.
        assert _redact("SECRET_KEY", "") == ""
        assert _redact("SECRET_KEY", None) == ""


def test_uri_credentials_are_stripped_but_host_kept(app):
    with app.app_context():
        out = _redact("MONGO_URI", "mongodb://user:S3cret@prod-db:27017/tinymrp")
        assert "S3cret" not in out and "user" not in out
        assert "prod-db:27017" in out and "tinymrp" in out
        # A credential-free URI is safe to show in full.
        assert _redact("MONGO_URI", "mongodb://localhost:27017/db") == "mongodb://localhost:27017/db"


def test_config_rows_flag_secrets_and_report_provenance(app):
    with app.app_context():
        os.environ["SECRET_KEY"] = "env-secret-value"
        try:
            rows = {row["key"]: row for row in config_rows()}
        finally:
            os.environ.pop("SECRET_KEY", None)
        assert rows["SECRET_KEY"]["secret"] is True
        assert "env-secret-value" not in rows["SECRET_KEY"]["value"]
        assert rows["FILES_LOCAL_ROOT"]["secret"] is False


def test_environment_report_sections_are_present(app):
    with app.app_context():
        report = environment_report()
        assert set(report) == {"config", "storage", "records"}
        assert isinstance(report["storage"], list)
        assert "total" in report["records"]

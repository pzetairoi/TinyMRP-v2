"""Mongo authentication posture tests (OPS-DBAUTH-01, Phase 5).

Mongo authentication is opt-in because enabling it on an existing data volume
requires creating users first - Mongo only honours MONGO_INITDB_ROOT_* on the
first boot of an empty data directory. That constraint is real and is why this
cannot simply be forced on for running deployments.

What was wrong is that "unauthenticated" was both the default AND silent:
nothing warned the operator, and nothing reported it.

These tests cover the classification helper, the startup warning, the opt-in
fail-closed switch, and the guarantee that nothing sensitive leaks through the
unauthenticated readiness endpoint.
"""

from __future__ import annotations

import mongomock
import pytest
from mongoengine import connect, disconnect

import app as app_module
from app.services.mongo_auth import describe_mongo_auth


# --- classification ----------------------------------------------------------


def test_credentials_in_uri_are_recognised():
    status = describe_mongo_auth(
        "mongodb://user:pass@mongo:27017/tinymrp?authSource=admin"
    )
    assert status["authenticated"] is True
    assert status["risk"] == "ok"
    assert status["message"] == ""


def test_networked_uri_without_credentials_is_flagged():
    status = describe_mongo_auth("mongodb://mongo:27017/tinymrp")
    assert status["authenticated"] is False
    assert status["risk"] == "unauthenticated"
    assert "NO AUTHENTICATION" in status["message"]


def test_loopback_without_credentials_is_only_informational():
    """A local dev database is not worth alarming about."""
    status = describe_mongo_auth("mongodb://localhost:27017/tinymrp")
    assert status["risk"] == "local-only"
    assert status["localhost_only"] is True


@pytest.mark.parametrize(
    "uri",
    [
        "mongodb://127.0.0.1:27017/db",
        "mongodb://[::1]:27017/db",
        "mongodb://localhost/db",
    ],
)
def test_loopback_forms_are_all_recognised(uri):
    assert describe_mongo_auth(uri)["localhost_only"] is True


def test_replica_set_with_one_remote_host_is_not_local_only():
    """A seed list is only local if EVERY host is loopback."""
    status = describe_mongo_auth(
        "mongodb://localhost:27017,db2.internal:27017/tinymrp"
    )
    assert status["localhost_only"] is False
    assert status["risk"] == "unauthenticated"


def test_empty_and_unparseable_uris_do_not_raise():
    """Classification must never be the reason startup crashes."""
    assert describe_mongo_auth("")["risk"] == "unauthenticated"
    assert describe_mongo_auth("   ")["risk"] == "unauthenticated"
    assert describe_mongo_auth("not a uri at all")["risk"] == "unauthenticated"


def test_message_never_contains_the_credentials():
    """The message is logged and surfaced; it must not echo the URI."""
    status = describe_mongo_auth("mongodb://user:sup3rs3cret@mongo:27017/db")
    assert "sup3rs3cret" not in status["message"]
    assert status["message"] == ""


# --- startup behaviour -------------------------------------------------------


def _make_app(monkeypatch, uri, **env):
    monkeypatch.setenv("TINYMRP_SECURITY_MODE", "compat")
    monkeypatch.setenv("SECRET_KEY", "dbauth-test-key")
    monkeypatch.setenv("SECURITY_PASSWORD_SALT", "dbauth-test-salt")
    monkeypatch.setenv("MONGO_URI", uri)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    disconnect(alias="tinymrp-v2")
    connect(
        alias="tinymrp-v2",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
    )
    app_module.init_mongo = lambda _app: None
    application = app_module.create_app()
    application.config["TESTING"] = True
    return application


def test_unauthenticated_startup_warns_but_still_boots(monkeypatch, caplog):
    """A warning, not a hard failure.

    Refusing to boot would break every existing deployment on upgrade, which is
    a worse outcome than a loud, repeated log line.
    """
    with caplog.at_level("WARNING"):
        app = _make_app(monkeypatch, "mongodb://mongo:27017/tinymrp")

    assert app is not None
    assert app.config["MONGO_AUTH_STATUS"]["risk"] == "unauthenticated"
    assert any(
        "NO AUTHENTICATION" in record.getMessage() for record in caplog.records
    ), "expected a startup security warning"


def test_authenticated_startup_produces_no_warning(monkeypatch):
    app = _make_app(
        monkeypatch, "mongodb://user:pass@mongo:27017/tinymrp?authSource=admin"
    )
    assert app.config["MONGO_AUTH_STATUS"]["risk"] == "ok"


def test_require_flag_makes_startup_fail_closed(monkeypatch):
    """Operators who want the guarantee can opt in to refusing to start."""
    with pytest.raises(RuntimeError, match="TINYMRP_REQUIRE_MONGO_AUTH"):
        _make_app(
            monkeypatch,
            "mongodb://mongo:27017/tinymrp",
            TINYMRP_REQUIRE_MONGO_AUTH="true",
        )


def test_require_flag_allows_an_authenticated_uri(monkeypatch):
    app = _make_app(
        monkeypatch,
        "mongodb://user:pass@mongo:27017/tinymrp?authSource=admin",
        TINYMRP_REQUIRE_MONGO_AUTH="true",
    )
    assert app.config["MONGO_AUTH_STATUS"]["risk"] == "ok"


# --- readiness surface -------------------------------------------------------


def test_readiness_reports_the_warning_without_failing(monkeypatch, tmp_path):
    """An unauthenticated database is a misconfiguration, not an outage.

    Failing readiness would pull a working instance out of the load balancer,
    which does not make the database any safer.
    """
    app = _make_app(monkeypatch, "mongodb://mongo:27017/tinymrp")
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["READINESS_MIN_FREE_DISK_MB"] = 0

    with app.test_client() as client:
        resp = client.get("/api/ready")

    assert resp.status_code == 200, "readiness must stay green"
    assert "mongodb_unauthenticated" in resp.get_json()["warnings"]


def test_readiness_omits_the_warning_when_authenticated(monkeypatch, tmp_path):
    app = _make_app(
        monkeypatch, "mongodb://user:pass@mongo:27017/tinymrp?authSource=admin"
    )
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["READINESS_MIN_FREE_DISK_MB"] = 0

    with app.test_client() as client:
        body = client.get("/api/ready").get_json()

    assert body["warnings"] == []


def test_readiness_never_leaks_the_connection_string(monkeypatch, tmp_path):
    app = _make_app(monkeypatch, "mongodb://user:sup3rs3cret@mongo:27017/db")
    app.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    app.config["READINESS_MIN_FREE_DISK_MB"] = 0

    with app.test_client() as client:
        raw = client.get("/api/ready").get_data(as_text=True)

    assert "sup3rs3cret" not in raw
    assert "mongodb://" not in raw

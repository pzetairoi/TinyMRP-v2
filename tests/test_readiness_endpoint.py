"""Liveness/readiness split tests (OPS-HEALTH-01, Phase 5).

/api/health returned ok=true unconditionally: it proved the process was
serving and nothing else. The container HEALTHCHECK and the guided VPS deploy
scripts rely on it, so an instance whose database was unreachable still
reported healthy.

/api/ready is the new endpoint that actually proves the dependencies work and
answers 503 when they do not.

The most important assertions here are the ones protecting the PROTECTED
deployment path: /api/health must keep its exact contract, and readiness must
never be the reason a container is killed.
"""

from __future__ import annotations

import mongomock
import pytest
from mongoengine import connect, disconnect

import app as app_module


def _make_app(monkeypatch, tmp_path=None, **config):
    monkeypatch.setenv("SECRET_KEY", "readiness-test-key")
    monkeypatch.setenv("SECURITY_PASSWORD_SALT", "readiness-test-salt")

    disconnect(alias="tinymrp-v2")
    connect(
        alias="tinymrp-v2",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
    )
    app_module.init_mongo = lambda _app: None
    application = app_module.create_app()
    application.config["TESTING"] = True
    if tmp_path is not None:
        application.config["FILE_ROOT_LOCAL"] = str(tmp_path)
    application.config.update(config)
    return application


# --- the protected contract --------------------------------------------------


def test_liveness_contract_is_unchanged(monkeypatch):
    """deploy scripts, doctor.sh and the container HEALTHCHECK depend on this.

    They assert JSON with ok=true on /api/health. Changing this shape or making
    it conditional would break the guided VPS/Caddy deployment.
    """
    app = _make_app(monkeypatch)
    with app.test_client() as client:
        resp = client.get("/api/health")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["service"] == "tinymrp"
    assert "server_version" in body


def test_liveness_stays_ok_when_a_dependency_is_broken(monkeypatch):
    """Liveness must not go red on a database problem.

    If it did, the container HEALTHCHECK would kill and restart the process -
    which cannot fix a database outage and turns a degraded instance into a
    crash loop. This is why readiness is a separate endpoint.
    """
    app = _make_app(monkeypatch)

    import app.views.api_health as health_mod

    monkeypatch.setattr(
        health_mod,
        "_check_database",
        lambda: {"ok": False, "error": "injected outage"},
    )

    with app.test_client() as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/ready").status_code == 503


# --- readiness actually proves something -------------------------------------


def test_readiness_ok_when_dependencies_are_healthy(monkeypatch, tmp_path):
    app = _make_app(monkeypatch, tmp_path=tmp_path, READINESS_MIN_FREE_DISK_MB=0)
    with app.test_client() as client:
        resp = client.get("/api/ready")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["storage"]["ok"] is True


def test_readiness_fails_when_database_is_unreachable(monkeypatch, tmp_path):
    app = _make_app(monkeypatch, tmp_path=tmp_path, READINESS_MIN_FREE_DISK_MB=0)

    import app.views.api_health as health_mod

    monkeypatch.setattr(
        health_mod,
        "_check_database",
        lambda: {"ok": False, "error": "connection refused"},
    )

    with app.test_client() as client:
        resp = client.get("/api/ready")

    assert resp.status_code == 503
    assert resp.get_json()["ok"] is False


def test_readiness_fails_when_storage_root_is_missing(monkeypatch, tmp_path):
    """An unmounted volume must be caught before the first import loses data."""
    missing = tmp_path / "not-mounted"
    app = _make_app(monkeypatch, READINESS_MIN_FREE_DISK_MB=0)
    app.config["FILE_ROOT_LOCAL"] = str(missing)

    with app.test_client() as client:
        resp = client.get("/api/ready")

    assert resp.status_code == 503
    assert resp.get_json()["checks"]["storage"]["ok"] is False


def test_readiness_fails_below_the_disk_threshold(monkeypatch, tmp_path):
    app = _make_app(monkeypatch, tmp_path=tmp_path)
    # Any real volume has less than an exabyte free.
    app.config["READINESS_MIN_FREE_DISK_MB"] = 10**12

    with app.test_client() as client:
        resp = client.get("/api/ready")

    assert resp.status_code == 503
    disk = resp.get_json()["checks"]["disk"]
    assert disk["ok"] is False
    assert "free_mb" in disk


def test_disk_threshold_zero_disables_the_check(monkeypatch, tmp_path):
    app = _make_app(monkeypatch, tmp_path=tmp_path, READINESS_MIN_FREE_DISK_MB=0)
    with app.test_client() as client:
        resp = client.get("/api/ready")

    assert resp.status_code == 200


def test_unconfigured_storage_is_not_a_failure(monkeypatch):
    """File features being unused must not make an instance unready."""
    app = _make_app(monkeypatch, READINESS_MIN_FREE_DISK_MB=0)
    app.config["FILE_ROOT_LOCAL"] = ""
    app.config["FILES_LOCAL_ROOT"] = ""

    with app.test_client() as client:
        resp = client.get("/api/ready")

    assert resp.status_code == 200
    assert resp.get_json()["checks"]["storage"]["configured"] is False


# --- it must not leak, and must not need credentials -------------------------


def test_readiness_needs_no_credentials(monkeypatch, tmp_path):
    """An orchestrator polls this before any credential exists."""
    app = _make_app(monkeypatch, tmp_path=tmp_path, READINESS_MIN_FREE_DISK_MB=0)
    with app.test_client() as client:
        resp = client.get("/api/ready")

    assert resp.status_code != 401
    assert resp.status_code != 403


def test_readiness_does_not_leak_configuration(monkeypatch, tmp_path):
    """Unauthenticated, so it must not disclose paths or connection strings."""
    app = _make_app(monkeypatch, tmp_path=tmp_path, READINESS_MIN_FREE_DISK_MB=0)
    with app.test_client() as client:
        raw = client.get("/api/ready").get_data(as_text=True)

    assert "mongodb://" not in raw
    assert str(tmp_path) not in raw, "the storage path must not be echoed"


# --- diagnostics: authenticated detail (OPS-HEALTH-01) -----------------------


def test_diagnostics_requires_authentication(monkeypatch, tmp_path):
    """Unlike health and ready, this one carries detail and must be guarded."""
    app = _make_app(monkeypatch, tmp_path=tmp_path, READINESS_MIN_FREE_DISK_MB=0)
    with app.test_client() as client:
        resp = client.get("/api/diagnostics")

    # Either rejected outright or redirected to login - never 200 with data.
    assert resp.status_code != 200
    assert b"environment" not in resp.data


def test_diagnostics_is_not_in_the_public_health_category(monkeypatch):
    """/api/health and /api/ready are exempt from auth; diagnostics is not."""
    from app.services import security_mode as mode

    assert "api_health.health" in mode._HEALTH_ENDPOINTS
    assert "api_health.ready" in mode._HEALTH_ENDPOINTS
    assert "api_health.diagnostics" not in mode._HEALTH_ENDPOINTS


def test_diagnostics_route_is_registered(monkeypatch):
    app = _make_app(monkeypatch)
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/diagnostics" in rules


def test_every_container_healthcheck_uses_readiness_not_liveness():
    """OPS-HEALTH-01: readiness was built, tested, and wired to nothing.

    /api/health returns ok=true unconditionally, so a container whose Mongo was
    unreachable or whose deliverables volume was unmounted still reported
    healthy and failed on the first real request. Every healthcheck now asks
    the endpoint that actually proves the dependencies work.

    The Dockerfile matters most: that HEALTHCHECK is baked into the image, so
    it applies however the container is launched.
    """
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    for relative in (
        "docker/app/Dockerfile",
        "docker-compose.yml",
        "docker-compose.onefolder.yml",
        "deploy/scripts/lib/common.sh",
    ):
        text = (repo_root / relative).read_text(encoding="utf-8")
        assert "urlopen('http://localhost:8000/api/ready'" in text, relative
        assert "urlopen('http://localhost:8000/api/health'" not in text, relative

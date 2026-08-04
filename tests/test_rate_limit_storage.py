"""Rate-limit storage and failure-policy tests (OPS-RATE-01, Phase 5).

Two separate defects lived here.

1. `memory://` storage keeps counters in EACH gunicorn worker's memory. With
   2 workers a "10 per minute" login limit really allowed 20 attempts per
   minute against the deployment. Redis gives every worker one shared budget.

2. `swallow_errors=True` meant a storage outage silently disabled rate limiting
   altogether. Fail-open is the right default - losing throttling beats
   refusing all traffic - but it is a real security downgrade during an outage
   and the roadmap asks for that to be an explicit, recorded decision rather
   than an accident.

These tests do not require a live Redis; the sharing behaviour itself was
verified separately against a real server. What is pinned here is the
configuration wiring, which is what silently regresses.
"""

from __future__ import annotations

import mongomock
import pytest
from mongoengine import connect, disconnect

import app as app_module


def _make_app(monkeypatch, **env):
    monkeypatch.setenv("TINYMRP_SECURITY_MODE", "compat")
    monkeypatch.setenv("SECRET_KEY", "ratelimit-test-key")
    monkeypatch.setenv("SECURITY_PASSWORD_SALT", "ratelimit-test-salt")
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


# --- the redis client must actually be installed -----------------------------


def test_redis_client_is_available():
    """Without the client, Flask-Limiter silently falls back to memory.

    That is the failure mode this test exists to catch: pointing
    RATE_LIMIT_STORAGE_URI at Redis appears to work while every worker keeps
    its own counters.
    """
    import redis  # noqa: F401


def test_redis_client_satisfies_the_limits_constraint():
    """limits 5.8.0 declares redis<8.0.0; a newer pin would break resolution."""
    import redis

    major = int(redis.__version__.split(".")[0])
    assert major < 8, f"redis {redis.__version__} violates the limits<8.0.0 cap"


# --- storage selection -------------------------------------------------------


def test_memory_storage_is_flagged_as_unshared(monkeypatch):
    app = _make_app(monkeypatch, RATE_LIMIT_STORAGE_URI="memory://")
    assert app.config["RATE_LIMIT_SHARED_STORAGE"] is False


def test_memory_storage_warns_about_per_worker_budgets(monkeypatch, caplog):
    """The defect must be visible, not silent."""
    with caplog.at_level("WARNING"):
        _make_app(monkeypatch, RATE_LIMIT_STORAGE_URI="memory://")

    assert any(
        "per-worker" in record.getMessage() for record in caplog.records
    ), "expected a warning that memory storage multiplies limits by worker count"


def test_redis_uri_is_treated_as_shared(monkeypatch):
    app = _make_app(monkeypatch, RATE_LIMIT_STORAGE_URI="redis://redis:6379/0")
    assert app.config["RATE_LIMIT_SHARED_STORAGE"] is True


def test_unset_storage_uri_defaults_to_memory(monkeypatch):
    """The application default stays memory:// so a bare `flask run` works.

    Redis is supplied by compose, not assumed by the app.
    """
    app = _make_app(monkeypatch, RATE_LIMIT_STORAGE_URI=None)
    assert app.config["RATE_LIMIT_STORAGE_URI"].startswith("memory:")


# --- failure policy ----------------------------------------------------------


def test_failure_policy_defaults_to_fail_open(monkeypatch):
    """Losing rate limiting beats refusing all traffic."""
    app = _make_app(monkeypatch, RATE_LIMIT_FAIL_CLOSED=None)
    assert app.config["RATE_LIMIT_FAIL_CLOSED"] is False


def test_failure_policy_can_be_made_fail_closed(monkeypatch):
    app = _make_app(monkeypatch, RATE_LIMIT_FAIL_CLOSED="true")
    assert app.config["RATE_LIMIT_FAIL_CLOSED"] is True


def test_fail_open_sets_swallow_errors_on_the_limiter(monkeypatch):
    """The policy must reach Flask-Limiter, not just sit in config."""
    app = _make_app(monkeypatch, RATE_LIMIT_FAIL_CLOSED="false")
    limiter = app.extensions.get("tinymrp_limiter")
    assert limiter is not None
    assert limiter._swallow_errors is True


def test_fail_closed_sets_swallow_errors_off(monkeypatch):
    app = _make_app(monkeypatch, RATE_LIMIT_FAIL_CLOSED="true")
    limiter = app.extensions.get("tinymrp_limiter")
    assert limiter is not None
    assert limiter._swallow_errors is False


# --- health endpoints stay exempt --------------------------------------------


def test_health_and_ready_remain_exempt_from_limits(monkeypatch):
    """Monitoring must not be able to throttle an instance out of service."""
    app = _make_app(
        monkeypatch,
        RATE_LIMIT_API="1 per hour",
        RATE_LIMIT_STORAGE_URI="memory://",
    )
    with app.test_client() as client:
        for _ in range(5):
            assert client.get("/api/health").status_code == 200
            assert client.get("/api/ready").status_code in (200, 503)

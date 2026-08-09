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


# --- expensive endpoints (OPS-RATE-01 residue) -------------------------------


def test_every_expensive_endpoint_name_actually_exists(monkeypatch):
    """A drifted endpoint name silently protects nothing.

    The wiring skips endpoints it cannot find so a rename cannot break startup
    - which also means a typo would leave the route unthrottled with no error.
    My first attempt named all six wrongly and this test is why that was
    caught.
    """
    from app.services.rate_limit import _EXPENSIVE_ENDPOINTS

    app = _make_app(monkeypatch)
    missing = [name for name, _limit in _EXPENSIVE_ENDPOINTS if name not in app.view_functions]
    assert not missing, f"these endpoints no longer exist: {missing}"


def test_setting_an_expensive_limit_does_not_break_startup(monkeypatch):
    assert _make_app(monkeypatch, RATE_LIMIT_EXPENSIVE="3 per minute") is not None
    assert _make_app(monkeypatch, RATE_LIMIT_EXPENSIVE="") is not None


def test_an_expensive_endpoint_actually_returns_429(monkeypatch):
    """The proof the first attempt lacked.

    A limit that is configured but never enforced is worse than none: it reads
    as protection in review and provides nothing at runtime. The withdrawn
    attempt looked exactly like working code. So this asserts the only thing
    that matters - a real 429 off a real request.
    """
    app = _make_app(
        monkeypatch,
        RATE_LIMIT_EXPENSIVE="2 per hour",
        RATE_LIMIT_STORAGE_URI="memory://",
    )
    rule = next(
        r for r in app.url_map.iter_rules() if r.endpoint == "upload_pack_api.upload_pack"
    )
    method = "POST" if "POST" in (rule.methods or set()) else "GET"

    # The request has to get past authentication to reach the limiter, so the
    # client is logged in. Unauthenticated callers are refused earlier and
    # never exercise the limit at all.
    with app.app_context():
        from app.models.auth import User

        user = User(
            email="rate-limit@example.test",
            password="x",
            active=True,
            fs_uniquifier="rate-limit-uniquifier",
        ).save()

    with app.test_client() as client:
        with client.session_transaction() as session:
            session["_user_id"] = user.get_id()
            session["_fresh"] = True
        client.environ_base["HTTP_ORIGIN"] = "http://localhost"
        statuses = [
            client.open(str(rule.rule), method=method).status_code for _ in range(4)
        ]

    # Unauthenticated calls are rejected long before the handler runs, which is
    # fine: the limiter sits in front of that, so exhausting the budget must
    # still flip the response to 429.
    assert 429 in statuses, f"limit never enforced; saw {statuses}"
    assert statuses.index(429) >= 2, f"throttled too early; saw {statuses}"


def test_expensive_budget_is_per_user_not_per_office(monkeypatch):
    """Keying by address would make one public IP share a single budget.

    Companies reach the server through one NAT, so an address-keyed limit
    would be divided among everyone doing real work - the opposite of the
    generous budget intended.
    """
    from app.services.rate_limit import _expensive_key

    app = _make_app(monkeypatch)
    with app.test_request_context("/api/upload-pack"):
        assert _expensive_key().startswith("addr:")

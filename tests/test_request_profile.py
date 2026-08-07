"""The profiler must cost nothing when it is off.

A profiler that slows production is one nobody dares enable, which makes it
useless exactly when it is needed. So the important tests here are about the
DISABLED path: no listener registered, no hooks installed, no per-request work.
"""

from __future__ import annotations

from app.services.request_profile import init_request_profiling, profiling_enabled


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("TINYMRP_PROFILE", raising=False)
    assert profiling_enabled() is False


def test_recognises_the_usual_truthy_spellings(monkeypatch):
    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("TINYMRP_PROFILE", value)
        assert profiling_enabled() is True, value
    for value in ("0", "false", "no", "", "  "):
        monkeypatch.setenv("TINYMRP_PROFILE", value)
        assert profiling_enabled() is False, value


def test_installs_nothing_when_disabled(monkeypatch):
    """No hooks, no listener - the whole point of the flag."""
    from flask import Flask

    monkeypatch.delenv("TINYMRP_PROFILE", raising=False)
    app = Flask(__name__)
    before = len(app.before_request_funcs.get(None, []))
    after = len(app.after_request_funcs.get(None, []))

    assert init_request_profiling(app) is False
    assert len(app.before_request_funcs.get(None, [])) == before
    assert len(app.after_request_funcs.get(None, [])) == after


def test_installs_hooks_when_enabled(monkeypatch):
    from flask import Flask

    monkeypatch.setenv("TINYMRP_PROFILE", "1")
    app = Flask(__name__)
    assert init_request_profiling(app) is True
    assert app.before_request_funcs.get(None)
    assert app.after_request_funcs.get(None)


def test_a_profiled_request_reports_its_operation_count(monkeypatch, caplog):
    """The number is the point: query COUNT, not query time."""
    import logging

    from flask import Flask

    monkeypatch.setenv("TINYMRP_PROFILE", "1")
    app = Flask(__name__)
    init_request_profiling(app)

    @app.get("/thing")
    def thing():
        return "ok"

    with caplog.at_level(logging.INFO, logger="tinymrp.profile"):
        assert app.test_client().get("/thing").status_code == 200

    line = "\n".join(r.getMessage() for r in caplog.records)
    assert "mongo ops" in line
    assert "/thing" in line

"""`python run.py` — the entry point locked-down hosts are approved to run.

On a host where `python.exe run.py` is the one blessed command, the only way to
change a port used to be editing run.py, and every such edit then collided with
the next `git pull`. So the bind address, the server and the debugger all come
from the environment, and these tests pin that: a tracked file that has to be
edited per host is the bug being prevented.
"""

from __future__ import annotations

import importlib
import sys

import mongomock
import pytest
from mongoengine import connect, disconnect

import app as app_module

RUN_ENV_KEYS = (
    "TINYMRP_URL",
    "INSTANCE_URL",
    "TINYMRP_ALLOWED_ORIGINS",
    "TINYMRP_BIND_HOST",
    "TINYMRP_BIND_PORT",
    "TINYMRP_SERVER",
    "TINYMRP_DEV",
    "FLASK_DEBUG",
    "TINYMRP_ALLOW_REMOTE_DEBUG",
)


@pytest.fixture
def run_module(monkeypatch):
    """Import run.py against mongomock, with a clean slate of its settings."""

    def _load(**env):
        monkeypatch.setenv("SECRET_KEY", "run-entrypoint-secret-key")
        monkeypatch.setenv("SECURITY_PASSWORD_SALT", "run-entrypoint-password-salt")
        for key in RUN_ENV_KEYS:
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        disconnect(alias="tinymrp-v2")
        connect(
            alias="tinymrp-v2",
            host="mongodb://localhost",
            mongo_client_class=mongomock.MongoClient,
        )
        monkeypatch.setattr(app_module, "init_mongo", lambda _app: None)
        sys.modules.pop("run", None)
        return importlib.import_module("run")

    yield _load
    sys.modules.pop("run", None)


def test_a_loopback_url_keeps_the_server_off_the_network(run_module):
    run = run_module(TINYMRP_URL="http://localhost:5000")
    assert run._resolve_bind() == ("127.0.0.1", 5000)


def test_a_lan_url_binds_every_interface_and_takes_its_port(run_module):
    """A server other people are meant to reach must not listen only to itself.

    Deriving the port from the same value keeps the address users type and the
    socket the server opens from drifting apart - a mismatch breaks login,
    because the origin includes the port.
    """
    run = run_module(TINYMRP_URL="http://tinymrp.local:5555")
    assert run._resolve_bind() == ("0.0.0.0", 5555)


def test_no_declared_url_stays_on_loopback(run_module):
    run = run_module()
    assert run._resolve_bind() == ("127.0.0.1", 5000)


def test_explicit_bind_settings_win(run_module):
    run = run_module(
        TINYMRP_URL="http://tinymrp.local:5555",
        TINYMRP_BIND_HOST="127.0.0.1",
        TINYMRP_BIND_PORT="8123",
    )
    assert run._resolve_bind() == ("127.0.0.1", 8123)


@pytest.mark.parametrize("value", ["not-a-number", "0", "70000"])
def test_a_nonsense_port_stops_startup(run_module, value):
    run = run_module(TINYMRP_BIND_PORT=value)
    with pytest.raises(SystemExit):
        run._resolve_bind()


def test_waitress_is_preferred_over_the_development_server(run_module):
    """The development server is explicitly not for shared use."""
    run = run_module()
    assert run._resolve_server(debug=False) == "waitress"


def test_debug_forces_the_flask_server(run_module):
    """The reloader and interactive debugger are Werkzeug features."""
    run = run_module()
    assert run._resolve_server(debug=True) == "flask"


def test_server_choice_can_be_forced(run_module):
    run = run_module(TINYMRP_SERVER="flask")
    assert run._resolve_server(debug=False) == "flask"
    run = run_module(TINYMRP_SERVER="nginx")
    with pytest.raises(SystemExit):
        run._resolve_server(debug=False)


def test_the_debugger_refuses_a_network_facing_bind(run_module, capsys):
    """Werkzeug's traceback console executes arbitrary Python in this process.

    A debug server anyone on the network can reach is remote code execution
    wearing a friendly error page, so this combination must not start.
    """
    run = run_module(TINYMRP_URL="http://tinymrp.local:5555", TINYMRP_DEV="1")

    assert run.main() == 2

    message = capsys.readouterr().err
    assert "REFUSING TO START" in message
    assert "TINYMRP_ALLOW_REMOTE_DEBUG" in message


def test_the_refusal_can_be_overridden_deliberately(run_module, monkeypatch):
    run = run_module(
        TINYMRP_URL="http://tinymrp.local:5555",
        TINYMRP_DEV="1",
        TINYMRP_ALLOW_REMOTE_DEBUG="1",
    )
    served = {}
    monkeypatch.setattr(run.app, "run", lambda **kwargs: served.update(kwargs))

    assert run.main() == 0
    assert served["host"] == "0.0.0.0"
    assert served["debug"] is True


def test_debugging_on_loopback_is_allowed(run_module, monkeypatch):
    run = run_module(TINYMRP_URL="http://localhost:5000", TINYMRP_DEV="1")
    served = {}
    monkeypatch.setattr(run.app, "run", lambda **kwargs: served.update(kwargs))

    assert run.main() == 0
    assert served == {
        "host": "127.0.0.1",
        "port": 5000,
        "debug": True,
        "threaded": True,
        "use_reloader": True,
    }


def test_an_undeclared_address_warns_about_the_login_loop(run_module, monkeypatch, capsys):
    """The failure it predicts has no error message of its own."""
    run = run_module()
    monkeypatch.setattr(run.app, "run", lambda **kwargs: None)
    monkeypatch.setenv("TINYMRP_SERVER", "flask")

    run.main()

    message = capsys.readouterr().err
    assert "TINYMRP_URL is not set" in message
    assert "Secure" in message

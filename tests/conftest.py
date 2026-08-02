import uuid
import mongomock
import pytest
from mongoengine import connect, disconnect

import app as app_module
from app.models.auth import User


@pytest.fixture(autouse=True)
def _mongo_test_db(monkeypatch):
    # The general regression suite exercises the explicitly supported local
    # development compatibility profile. Strict-mode behavior has its own app
    # fixtures and integration coverage.
    monkeypatch.setenv("TINYMRP_SECURITY_MODE", "compat")
    disconnect(alias="tinymrp-v2")
    connect(
        alias="tinymrp-v2",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
    )
    yield
    disconnect(alias="tinymrp-v2")


@pytest.fixture
def app():
    app_module.init_mongo = lambda _app: None
    app = app_module.create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user():
    user = User(
        email="user@example.com",
        password="test",
        active=True,
        fs_uniquifier=str(uuid.uuid4()),
    )
    user.save()
    return user

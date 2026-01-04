import mongomock
import pytest
from mongoengine import connect, disconnect


@pytest.fixture(autouse=True)
def _mongo_test_db():
    disconnect(alias="tinymrp-v2")
    connect(
        alias="tinymrp-v2",
        host="mongodb://localhost",
        mongo_client_class=mongomock.MongoClient,
    )
    yield
    disconnect(alias="tinymrp-v2")

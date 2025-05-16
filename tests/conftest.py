import os
import pytest
from src.app import create_app


@pytest.fixture
def app(monkeypatch):
    # force these so login & sync auth pass
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASS", "secret")
    monkeypatch.setenv("CRON_SECRET_KEY", "test-cron-key")
    monkeypatch.setenv("SECRET_KEY", "test-secret")  # for JWT

    test_config = {
        "TESTING": True,
        "DATABASE_URL": "sqlite:///:memory:",
        # we no longer need to set ADMIN_USER etc here
    }
    app = create_app(test_config)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()

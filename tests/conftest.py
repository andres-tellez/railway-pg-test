# tests/conftest.py

import os
import pytest
from src.app import create_app


@pytest.fixture
def app(monkeypatch):
    # Ensure all ENV VARS are in os.environ for both config *and* get_conn()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASS", "secret")
    monkeypatch.setenv("CRON_SECRET_KEY", "test-cron-key")
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    test_config = {
        "TESTING": True,
        # DATABASE_URL isn’t strictly needed here now, but harmless:
        "DATABASE_URL": "sqlite:///:memory:",
    }
    app = create_app(test_config)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()

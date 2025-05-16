# tests/conftest.py

import os
import pytest
from src.app import create_app


@pytest.fixture
def app(monkeypatch):
    # Ensure environment variables are available to both Flask and src.db
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASS", "secret")
    monkeypatch.setenv("CRON_SECRET_KEY", "test-cron-key")
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    test_config = {
        "TESTING": True,
        "DATABASE_URL": "sqlite:///:memory:",
    }
    app = create_app(test_config)

    # Bootstrap the schema in the in-memory SQLite database
    from src.db import init_db

    init_db(app.config["DATABASE_URL"])

    yield app


@pytest.fixture
def client(app):
    return app.test_client()

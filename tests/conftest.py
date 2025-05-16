# tests/conftest.py
import pytest
import os
from src.app import create_app


@pytest.fixture
def app():
    test_config = {
        "TESTING": True,
        "DATABASE_URL": "sqlite:///:memory:",
        "CRON_SECRET_KEY": "test-cron-key",
        "ADMIN_USER": "admin",
        "ADMIN_PASS": "secret",
        "SECRET_KEY": "test-secret",
    }
    app = create_app(test_config)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()

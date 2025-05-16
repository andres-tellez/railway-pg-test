# tests/conftest.py

import os
import pytest
from pathlib import Path
from src.app import create_app
from src.services.db_bootstrap import init_db  # ✅ NEW location


@pytest.fixture
def app(tmp_path, monkeypatch):
    # Use a file-based SQLite DB so schema persists across connections
    db_file = tmp_path / "test.db"
    db_url = f"sqlite:///{db_file}"

    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASS", "secret")
    monkeypatch.setenv("CRON_SECRET_KEY", "test-cron-key")
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    test_config = {
        "TESTING": True,
        "DATABASE_URL": db_url,
    }
    app = create_app(test_config)

    # ✅ Re-initialize schema
    init_db(app.config["DATABASE_URL"])

    yield app


@pytest.fixture
def client(app):
    return app.test_client()

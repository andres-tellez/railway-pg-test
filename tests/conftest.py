# tests/conftest.py

import os
import sys
import pytest
from pathlib import Path
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from unittest.mock import patch

# ✅ Load environment variables
load_dotenv()

# ✅ Ensure project root is on sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.app import create_app
from src.db.db_session import get_engine
from src.scripts.dev_only_init_db import init_db

# ✅ DATABASE_URL for test Postgres instance
TEST_DATABASE_URL = "postgresql+psycopg2://smartcoach:devpass@localhost:15432/smartcoach"

# ✅ Create shared test database engine
@pytest.fixture(scope="session")
def shared_engine():
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    engine = get_engine(TEST_DATABASE_URL)
    init_db(TEST_DATABASE_URL)
    return engine

# ✅ Standard app fixture (no mocking)
@pytest.fixture(scope="function")
def app(shared_engine):
    app = create_app({"TESTING": True, "DATABASE_URL": TEST_DATABASE_URL})
    yield app

# ✅ Standard client fixture
@pytest.fixture(scope="function")
def client(app):
    return app.test_client()

# ✅ SQLAlchemy session fixture
@pytest.fixture(scope="function")
def sqlalchemy_session(shared_engine):
    connection = shared_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, future=True)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

# ✅ Patched app fixture for mocking sync_recent
@pytest.fixture(scope="function")
def patched_app(monkeypatch):
    monkeypatch.setenv("CRON_SECRET_KEY", "devkey123")

    with patch("src.routes.sync_routes.sync_recent") as mock_sync_recent:
        mock_sync_recent.return_value = 10

        app = create_app({"TESTING": True, "DATABASE_URL": TEST_DATABASE_URL})
        yield app

# ✅ Patched client fixture built on patched app
@pytest.fixture(scope="function")
def patched_client(patched_app):
    return patched_app.test_client()

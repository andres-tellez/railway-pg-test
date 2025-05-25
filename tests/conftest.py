# tests/conftest.py

import os
import sys
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ✅ Add project root to Python path so 'src' can be imported
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.app import create_app
from src.db.init_db import init_db

# 🧪 DAO Tests: in-memory SQLite for fast isolation
@pytest.fixture(scope="session")
def sqlalchemy_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    return engine

@pytest.fixture(scope="function")
def sqlalchemy_session(sqlalchemy_engine):
    connection = sqlalchemy_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

# ✅ App for route tests (tasktracker, auth, sync, etc)
@pytest.fixture(scope="function")
def app(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    app = create_app({"TESTING": True})
    with app.app_context():
        init_db()
    yield app

@pytest.fixture(scope="function")
def client(app):
    return app.test_client()

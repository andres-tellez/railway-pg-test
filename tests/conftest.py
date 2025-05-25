import os
import sys
import tempfile
import pytest
from pathlib import Path

# ✅ Add project root to Python path so 'src' can be imported
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.app import create_app
from src.db.init_db import init_db


@pytest.fixture(scope="function")
def db_path():
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(db_fd)
    yield db_path
    os.remove(db_path)

@pytest.fixture(scope="function")
def app(db_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    app = create_app({"TESTING": True})
    with app.app_context():
        init_db()
    yield app

@pytest.fixture(scope="function")
def client(app):
    return app.test_client()

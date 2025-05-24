import os
import tempfile
import pytest

from src.app import create_app
from src.db.init_db import init_db


@pytest.fixture(scope="function")
def db_path():
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(db_fd)
    yield db_path
    os.remove(db_path)

@pytest.fixture(scope="function")  # <-- make sure this is function-scoped
def app(db_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    app = create_app({"TESTING": True})
    with app.app_context():
        init_db()
    yield app

@pytest.fixture(scope="function")  # <-- this too
def client(app):
    return app.test_client()

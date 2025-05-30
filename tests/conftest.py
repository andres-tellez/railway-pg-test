# tests/conftest.py

import os
import sys
import pytest
from pathlib import Path
from sqlalchemy.orm import sessionmaker

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.app import create_app
from src.core import get_engine, set_engine_for_testing
from src.db.init_db import init_db

# DATABASE_URL for test Postgres instance
TEST_DATABASE_URL = "postgresql+psycopg2://smartcoach:devpass@localhost:15432/smartcoach"

@pytest.fixture(scope="session")
def shared_engine():
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    engine = get_engine(TEST_DATABASE_URL)
    set_engine_for_testing(engine)
    init_db(TEST_DATABASE_URL)
    return engine

@pytest.fixture(scope="function")
def app(shared_engine):
    app = create_app({"TESTING": True, "DATABASE_URL": TEST_DATABASE_URL})
    yield app

@pytest.fixture(scope="function")
def client(app):
    return app.test_client()

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

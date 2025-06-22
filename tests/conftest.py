# tests/conftest.py

import os
import sys
import pytest
from pathlib import Path
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from unittest.mock import patch
from datetime import datetime, timedelta

# Load test environment variables
load_dotenv(dotenv_path=".env.test", override=True)

# Ensure project root is on sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.app import create_app
from src.db.db_session import get_engine
from src.db.models.tokens import Token
from src.db.models.athletes import Athlete
from src.db.models.activities import Activity
from tests.test_data.sample_activities import SAMPLE_ACTIVITY_JSON


@pytest.fixture(scope="session")
def shared_engine():
    """Shared DB engine for the test session."""
    database_url = os.getenv("DATABASE_URL")
    print(f"DEBUG: Using DATABASE_URL = {database_url}")
    engine = get_engine(database_url)
    return engine


@pytest.fixture(scope="function")
def app(shared_engine):
    """Flask app fixture with test config."""
    database_url = os.getenv("DATABASE_URL")
    app = create_app({"TESTING": True, "DATABASE_URL": database_url})
    yield app


@pytest.fixture(scope="function")
def client(app):
    """HTTP client for app."""
    return app.test_client()


@pytest.fixture(scope="function")
def sqlalchemy_session(shared_engine):
    """Provides isolated SQLAlchemy session with transaction rollback."""
    connection = shared_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection, future=True)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def test_db_session(sqlalchemy_session):
    """Alias for SQLAlchemy session used in most tests."""
    return sqlalchemy_session


@pytest.fixture(scope="function")
def seed_test_data(test_db_session):
    """Seeds athlete, token, and sample activity into DB."""
    athlete = test_db_session.query(Athlete).filter_by(athlete_id=1).first()
    if not athlete:
        athlete = Athlete(athlete_id=1, first_name="Test", last_name="Athlete")
        test_db_session.add(athlete)

    token = test_db_session.query(Token).filter_by(athlete_id=1).first()
    if not token:
        token = Token(
            athlete_id=1,
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            expires_at=int((datetime.utcnow() + timedelta(days=1)).timestamp())
        )
        test_db_session.add(token)

    activity = test_db_session.query(Activity).filter_by(activity_id=SAMPLE_ACTIVITY_JSON["activity_id"]).first()
    if not activity:
        activity = Activity(
            activity_id=SAMPLE_ACTIVITY_JSON["activity_id"],
            athlete_id=1,
            name=SAMPLE_ACTIVITY_JSON["name"],
            type=SAMPLE_ACTIVITY_JSON["type"],
            distance=SAMPLE_ACTIVITY_JSON["distance"],
            moving_time=SAMPLE_ACTIVITY_JSON["moving_time"],
            elapsed_time=SAMPLE_ACTIVITY_JSON["elapsed_time"],
            total_elevation_gain=SAMPLE_ACTIVITY_JSON["total_elevation_gain"],
            average_speed=SAMPLE_ACTIVITY_JSON["average_speed"],
            max_speed=SAMPLE_ACTIVITY_JSON["max_speed"],
            suffer_score=SAMPLE_ACTIVITY_JSON["suffer_score"],
            average_heartrate=SAMPLE_ACTIVITY_JSON["average_heartrate"],
            max_heartrate=SAMPLE_ACTIVITY_JSON["max_heartrate"],
            calories=SAMPLE_ACTIVITY_JSON["calories"],
        )
        test_db_session.add(activity)

    test_db_session.commit()


@pytest.fixture(scope="function")
def patched_app(monkeypatch):
    """Patched app with env var override and sync route mock."""
    monkeypatch.setenv("CRON_SECRET_KEY", "devkey123")

    with patch("src.routes.sync_routes.sync_recent") as mock_sync_recent:
        mock_sync_recent.return_value = 10
        database_url = os.getenv("DATABASE_URL")
        app = create_app({"TESTING": True, "DATABASE_URL": database_url})
        yield app


@pytest.fixture(scope="function")
def patched_client(patched_app):
    """Patched client for routes tests."""
    return patched_app.test_client()


# 🔧 New: Patch token DAO and service layer for mocking token flow
@pytest.fixture(scope="function")
def patched_token_mocks():
    """Mocks token retrieval logic in tests."""
    with patch("src.services.token_service.get_valid_token") as mock_valid, \
         patch("src.db.dao.token_dao.get_tokens_sa") as mock_tokens:

        mock_tokens.return_value = [
            Token(
                athlete_id=1,
                access_token="mock_access_token",
                refresh_token="mock_refresh_token",
                expires_at=int((datetime.utcnow() + timedelta(hours=1)).timestamp())
            )
        ]
        mock_valid.return_value = "mock_access_token"

        yield mock_tokens, mock_valid

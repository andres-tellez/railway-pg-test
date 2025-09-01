# tests/conftest.py
import os
import sys
import pytest
from pathlib import Path
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from unittest.mock import patch
from datetime import datetime, timedelta

# -------------------------
# 🔧 Environment & Path Setup
# -------------------------

# Add project root to PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Load test-specific environment variables
load_dotenv(dotenv_path=PROJECT_ROOT / ".env.local", override=True)

# -------------------------
# 🔌 Flask App Fixtures
# -------------------------

from src.app import create_app
from src.db.db_session import get_engine
from src.db.models.tokens import Token
from src.db.models.athletes import Athlete
from src.db.models.activities import Activity
from tests.test_data.sample_activities import SAMPLE_ACTIVITY_JSON


@pytest.fixture(scope="session")
def shared_engine():
    database_url = os.getenv("DATABASE_URL")
    print(f"[TEST] Using DATABASE_URL = {database_url}")
    return get_engine(database_url)


@pytest.fixture(scope="function")
def app(shared_engine):
    test_config = {"TESTING": True, "DATABASE_URL": os.getenv("DATABASE_URL")}
    yield create_app(test_config)


@pytest.fixture(scope="function")
def client(app):
    return app.test_client()


# -------------------------
# 🧪 Database Fixtures
# -------------------------


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


@pytest.fixture(scope="function")
def test_db_session(sqlalchemy_session):
    return sqlalchemy_session


@pytest.fixture(scope="function")
def seed_test_data(test_db_session):
    """Seed athletes, tokens, and activities with safe defaults."""
    if not test_db_session.query(Athlete).filter_by(athlete_id=1).first():
        test_db_session.add(
            Athlete(athlete_id=1, first_name="Test", last_name="Athlete")
        )

    if not test_db_session.query(Token).filter_by(athlete_id=1).first():
        test_db_session.add(
            Token(
                athlete_id=1,
                access_token="test_access_token",
                refresh_token="test_refresh_token",
                expires_at=int((datetime.utcnow() + timedelta(days=1)).timestamp()),
            )
        )

    if (
        not test_db_session.query(Activity)
        .filter_by(activity_id=SAMPLE_ACTIVITY_JSON["activity_id"])
        .first()
    ):
        test_db_session.add(
            Activity(
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
        )

    test_db_session.commit()


# -------------------------
# 🔁 Patched App Fixtures
# -------------------------


@pytest.fixture(scope="function")
def patched_app(monkeypatch):
    monkeypatch.setenv("CRON_SECRET_KEY", "devkey123")

    with patch("src.routes.sync_routes.sync_recent") as mock_sync_recent:
        mock_sync_recent.return_value = 10
        app = create_app({"TESTING": True, "DATABASE_URL": os.getenv("DATABASE_URL")})
        yield app


@pytest.fixture(scope="function")
def patched_client(patched_app):
    return patched_app.test_client()


# -------------------------
# 🔐 Auth0 Token Mocking
# -------------------------


@pytest.fixture(autouse=True)
def mock_verify_and_decode(monkeypatch):
    """
    Automatically mock Auth0 JWT verification for all tests.
    Prevents hitting Auth0 JWKS and ensures deterministic claims.
    """

    def fake_verify_and_decode(token: str):
        return {"sub": "auth0|test-user", "email": "test@example.com"}

    monkeypatch.setattr("src.utils.auth0_jwt.verify_and_decode", fake_verify_and_decode)
    yield


@pytest.fixture(scope="function")
def auth_header():
    """
    Helper: generate headers for test users.
    """

    def _h(sub: str = "auth0|test-user", *, unauthorized: bool = False):
        if unauthorized:
            return {"Authorization": "Bearer invalid"}
        return {"Authorization": f"Bearer fake-token-for-{sub}"}

    return _h


# -------------------------
# 🧹 Table Cleanup Between Tests
# -------------------------

from sqlalchemy import text


@pytest.fixture(scope="function", autouse=True)
def clean_user_profile(shared_engine):
    yield
    with shared_engine.connect() as conn:
        conn.execute(text("DELETE FROM user_profile WHERE user_id LIKE 'auth0|%'"))
        conn.commit()


@pytest.fixture(scope="function", autouse=True)
def clean_user_athletes(shared_engine):
    yield
    with shared_engine.connect() as conn:
        conn.execute(text("DELETE FROM user_athletes WHERE user_id LIKE 'auth0|%'"))
        conn.commit()


# -------------------------
# 🏃 DAO Helpers
# -------------------------


@pytest.fixture(scope="function")
def make_athlete(shared_engine):
    """
    Factory to insert a new athlete row.
    Handles both old and new schema (athlete_id vs strava_athlete_id).
    """
    Session = sessionmaker(bind=shared_engine, future=True)

    def _create(**overrides):
        from time import time

        with Session() as s:
            if hasattr(Athlete, "strava_athlete_id"):
                a = Athlete(
                    strava_athlete_id=overrides.get(
                        "strava_athlete_id", int(time() * 1_000_000)
                    )
                )
            else:
                a = Athlete(
                    athlete_id=overrides.get("athlete_id", int(time() * 1_000_000)),
                    first_name=overrides.get("first_name", "Test"),
                    last_name=overrides.get("last_name", "Athlete"),
                )
            s.add(a)
            s.commit()
            s.refresh(a)
            return a

    return _create


@pytest.fixture(scope="function")
def link_user():
    from src.db.dao.user_athletes_dao import create_link

    def _link(user_id: str, athlete_id: int):
        return create_link(user_id, athlete_id)

    return _link

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
# 🔐 Token Mock Fixtures
# -------------------------


@pytest.fixture(scope="function")
def patched_token_mocks():
    with patch("src.services.token_service.get_valid_token") as mock_valid, patch(
        "src.db.dao.token_dao.get_tokens_sa"
    ) as mock_tokens:

        mock_tokens.return_value = [
            Token(
                athlete_id=1,
                access_token="mock_access_token",
                refresh_token="mock_refresh_token",
                expires_at=int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            )
        ]
        mock_valid.return_value = "mock_access_token"

        yield mock_tokens, mock_valid


from sqlalchemy import text


@pytest.fixture(scope="function", autouse=True)
def clean_user_profile(shared_engine):
    """
    Clean up user_profile table after onboarding tests to ensure test isolation.
    Only applies to test cases using 'test-user-123'.
    """
    yield
    with shared_engine.connect() as conn:
        conn.execute(text("DELETE FROM user_profile WHERE user_id = 'test-user-123'"))
        conn.commit()


# =====================================================================
# 🆕 Added fixtures for user_athletes tests (non-destructive additions)
# =====================================================================

from functools import wraps
from flask import g, request, jsonify


@pytest.fixture(scope="function")
def auth_header():
    """
    Helper to pass a deterministic test user into routes via header.
    Pairs with patched requires_auth below.
    """

    def _h(sub: str, *, unauthorized: bool = False):
        h = {"X-TEST-USER": sub}
        if unauthorized:
            h["X-TEST-UNAUTH"] = "1"
        return h

    return _h


@pytest.fixture(scope="function", autouse=True)
def patch_requires_auth(monkeypatch):
    """
    Patch src.utils.auth0_jwt.requires_auth so route tests can:
      - set g.current_user['sub'] from X-TEST-USER header
      - optionally force a 401 by sending X-TEST-UNAUTH: 1
    This does NOT modify your production code and only applies in tests.
    """
    import src.utils.auth0_jwt as auth0_jwt

    def test_requires_auth(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if request.headers.get("X-TEST-UNAUTH") == "1":
                return jsonify({"error": "Unauthorized"}), 401
            sub = request.headers.get("X-TEST-USER", "auth0|test-user")
            g.current_user = {"sub": sub}
            return fn(*args, **kwargs)

        return wrapper

    monkeypatch.setattr(auth0_jwt, "requires_auth", lambda f: test_requires_auth(f))
    yield
    # No unpatch needed; monkeypatch fixture handles teardown


@pytest.fixture(scope="function")
def make_athlete(shared_engine):
    """
    Factory to create an Athlete row compatible with either schema variant:
      - Newer: Athlete(id PK, strava_athlete_id BIGINT, created_at ...)
      - Older: Athlete(athlete_id PK or column, first_name, last_name, ...)
    Returns the ORM object with a usable primary key (a.id).
    """
    Session = sessionmaker(bind=shared_engine, future=True)

    def _create(**overrides):
        from time import time

        with Session() as s:
            a = None
            # Try to handle both schemas gracefully
            if hasattr(Athlete, "strava_athlete_id"):
                # Newer schema
                defaults = {
                    "strava_athlete_id": overrides.pop(
                        "strava_athlete_id", int(time() * 1_000_000)
                    ),
                }
                a = Athlete(**{**defaults, **overrides})
            else:
                # Older schema fallback
                defaults = {
                    "athlete_id": overrides.pop("athlete_id", int(time() * 1_000_000)),
                    "first_name": overrides.pop("first_name", "Test"),
                    "last_name": overrides.pop("last_name", "Athlete"),
                }
                a = Athlete(**{**defaults, **overrides})

            s.add(a)
            s.commit()
            s.refresh(a)
            return a

    return _create


@pytest.fixture(scope="function")
def link_user():
    """
    Helper to create a user↔athlete link via DAO (uses production code path).
    """
    from src.db.dao.user_athletes_dao import create_link

    def _link(user_id: str, athlete_id: int):
        return create_link(user_id, athlete_id)

    return _link


@pytest.fixture(scope="function", autouse=True)
def clean_user_athletes(shared_engine):
    """
    Keep user_athletes clean between tests. Only deletes rows created by tests
    for Auth0-like subjects to avoid interfering with other data.
    """
    yield
    with shared_engine.connect() as conn:
        # Delete typical test subjects
        conn.execute(text("DELETE FROM user_athletes WHERE user_id LIKE 'auth0|%'"))
        conn.execute(text("DELETE FROM user_athletes WHERE user_id = 'test-user-123'"))
        conn.commit()

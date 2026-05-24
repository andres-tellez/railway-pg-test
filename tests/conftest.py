# tests/conftest.py
import os
import sys
import pytest
import uuid
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, clear_mappers


# -------------------------
# 🔧 Environment & Path Setup
# -------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(dotenv_path=PROJECT_ROOT / ".env.local", override=True)


# -------------------------
# 🛠️ Import project modules AFTER sys.path is fixed
# -------------------------

from src.db import db_session


@pytest.fixture(scope="session", autouse=True)
def use_sqlite_for_tests():
    """Force all DB sessions to use in-memory SQLite for tests."""
    from src.db import db_session

    # 🚨 Import all models so Base.metadata sees them
    import src.db.models.user_identity
    import src.db.models.tokens
    import src.db.models.activities
    import src.db.models.user_profile
    import src.db.models.user_athletes
    import src.db.models.plans  # Import plans model for tests
    import src.db.models.plan_workouts  # Import plan_workouts model for tests
    import src.db.models.strava_ingestion_retry  # Retry queue for Strava ingestion
    import src.db.models.user_phase_goals  # Phase D 3D.1 — phase goal/focus rows
    import src.db.models.memory.session_summaries  # Phase F — session summaries
    import src.db.models.memory.user_plan_memories  # Phase F — plan memories
    import src.db.models.memory.user_state_observations  # Memory V2
    import src.db.models.memory.user_open_threads  # Memory V2
    import src.db.models.memory.coach_interactions  # Memory V2
    import src.db.models.coach_tools  # coach_tools table for execute_tool call_count updates
    import src.db.models.product_analytics_event  # pilot product analytics
    import src.db.models.runner_zone_profiles  # Runner profile zones
    import src.db.models.weekly_training_insights  # mobile Insights precompute
    import src.db.models.strava_sync_status  # coach Strava readiness

    test_engine = create_engine("sqlite:///:memory:", future=True)

    from sqlalchemy import event

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")  # ⚠️ TEMPORARY to break FK loops
        cursor.close()

    db_session.engine = test_engine
    db_session.SessionLocal = sessionmaker(
        bind=test_engine, future=True, autoflush=False, autocommit=False
    )

    # Now Base has all models registered
    db_session.Base.metadata.create_all(bind=test_engine)

    yield

    db_session.Base.metadata.drop_all(bind=test_engine)


# -------------------------
# 🔌 Flask App Fixtures
# -------------------------

from src.app import create_app
from src.db.models.tokens import Token
from src.db.models.activities import Activity
from src.db.models.user_identity import UserIdentity
from tests.test_data.sample_activities import SAMPLE_ACTIVITY_JSON


@pytest.fixture(scope="function")
def app():
    """Flask app for tests"""
    test_config = {"TESTING": True, "DATABASE_URL": os.getenv("DATABASE_URL")}
    app = create_app(test_config)
    app.config["PROPAGATE_EXCEPTIONS"] = True  # ✅ show tracebacks instead of 500
    yield app


@pytest.fixture(scope="function")
def client(app):
    """Flask test client"""
    return app.test_client()


# -------------------------
# 🧪 Database Fixtures
# -------------------------


@pytest.fixture(scope="function")
def test_db_session():
    """Provide a database session wrapped in a rollback transaction."""
    connection = db_session.engine.connect()
    transaction = connection.begin()
    SessionTesting = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = SessionTesting()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def _clear_module_level_caches():
    """
    Reset module-level caches that otherwise leak between tests (e.g.
    ``user_context_cache`` populated by ``tool_get_user_context`` in
    one test confusing assertions in the next). Add new caches here as
    they're introduced.
    """
    try:
        from src.smartcoach_mobile_coach import user_context_cache

        user_context_cache.clear_all()
    except Exception:
        pass
    try:
        from src.smartcoach_mobile_coach import plan_cache

        plan_cache.clear_all()
    except Exception:
        pass
    yield


@pytest.fixture(scope="function")
def seed_test_data(test_db_session):
    """Seed tokens and activities with safe defaults."""

    if not test_db_session.query(Token).filter_by(athlete_id=1).first():
        tok = Token(
            athlete_id=1,
            expires_at=int((datetime.utcnow() + timedelta(days=1)).timestamp()),
        )
        tok.access_token = "test_access_token"
        tok.refresh_token = "test_refresh_token"
        test_db_session.add(tok)

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
# 👤 Default User Fixture (autouse)
# -------------------------

from src.db.models.user_identity import (
    UserIdentity,
)  # ✅ Ensure this is at the top if not already

import uuid
import pytest


@pytest.fixture(scope="function", autouse=True)
def seed_default_user(test_db_session):
    """Ensure a default UserIdentity exists for tests."""

    default_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # ✅ wrap with text()
    from sqlalchemy import or_

    test_db_session.query(UserIdentity).filter(
        or_(
            UserIdentity.user_id == uuid.UUID("00000000-0000-0000-0000-000000000001"),
            UserIdentity.user_id == 1,  # For SQLite, fallback
        )
    ).delete(synchronize_session=False)
    test_db_session.commit()

    test_db_session.add(
        UserIdentity(
            user_id=default_user_id,
            email="default@example.com",
            email_verified=True,
            name="Default Test User",
            picture=None,
        )
    )
    test_db_session.commit()

    yield


# -------------------------
# 🔐 Auth0 Token Mocking
# -------------------------


@pytest.fixture(autouse=True)
def mock_verify_and_decode(monkeypatch):
    """Automatically mock Auth0 JWT verification for all tests."""

    def fake_verify_and_decode(token: str):
        return {"sub": "auth0|test-user", "email": "test@example.com"}

    monkeypatch.setattr("src.utils.auth0_jwt.verify_and_decode", fake_verify_and_decode)
    yield


@pytest.fixture(scope="function")
def auth_header():
    """Helper: generate headers for test users."""

    def _h(sub: str = "auth0|test-user", *, unauthorized: bool = False):
        if unauthorized:
            return {"Authorization": "Bearer invalid"}
        return {"Authorization": f"Bearer fake-token-for-{sub}"}

    return _h


# -------------------------
# 🧹 Table Cleanup Between Tests
# -------------------------

from sqlalchemy import inspect, text


@pytest.fixture(scope="function", autouse=True)
def clean_user_profile(test_db_session):
    yield
    inspector = inspect(test_db_session.bind)
    if "user_profile" in inspector.get_table_names():
        test_db_session.execute(
            text("DELETE FROM user_profile WHERE user_id LIKE 'auth0|%'")
        )
        test_db_session.commit()


@pytest.fixture(scope="function", autouse=True)
def clean_user_athletes(test_db_session):
    yield
    inspector = inspect(test_db_session.bind)
    if "user_athletes" in inspector.get_table_names():
        test_db_session.execute(
            text("DELETE FROM user_athletes WHERE user_id LIKE 'auth0|%'")
        )
        test_db_session.commit()


# -------------------------
# 🏗️ Create & Drop Tables
# -------------------------

from sqlalchemy.schema import DropTable
from sqlalchemy.ext.compiler import compiles


@compiles(DropTable, "postgresql")
def _compile_drop_table(element, compiler, **kwargs):
    """Force CASCADE on drop_all()"""
    return compiler.visit_drop_table(element) + " CASCADE"


@pytest.fixture(autouse=True)
def patch_get_session(monkeypatch, test_db_session):
    """
    Ensure routes use the same test_db_session instead of creating a new one.
    Prevents session mismatches & hanging commits.
    """
    monkeypatch.setattr("src.db.db_session.get_session", lambda: test_db_session)

    yield

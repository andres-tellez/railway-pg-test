# tests/test_integration_ingestion.py

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import ingest_specific_activity
from src.db.models.activities import Activity
from src.db.models.tokens import Token

@pytest.fixture(scope="module")
def test_session():
    session = get_session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture(scope="function")
def token_fixture(test_session):
    token = Token(
        athlete_id=1,
        access_token="test_token",
        refresh_token="test_refresh",
        expires_at=int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
    )
    test_session.add(token)
    test_session.commit()
    yield token
    test_session.delete(token)
    test_session.commit()

@patch("src.services.strava_access_service.StravaClient._request_with_backoff")
def test_ingest_specific_activity_integration(mock_strava_call, test_session, token_fixture):
    athlete_id = 1
    activity_id = 123456

    mock_strava_call.return_value = {
        "id": activity_id,
        "name": "Mocked Run",
        "distance": 5000,
        "moving_time": 1800,
        "elapsed_time": 1900,
        "total_elevation_gain": 100,
        "type": "Run",
        "average_speed": 2.8,
        "max_speed": 3.5,
        "suffer_score": 30,
        "average_heartrate": 145,
        "max_heartrate": 160,
        "calories": 300,
        "start_date": "2025-06-01T08:00:00Z"
    }

    result = ingest_specific_activity(test_session, athlete_id, activity_id)

    assert result == 1
    activity = test_session.query(Activity).filter(Activity.activity_id == activity_id).first()
    assert activity is not None
    assert activity.activity_id == activity_id

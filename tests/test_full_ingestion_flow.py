import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

from src.db.db_session import get_session
from src.db.models.tokens import Token
from src.db.models.activities import Activity
from src.db.models.splits import Split
from src.scripts.main_pipeline import run_full_ingestion_and_enrichment

# Import the sample activity JSON with external_id included
from tests.test_data.sample_activities import SAMPLE_ACTIVITY_JSON

@pytest.fixture(scope="module")
def test_session():
    session = get_session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture(scope="function")
def seeded_token(test_session):
    token = Token(
        athlete_id=1,
        access_token="mock_access",
        refresh_token="mock_refresh",
        expires_at=int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    )
    test_session.add(token)
    test_session.commit()
    yield token
    test_session.delete(token)
    test_session.commit()

@patch("src.services.strava_access_service.StravaClient.get_streams")
@patch("src.services.strava_access_service.StravaClient.get_activity")
@patch("src.services.strava_access_service.StravaClient.get_activities")
@patch("src.services.strava_access_service.StravaClient.get_splits")
@patch("src.services.strava_access_service.StravaClient.get_hr_zones")
def test_run_full_ingestion_flow(
    mock_zones, mock_splits, mock_activities, mock_activity, mock_streams,
    test_session, seeded_token
):
    athlete_id = 1
    mock_activity_id = SAMPLE_ACTIVITY_JSON["id"]

    # Ensure no conflicting data
    test_session.query(Split).filter_by(activity_id=mock_activity_id).delete()
    test_session.query(Activity).filter_by(activity_id=mock_activity_id).delete()
    test_session.commit()

    # Use SAMPLE_ACTIVITY_JSON and ensure it has external_id
    mock_activity_data = SAMPLE_ACTIVITY_JSON.copy()
    mock_activity_data["external_id"] = f"external_{mock_activity_id}"  # Ensure external_id exists

    mock_activities.return_value = [mock_activity_data]
    mock_activity.return_value = mock_activity_data

    mock_splits.return_value = [
        {"elapsed_time": 600, "distance": 1609, "average_speed": 3.3, "split": 1},
        {"elapsed_time": 620, "distance": 1609, "average_speed": 3.2, "split": 2}
    ]

    mock_zones.return_value = [{
        "type": "heartrate",
        "distribution_buckets": [
            {"time": 300}, {"time": 300}, {"time": 200}, {"time": 100}, {"time": 100}
        ]
    }]

    mock_streams.return_value = {
        "distance": [1609.344, 3219],  # Slightly more than 2 * 1609.344
        "time": [600, 1220],
        "velocity_smooth": [3.3, 3.2],
        "heartrate": [140, 145]
    }

    result = run_full_ingestion_and_enrichment(test_session, athlete_id)

    assert result["synced"] >= 1, "Expected at least one activity to be inserted"

    activity = test_session.query(Activity).filter_by(activity_id=mock_activity_id).first()
    assert activity is not None, "Activity not found in DB"
    assert activity.name == mock_activity_data["name"]
    assert activity.start_date.isoformat().startswith("2025-06-01")
    assert activity.distance == mock_activity_data["distance"]

    splits = test_session.query(Split).filter_by(activity_id=mock_activity_id).all()
    assert len(splits) == 2, "Expected 2 splits to be inserted"

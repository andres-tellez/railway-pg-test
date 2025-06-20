# tests/test_enrichment_with_splits.py

import pytest
from unittest.mock import patch
from datetime import datetime

from src.db.models.activities import Activity
from src.db.models.splits import Split
from src.services.activity_service import enrich_one_activity_with_refresh
from tests.test_data.sample_activities import (
    SAMPLE_ACTIVITY_JSON,
    SAMPLE_HR_ZONE_RESPONSE,
    SAMPLE_STREAMS_RESPONSE,  # Optional; not used directly
)

@pytest.fixture
def seed_activity(sqlalchemy_session):
    athlete_id = 42
    activity = Activity(
        activity_id=99999,
        athlete_id=athlete_id,
        start_date=datetime.utcnow()
    )
    sqlalchemy_session.add(activity)
    sqlalchemy_session.commit()
    return activity

@patch("src.services.activity_service.get_valid_token", return_value="dummy_access")
@patch("src.services.strava_access_service.StravaClient.get_activity")
@patch("src.services.strava_access_service.StravaClient.get_hr_zones")
@patch("src.services.strava_access_service.StravaClient.get_streams")
def test_enrich_one_activity_with_splits(
    mock_get_streams,
    mock_get_hr_zones,
    mock_get_activity,
    mock_get_token,
    sqlalchemy_session,
    seed_activity
):
    # ✅ Patch mock responses
    mock_get_activity.return_value = SAMPLE_ACTIVITY_JSON
    mock_get_hr_zones.return_value = SAMPLE_HR_ZONE_RESPONSE

    # ✅ Use proper structure (flat lists) for stream data
    patched_streams = {
        "distance": [0.0, 1000.0],
        "time": [0, 300],
        "velocity_smooth": [3.2, 3.3],
        "heartrate": [140, 145]
    }
    mock_get_streams.return_value = patched_streams

    athlete_id = seed_activity.athlete_id
    result = enrich_one_activity_with_refresh(sqlalchemy_session, athlete_id, activity_id=99999)
    assert result is True

    # ✅ Verify splits inserted correctly
    splits = sqlalchemy_session.query(Split).filter_by(activity_id=99999).all()
    assert len(splits) == 1
    assert splits[0].lap_index == 1
    assert splits[0].distance == 1000.0
    assert splits[0].elapsed_time == 300
    assert isinstance(splits[0].split, int)

    # ✅ Confirm enrichment saved to activity
    activity = sqlalchemy_session.query(Activity).filter_by(activity_id=99999).one()
    assert activity.hr_zone_1 is not None
    assert activity.hr_zone_5 is not None

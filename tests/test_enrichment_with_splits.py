# tests/test_enrichment_with_splits.py

import random
from datetime import datetime
from unittest.mock import patch

import pytest

from src.db.models.activities import Activity
from src.db.models.splits import Split
from src.services.activity_service import enrich_one_activity_with_refresh
from tests.test_data.sample_activities import SAMPLE_ACTIVITY_JSON

SAMPLE_HR_ZONE_RESPONSE = {
    "type": "heartrate",
    "distribution_buckets": [
        {"time": 300},
        {"time": 300},
        {"time": 200},
        {"time": 100},
        {"time": 100},
    ],
}


@pytest.fixture
def seed_activity(test_db_session):
    activity_id = random.randint(100000, 999999)
    activity = Activity(
        activity_id=activity_id, athlete_id=42, start_date=datetime.utcnow()
    )
    test_db_session.add(activity)
    test_db_session.commit()
    return activity


@patch("src.services.activity_service.get_valid_token")
@patch("src.services.strava_access_service.StravaClient.get_activity")
@patch("src.services.strava_access_service.StravaClient.get_hr_zones")
@patch("src.services.strava_access_service.StravaClient.get_streams")
@patch("src.services.strava_access_service.StravaClient.get_splits")
def test_enrich_one_activity_with_splits(
    mock_get_splits,
    mock_get_streams,
    mock_get_hr_zones,
    mock_get_activity,
    mock_get_token,
    test_db_session,
    seed_activity,
):
    mock_get_token.return_value = "mock_access"

    activity_payload = dict(SAMPLE_ACTIVITY_JSON)
    activity_payload["id"] = seed_activity.activity_id
    activity_payload.pop("splits_metric", None)
    activity_payload.pop("splits_standard", None)
    mock_get_activity.return_value = activity_payload

    mock_get_hr_zones.return_value = SAMPLE_HR_ZONE_RESPONSE
    mock_get_streams.return_value = {
        "distance": [0.0, 800.0, 1609.34, 1700.0],  # 1609.34 is exactly 1 mile
        "time": [0, 200, 400, 420],
        "velocity_smooth": [3.1, 3.3, 3.4, 3.2],
        "heartrate": [138, 140, 142, 144],
    }
    mock_get_splits.return_value = [
        {
            "elapsed_time": 300,
            "distance": 1700.0,
            "average_speed": 3.2,
            "split": 1,
            "lap_index": 1,
        }
    ]

    activity_id = seed_activity.activity_id

    result = enrich_one_activity_with_refresh(
        test_db_session, seed_activity.athlete_id, activity_id=activity_id
    )
    assert result is True

    splits = test_db_session.query(Split).filter_by(activity_id=activity_id).all()
    assert len(splits) == 1
    assert splits[0].lap_index == 1
    assert splits[0].distance == 1700.0
    assert splits[0].elapsed_time == 420
    assert isinstance(splits[0].split, int)

    activity = test_db_session.query(Activity).filter_by(activity_id=activity_id).one()
    assert activity.hr_zone_1 is not None
    assert activity.hr_zone_5 is not None

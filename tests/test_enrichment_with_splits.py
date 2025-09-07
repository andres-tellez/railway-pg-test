# tests/test_enrichment_with_splits.py

import pytest
from unittest.mock import patch
from datetime import datetime, timedelta
import random

from src.db.models.activities import Activity
from src.db.models.splits import Split
from src.db.models.tokens import Token
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
def sqlalchemy_token(sqlalchemy_session):
    token = Token(
        athlete_id=42,
        access_token="mock_access",
        refresh_token="mock_refresh",
        expires_at=int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
    )
    sqlalchemy_session.add(token)
    sqlalchemy_session.commit()
    return token


@pytest.fixture
def seed_activity(sqlalchemy_session):
    activity_id = random.randint(100000, 999999)
    activity = Activity(
        activity_id=activity_id, athlete_id=42, start_date=datetime.utcnow()
    )
    sqlalchemy_session.add(activity)
    sqlalchemy_session.commit()
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
    sqlalchemy_session,
    sqlalchemy_token,
    seed_activity,
):
    mock_get_token.return_value = sqlalchemy_token
    mock_get_activity.return_value = SAMPLE_ACTIVITY_JSON
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
        sqlalchemy_session, seed_activity.athlete_id, activity_id=activity_id
    )
    assert result is True

    splits = sqlalchemy_session.query(Split).filter_by(activity_id=activity_id).all()
    assert len(splits) == 1
    assert splits[0].lap_index == 1
    assert splits[0].distance == 1700.0
    assert splits[0].elapsed_time == 420
    assert isinstance(splits[0].split, int)

    activity = (
        sqlalchemy_session.query(Activity).filter_by(activity_id=activity_id).one()
    )
    assert activity.hr_zone_1 is not None
    assert activity.hr_zone_5 is not None

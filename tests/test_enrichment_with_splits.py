import pytest
from unittest.mock import patch
from datetime import datetime

from src.db.models.activities import Activity
from src.db.models.splits import Split
from src.services.activity_service import enrich_one_activity_with_refresh

# ✅ Sample activity data
SAMPLE_ACTIVITY_JSON = {
    "id": 99999,
    "name": "Mock Run",
    "type": "Run",
    "distance": 5000.0,
    "moving_time": 1500,
    "elapsed_time": 1600,
    "total_elevation_gain": 50.0,
    "average_speed": 3.5,
    "max_speed": 4.0,
    "suffer_score": 30,
    "average_heartrate": 150,
    "max_heartrate": 170,
    "calories": 400,
    "laps": [
        {
            "split_index": 1,
            "distance": 1000,
            "elapsed_time": 300,
            "moving_time": 295,
            "average_speed": 3.33,
            "max_speed": 3.5,
            "start_index": 0,
            "end_index": 299,
            "split": True
        }
    ]
}

SAMPLE_HR_ZONE_RESPONSE = [
    {
        "type": "heartrate",
        "distribution_buckets": [
            {"min": 90, "max": 110, "time": 60},
            {"min": 110, "max": 130, "time": 120},
            {"min": 130, "max": 150, "time": 180},
            {"min": 150, "max": 170, "time": 240},
            {"min": 170, "max": 190, "time": 300}
        ]
    }
]

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

# ✅ Patching based on how it's imported in `activity_service`
@patch("src.services.activity_service.get_valid_token", return_value="dummy_access")
@patch("src.services.strava_access_service.StravaClient.get_activity")
@patch("src.services.strava_access_service.StravaClient.get_hr_zones")
def test_enrich_one_activity_with_splits(mock_get_hr_zones, mock_get_activity, mock_get_token, sqlalchemy_session, seed_activity):
    mock_get_activity.return_value = SAMPLE_ACTIVITY_JSON
    mock_get_hr_zones.return_value = SAMPLE_HR_ZONE_RESPONSE

    athlete_id = seed_activity.athlete_id

    result = enrich_one_activity_with_refresh(sqlalchemy_session, athlete_id, activity_id=99999)
    assert result is True

    splits = sqlalchemy_session.query(Split).filter_by(activity_id=99999).all()
    assert len(splits) == 1
    assert splits[0].lap_index == 1
    assert splits[0].distance == 1000
    assert splits[0].elapsed_time == 300

    activity = sqlalchemy_session.query(Activity).filter_by(activity_id=99999).one()
    assert activity.hr_zone_1_pct is not None
    assert activity.hr_zone_5_pct is not None

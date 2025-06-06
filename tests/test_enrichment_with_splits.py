# tests/test_enrichment_with_splits.py

import pytest
from unittest.mock import patch, Mock
from datetime import datetime

from src.db.models.activities import Activity
from src.db.models.splits import Split
from src.db.dao.split_dao import upsert_splits
from src.services.enrichment_sync import enrich_one_activity

# Sample mock data for enrichment
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
    "splits_metric": [
        {
            "lap_index": 1,
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
    # Create parent activity row before enrichment (FK required)
    activity = Activity(
        activity_id=99999,
        athlete_id=42,
        start_date=datetime.utcnow()
    )
    sqlalchemy_session.add(activity)
    sqlalchemy_session.commit()
    return activity

@patch("src.services.enrichment_sync.requests.get")
def test_enrich_one_activity_with_splits(mock_requests_get, sqlalchemy_session, seed_activity):
    # Patch Strava activity fetch
    def side_effect(url, headers, timeout):
        if "zones" in url:
            mock_zone = Mock()
            mock_zone.status_code = 200
            mock_zone.json.return_value = SAMPLE_HR_ZONE_RESPONSE
            return mock_zone
        else:
            mock_activity = Mock()
            mock_activity.status_code = 200
            mock_activity.json.return_value = SAMPLE_ACTIVITY_JSON
            return mock_activity

    mock_requests_get.side_effect = side_effect

    athlete_id = seed_activity.athlete_id
    access_token = "mock-access-token"

    # Execute enrichment with splits extraction
    result = enrich_one_activity(sqlalchemy_session, athlete_id, access_token, activity_id=99999)
    assert result is True

    # Validate splits inserted
    splits = sqlalchemy_session.query(Split).filter_by(activity_id=99999).all()
    assert len(splits) == 1
    assert splits[0].lap_index == 1
    assert splits[0].distance == 1000
    assert splits[0].elapsed_time == 300

    # Validate HR zone enrichment
    activity = sqlalchemy_session.query(Activity).filter_by(activity_id=99999).one()
    assert activity.hr_zone_1_pct is not None
    assert activity.hr_zone_5_pct is not None

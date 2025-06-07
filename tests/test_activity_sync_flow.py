import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

from src.db.models.activities import Activity
from src.db.models.splits import Split
from src.db.dao.token_dao import save_tokens_sa  # ✅ ADD THIS IMPORT
from src.services.activity_sync import sync_recent


@patch("src.services.strava_client.StravaClient.get_activities")
def test_activity_sync_inserts_data(mock_get_activities, sqlalchemy_session):
    mock_get_activities.return_value = [
        {
            "id": 9999,
            "athlete": {"id": 42},
            "name": "Test Activity",
            "type": "Run",
            "start_date": datetime.utcnow().isoformat(),
            "distance": 5000.0,
            "elapsed_time": 1500,
            "moving_time": 1450,
            "total_elevation_gain": 100.0,
            "external_id": "test123",
            "timezone": "UTC",
            "laps": [
                {
                    "split_index": 1,
                    "distance": 1000.0,
                    "elapsed_time": 300,
                    "moving_time": 290,
                    "average_speed": 3.3,
                    "max_speed": 3.5,
                    "start_index": 0,
                    "end_index": 299,
                    "split": True
                }
            ]
        }
    ]

    athlete_id = 42

    # ✅ Insert valid token for athlete before calling sync_recent()
    valid_token = int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    save_tokens_sa(sqlalchemy_session, athlete_id, "dummy_access", "dummy_refresh", valid_token)

    count = sync_recent(sqlalchemy_session, athlete_id)

    activity_row = sqlalchemy_session.query(Activity).filter_by(activity_id=9999).one_or_none()
    assert activity_row is not None
    assert activity_row.distance == 5000.0

    splits = sqlalchemy_session.query(Split).filter_by(activity_id=9999).all()
    assert len(splits) == 1
    assert splits[0].lap_index == 1
    assert splits[0].distance == 1000.0

    assert count == 1

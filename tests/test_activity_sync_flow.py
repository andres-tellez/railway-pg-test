import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

from src.db.models.activities import Activity
from src.db.models.splits import Split
from src.services.activity_sync import sync_recent


def mock_fetch_activities_between(access_token, start_date, end_date, per_page=200):
    # Return one activity with embedded splits
    return [
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
            "splits_metric": [
                {
                    "lap_index": 1,
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


@patch("src.services.activity_sync.fetch_activities_between", side_effect=mock_fetch_activities_between)
def test_activity_sync_inserts_data(mock_fetch, sqlalchemy_session):
    athlete_id = 42
    access_token = "dummy"

    count = sync_recent(sqlalchemy_session, athlete_id, access_token)

    # ✅ Verify activity inserted
    activity_row = sqlalchemy_session.query(Activity).filter_by(activity_id=9999).one_or_none()
    assert activity_row is not None
    assert activity_row.distance == 5000.0

    # ✅ Verify splits inserted
    splits = sqlalchemy_session.query(Split).filter_by(activity_id=9999).all()
    assert len(splits) == 1
    assert splits[0].lap_index == 1
    assert splits[0].distance == 1000.0

    # ✅ Verify total count returned
    assert count == 1

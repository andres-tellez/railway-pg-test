import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from src.db.models.activities import Activity
from src.db.dao.activity_stats_dao import ActivityStatsDAO
from src.db.dao.activity_dao import ActivityDAO


def test_get_by_id_returns_activity():
    mock_session = MagicMock()

    mock_query = mock_session.query.return_value
    mock_filter_by = mock_query.filter_by.return_value
    expected_activity = Activity(activity_id=123)
    mock_filter_by.first.return_value = expected_activity

    result = ActivityDAO.get_by_id(mock_session, 123)
    assert result == expected_activity

    mock_session.query.assert_called_once_with(Activity)
    mock_query.filter_by.assert_called_once_with(activity_id=123)
    mock_filter_by.first.assert_called_once()


def test_get_by_id_returns_none():
    mock_session = MagicMock()
    mock_query = mock_session.query.return_value
    mock_filter_by = mock_query.filter_by.return_value
    mock_filter_by.first.return_value = None

    result = ActivityDAO.get_by_id(mock_session, 999)
    assert result is None

    mock_session.query.assert_called_once_with(Activity)
    mock_query.filter_by.assert_called_once_with(activity_id=999)
    mock_filter_by.first.assert_called_once()


@patch("src.db.dao.activity_dao.convert_metrics")
def test_upsert_activities_empty_list_returns_zero(mock_convert):
    mock_session = MagicMock()
    count = ActivityDAO.upsert_activities(mock_session, athlete_id=1, activities=[])
    assert count == 0
    mock_convert.assert_not_called()
    mock_session.execute.assert_not_called()
    mock_session.commit.assert_not_called()


@patch("src.db.dao.activity_dao.convert_metrics")
def test_upsert_activities_single_activity(mock_convert):
    mock_session = MagicMock()
    mock_convert.return_value = {
        "conv_distance": 100,
        "conv_elevation_feet": 50,
        "conv_avg_speed": 5,
        "conv_max_speed": 10,
        "conv_moving_time": 60,
        "conv_elapsed_time": 65,
    }

    activities = [{
        "id": 101,
        "name": "Run",
        "type": "Run",
        "start_date": "2023-01-01T00:00:00Z",
        "distance": 1000,
        "elapsed_time": 65,
        "moving_time": 60,
        "total_elevation_gain": 15,
        "external_id": "ext-101",
        "timezone": "UTC",
        "hr_zone_1": 10,
        "hr_zone_2": 20,
        "hr_zone_3": 30,
        "hr_zone_4": 40,
        "hr_zone_5": 50
    }]

    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_session.execute.return_value = mock_result

    count = ActivityDAO.upsert_activities(mock_session, athlete_id=42, activities=activities)

    assert count == 1
    mock_convert.assert_called_once()
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


@patch("src.db.dao.activity_dao.convert_metrics")
def test_upsert_activities_multiple_activities(mock_convert):
    mock_session = MagicMock()
    mock_convert.return_value = {
        "conv_distance": 100,
        "conv_elevation_feet": 50,
        "conv_avg_speed": 5,
        "conv_max_speed": 10,
        "conv_moving_time": 60,
        "conv_elapsed_time": 65,
    }

    activities = [
        {"id": 201, "name": "Morning Run", "type": "Run", "start_date": "2023-01-01T06:00:00Z", "distance": 1000, "elapsed_time": 65, "moving_time": 60, "total_elevation_gain": 15, "external_id": "ext-201"},
        {"id": 202, "name": "Treadmill Run", "type": "Run", "start_date": "2023-01-02T07:00:00Z", "distance": 500, "elapsed_time": 35, "moving_time": 30, "total_elevation_gain": 5, "external_id": "ext-202"},
    ]

    mock_result = MagicMock()
    mock_result.rowcount = 2
    mock_session.execute.return_value = mock_result

    count = ActivityDAO.upsert_activities(mock_session, athlete_id=99, activities=activities)

    assert count == 2
    assert mock_convert.call_count == 2
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


def test_get_recent_activities():
    mock_session = MagicMock()
    fake_activity = MagicMock()
    fake_activity.activity_id = 999999
    fake_activity.athlete_id = 123
    fake_activity.name = "Test Run"
    mock_session.scalars.return_value.all.return_value = [fake_activity]

    result = ActivityStatsDAO.get_recent_activities(mock_session, athlete_id=123, days=7)

    assert isinstance(result, list)
    assert result[0].activity_id == 999999
    mock_session.scalars.assert_called_once()

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta
from src.services import activity_service as svc

@pytest.fixture
def mock_session():
    return MagicMock()

@pytest.fixture
def athlete_id():
    return 42

@pytest.fixture
def dummy_activity_json():
    return {
        "id": 123,
        "name": "Test Activity",
        "distance": 5000,
        "total_elevation_gain": 100,
        "average_speed": 3.5,
        "max_speed": 5.0,
        "moving_time": 1800,
        "elapsed_time": 2000,
        "type": "Run",
        "suffer_score": 50,
        "average_heartrate": 140,
        "max_heartrate": 170,
        "calories": 400,
        "hr_zone_1": 10,
        "hr_zone_2": 20,
        "hr_zone_3": 30,
        "hr_zone_4": 25,
        "hr_zone_5": 15
    }

@pytest.fixture
def dummy_zones_data():
    return [
        {
            "type": "heartrate",
            "distribution_buckets": [
                {"time": 300},
                {"time": 300},
                {"time": 200},
                {"time": 100},
                {"time": 100},
            ]
        }
    ]

@pytest.fixture
def dummy_streams():
    return {
        "distance": [0, 1609.344, 3218.688, 4000],
        "time": [0, 600, 1200, 1500],
        "velocity_smooth": [3.0, 3.5, 4.0, 3.8],
        "heartrate": [130, 135, 140, 145],
    }

def test_get_activities_to_enrich_returns_ids(mock_session, athlete_id):
    # Setup mock execute().fetchall()
    mock_session.execute.return_value.fetchall.return_value = [
        MagicMock(activity_id=101),
        MagicMock(activity_id=102),
        MagicMock(activity_id=103),
    ]
    result = svc.get_activities_to_enrich(mock_session, athlete_id, limit=3)
    assert result == [101, 102, 103]
    mock_session.execute.assert_called_once()

@patch("src.services.activity_service.StravaClient")
@patch("src.services.activity_service.extract_hr_zone_percentages", return_value=[10,20,30,25,15])
@patch("src.services.activity_service.upsert_splits")
def test_enrich_one_activity_success(mock_upsert, mock_extract_zones, MockClient, mock_session, dummy_activity_json, dummy_zones_data, dummy_streams):
    mock_client = MockClient.return_value
    mock_client.get_activity.return_value = dummy_activity_json
    mock_client.get_hr_zones.return_value = dummy_zones_data
    mock_client.get_streams.return_value = dummy_streams

    result = svc.enrich_one_activity(mock_session, "fake-token", 123)
    assert result is True
    mock_client.get_activity.assert_called_once_with(123)
    mock_extract_zones.assert_called_once_with(dummy_zones_data)
    mock_upsert.assert_called_once()
    mock_session.execute.assert_called()
    mock_session.commit.assert_called()

@patch("src.services.activity_service.get_valid_token", return_value="fake-token")
@patch("src.services.activity_service.enrich_one_activity", return_value=True)
def test_enrich_one_activity_with_refresh_calls_enrich(mock_enrich, mock_token, mock_session, athlete_id):
    result = svc.enrich_one_activity_with_refresh(mock_session, athlete_id, 456)
    assert result is True
    mock_token.assert_called_once_with(mock_session, athlete_id)
    mock_enrich.assert_called_once_with(mock_session, "fake-token", 456)

def test_update_activity_enrichment_executes_sql(mock_session, dummy_activity_json):
    hr_zones = [10, 20, 30, 25, 15]
    svc.update_activity_enrichment(mock_session, 123, dummy_activity_json, hr_zones)
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()

def test_extract_hr_zone_percentages_returns_correct_percentages():
    zones_data = [
        {
            "type": "heartrate",
            "distribution_buckets": [
                {"time": 300},
                {"time": 300},
                {"time": 200},
                {"time": 100},
                {"time": 100},
            ]
        }
    ]
    result = svc.extract_hr_zone_percentages(zones_data)
    assert sum(result) == 100.0
    assert len(result) == 5

def test_build_mile_splits_correctness():
    streams = {
        "distance": [0, 1609.344, 3218.688, 4000],
        "time": [0, 600, 1200, 1500],
        "velocity_smooth": [3.0, 3.5, 4.0, 3.8],
        "heartrate": [130, 135, 140, 145],
    }
    splits = svc.build_mile_splits(1, streams)
    assert isinstance(splits, list)
    assert all("activity_id" in split for split in splits)
    assert splits[0]["lap_index"] == 1
    assert splits[-1]["lap_index"] == len(splits)

@patch("src.services.activity_service.ActivityDAO.upsert_activities")
@patch("src.services.activity_service.StravaClient.get_activities")
@patch("src.services.activity_service.get_valid_token", return_value="fake-token")
def test_activity_ingestion_service_methods(mock_token, mock_get_activities, mock_upsert, mock_session, athlete_id):
    # Setup mock activities
    mock_get_activities.return_value = [{"id": 1}, {"id": 2}]

    service = svc.ActivityIngestionService(mock_session, athlete_id)

    # ingest_recent calls DAO upsert
    service.ingest_recent(lookback_days=10, max_activities=5)
    mock_get_activities.assert_called()
    mock_upsert.assert_called_once()

    # ingest_full_history delegates to ingest_recent
    mock_upsert.reset_mock()
    service.ingest_full_history(lookback_days=365, max_activities=10)
    mock_upsert.assert_called_once()

    # ingest_between calls DAO upsert
    start = datetime.utcnow() - timedelta(days=5)
    end = datetime.utcnow()
    mock_upsert.reset_mock()
    service.ingest_between(start, end, max_activities=10)
    mock_upsert.assert_called_once()

@patch("src.services.activity_service.get_activities_to_enrich")
@patch("src.services.activity_service.enrich_one_activity_with_refresh")
def test_run_enrichment_batch_calls_all(mock_enrich, mock_get_activities, mock_session, athlete_id):
    mock_get_activities.return_value = [1, 2, 3]
    svc.run_enrichment_batch(mock_session, athlete_id, batch_size=3)
    assert mock_enrich.call_count == 3
    mock_enrich.assert_has_calls([call(mock_session, athlete_id, 1), call(mock_session, athlete_id, 2), call(mock_session, athlete_id, 3)])

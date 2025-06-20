import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import HTTPError
from src.services.strava_access_service import StravaClient

@pytest.fixture
def client():
    return StravaClient(access_token="fake-token")

@patch("src.services.strava_access_service.requests.request")
def test_request_with_backoff_success(mock_request, client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": "ok"}
    mock_request.return_value = mock_resp

    result = client._request_with_backoff("GET", "http://test-url")
    assert result == {"data": "ok"}
    mock_request.assert_called_once()

@patch("src.services.strava_access_service.requests.request")
@patch("time.sleep", return_value=None)
def test_request_with_backoff_rate_limit_retries(mock_sleep, mock_request, client):
    resp_429 = MagicMock(status_code=429)
    resp_429.raise_for_status.side_effect = None
    resp_429.json.return_value = {}

    resp_200 = MagicMock(status_code=200)
    resp_200.json.return_value = {"success": True}

    mock_request.side_effect = [resp_429, resp_429, resp_200]

    result = client._request_with_backoff("GET", "http://test-url")
    assert result == {"success": True}
    assert mock_request.call_count == 3
    assert mock_sleep.call_count == 2

@patch("src.services.strava_access_service.requests.request")
@patch("time.sleep", return_value=None)
def test_request_with_backoff_max_retries_exceeded(mock_sleep, mock_request, client):
    resp_429 = MagicMock(status_code=429)
    resp_429.raise_for_status.side_effect = None
    resp_429.json.return_value = {}

    mock_request.return_value = resp_429

    with pytest.raises(RuntimeError, match="Exceeded max retries"):
        client._request_with_backoff("GET", "http://test-url")

@patch("src.services.strava_access_service.requests.request")
def test_get_activities_pagination_and_limit(mock_request, client):
    batch1 = [{"id": 1}, {"id": 2}]
    batch2 = [{"id": 3}]
    batch3 = []

    mock_request.side_effect = [
        MagicMock(status_code=200, json=lambda: batch1),
        MagicMock(status_code=200, json=lambda: batch2),
        MagicMock(status_code=200, json=lambda: batch3),
    ]

    activities = client.get_activities(limit=3, per_page=2)
    assert len(activities) == 3
    assert activities[0]["id"] == 1
    assert mock_request.call_count == 2  # Corrected here

@patch("src.services.strava_access_service.requests.request")
def test_get_activity_success(mock_request, client):
    expected = {"id": 123}
    mock_request.return_value = MagicMock(status_code=200, json=lambda: expected)

    activity = client.get_activity(123)
    assert activity == expected
    mock_request.assert_called_once()

@patch("src.services.strava_access_service.requests.request")
def test_get_hr_zones_success_and_404(mock_request, client):
    mock_request.return_value = MagicMock(status_code=200, json=lambda: {"zones": []})
    result = client.get_hr_zones(1)
    assert "zones" in result

    # Simulate 404 HTTPError
    mock_resp = MagicMock(status_code=404)
    mock_error = HTTPError(response=mock_resp)
    mock_request.side_effect = mock_error
    result = client.get_hr_zones(999)
    assert result is None

@patch("src.services.strava_access_service.requests.request")
def test_get_splits_success_and_404(mock_request, client):
    mock_request.return_value = MagicMock(status_code=200, json=lambda: [{"lap": 1}])
    splits = client.get_splits(1)
    assert len(splits) == 1

    mock_resp = MagicMock(status_code=404)
    mock_error = HTTPError(response=mock_resp)
    mock_request.side_effect = mock_error
    splits = client.get_splits(999)
    assert splits == []

@patch("src.services.strava_access_service.requests.request")
def test_get_streams_parsing_and_empty(mock_request, client):
    resp_json = {
        "heartrate": {"data": [100, 101, "102", "abc"]},
        "cadence": {"data": [80, 81]},
        "watts": None
    }
    mock_request.return_value = MagicMock(status_code=200, json=lambda: resp_json)

    streams = client.get_streams(1, ["heartrate", "cadence", "watts"])
    assert streams["heartrate"] == [100.0, 101.0, 102.0]
    assert streams["cadence"] == [80.0, 81.0]
    assert streams["watts"] == []

@patch("src.services.strava_access_service.requests.request")
def test_get_streams_handles_bad_data(mock_request, client):
    # Simulate bad data causing exception in float conversion
    resp_json = {
        "heartrate": {"data": ["bad", "data", 123]},
    }
    mock_request.return_value = MagicMock(status_code=200, json=lambda: resp_json)

    streams = client.get_streams(1, ["heartrate"])
    assert streams["heartrate"] == [123.0]

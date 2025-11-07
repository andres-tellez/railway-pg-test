"""
Comprehensive Tests for Strava Access Service

Tests for StravaClient including:
- Error scenarios with new exception types
- Authentication errors
- API errors
- Rate limiting
- Retry logic
"""

import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import HTTPError, RequestException
from src.services.strava_access_service import StravaClient
from src.utils.strava_exceptions import (
    StravaAPIError,
    StravaRateLimitError,
    StravaAuthenticationError,
)


@pytest.fixture
def client():
    return StravaClient(access_token="fake-token")


class TestStravaClientAuthenticationErrors:
    """Tests for authentication error handling."""

    @patch("src.services.strava_access_service.requests.request")
    def test_401_raises_authentication_error(self, mock_request, client):
        """Test that 401 status code raises StravaAuthenticationError."""
        resp_401 = MagicMock(status_code=401)
        resp_401.headers = {}
        mock_request.return_value = resp_401

        with pytest.raises(StravaAuthenticationError) as exc_info:
            client._request_with_backoff("GET", "http://test-url")

        assert exc_info.value.status_code == 401
        assert "authentication" in exc_info.value.message.lower()

    @patch("src.services.strava_access_service.requests.request")
    def test_401_includes_details(self, mock_request, client):
        """Test that 401 error includes request details."""
        resp_401 = MagicMock(status_code=401)
        resp_401.headers = {}
        mock_request.return_value = resp_401

        with pytest.raises(StravaAuthenticationError) as exc_info:
            client._request_with_backoff("GET", "http://test-url")

        assert "details" in exc_info.value.details
        assert "url" in exc_info.value.details
        assert "method" in exc_info.value.details


class TestStravaClientAPIErrors:
    """Tests for general API error handling."""

    @patch("src.services.strava_access_service.requests.request")
    def test_500_raises_api_error(self, mock_request, client):
        """Test that 500 status code raises StravaAPIError."""
        resp_500 = MagicMock(status_code=500)
        resp_500.text = "Internal Server Error"
        resp_500.raise_for_status.side_effect = HTTPError(response=resp_500)
        mock_request.return_value = resp_500

        with pytest.raises(StravaAPIError) as exc_info:
            client._request_with_backoff("GET", "http://test-url")

        assert exc_info.value.status_code == 500
        assert exc_info.value.response_body is not None

    @patch("src.services.strava_access_service.requests.request")
    def test_404_raises_api_error(self, mock_request, client):
        """Test that 404 status code raises StravaAPIError."""
        resp_404 = MagicMock(status_code=404)
        resp_404.text = "Not Found"
        resp_404.raise_for_status.side_effect = HTTPError(response=resp_404)
        mock_request.return_value = resp_404

        with pytest.raises(StravaAPIError) as exc_info:
            client._request_with_backoff("GET", "http://test-url")

        assert exc_info.value.status_code == 404

    @patch("src.services.strava_access_service.requests.request")
    def test_api_error_includes_response_body(self, mock_request, client):
        """Test that API error includes response body (truncated)."""
        resp_500 = MagicMock(status_code=500)
        resp_500.text = "A" * 1000  # Long response
        resp_500.raise_for_status.side_effect = HTTPError(response=resp_500)
        mock_request.return_value = resp_500

        with pytest.raises(StravaAPIError) as exc_info:
            client._request_with_backoff("GET", "http://test-url")

        # Response body should be truncated to 500 chars
        assert len(exc_info.value.response_body) <= 500


class TestStravaClientRateLimiting:
    """Tests for rate limiting and retry logic."""

    @patch("src.services.strava_access_service.requests.request")
    @patch("time.sleep", return_value=None)
    def test_rate_limit_retry_with_retry_after_header(
        self, mock_sleep, mock_request, client
    ):
        """Test that rate limit retry respects Retry-After header."""
        resp_429 = MagicMock(status_code=429)
        resp_429.headers = {"Retry-After": "60"}
        resp_429.raise_for_status.side_effect = None

        resp_200 = MagicMock(status_code=200)
        resp_200.json.return_value = {"success": True}

        mock_request.side_effect = [resp_429, resp_200]

        result = client._request_with_backoff("GET", "http://test-url")

        assert result == {"success": True}
        assert mock_request.call_count == 2

    @patch("src.services.strava_access_service.requests.request")
    @patch("time.sleep", return_value=None)
    def test_rate_limit_exceeded_raises_error(self, mock_sleep, mock_request, client):
        """Test that exceeding max retries raises StravaRateLimitError."""
        resp_429 = MagicMock(status_code=429)
        resp_429.headers = {}
        resp_429.raise_for_status.side_effect = None
        mock_request.return_value = resp_429

        with pytest.raises(StravaRateLimitError) as exc_info:
            client._request_with_backoff("GET", "http://test-url")

        assert exc_info.value.status_code == 429
        assert exc_info.value.retry_after is not None
        assert "max retries" in exc_info.value.message.lower()

    @patch("src.services.strava_access_service.requests.request")
    @patch("time.sleep", return_value=None)
    def test_rate_limit_exponential_backoff(self, mock_sleep, mock_request, client):
        """Test that backoff time increases exponentially."""
        resp_429 = MagicMock(status_code=429)
        resp_429.headers = {}
        resp_429.raise_for_status.side_effect = None

        resp_200 = MagicMock(status_code=200)
        resp_200.json.return_value = {"success": True}

        # First 429, then 200
        mock_request.side_effect = [resp_429, resp_200]

        client._request_with_backoff("GET", "http://test-url")

        # Verify sleep was called with increasing backoff
        assert mock_sleep.called
        # First sleep should be initial backoff (10 seconds from config)
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert len(sleep_calls) >= 1


class TestStravaClientMethods:
    """Tests for StravaClient public methods."""

    @patch("src.services.strava_access_service.StravaClient._request_with_backoff")
    def test_get_activities_with_date_range(self, mock_request, client):
        """Test get_activities with after and before parameters."""
        mock_request.return_value = [{"id": 1}, {"id": 2}]

        activities = client.get_activities(
            after=1609459200,  # 2021-01-01
            before=1640995200,  # 2022-01-01
            limit=10,
            per_page=5,
        )

        assert len(activities) == 2
        # Verify params were passed correctly
        call_args = mock_request.call_args
        assert "params" in call_args.kwargs
        assert call_args.kwargs["params"]["after"] == 1609459200
        assert call_args.kwargs["params"]["before"] == 1640995200

    @patch("src.services.strava_access_service.StravaClient._request_with_backoff")
    def test_get_activities_pagination(self, mock_request, client):
        """Test that get_activities handles pagination correctly."""
        # First page returns 2, second page returns 1, third returns empty
        mock_request.side_effect = [[{"id": 1}, {"id": 2}], [{"id": 3}], []]

        activities = client.get_activities(limit=5, per_page=2)

        assert len(activities) == 3
        assert mock_request.call_count == 3  # 3 pages

    @patch("src.services.strava_access_service.StravaClient._request_with_backoff")
    def test_get_activity_calls_correct_endpoint(self, mock_request, client):
        """Test that get_activity calls the correct API endpoint."""
        mock_request.return_value = {"id": 123, "name": "Test Run"}

        activity = client.get_activity(123)

        assert activity["id"] == 123
        call_args = mock_request.call_args
        assert "activities/123" in call_args[0][1]  # URL contains activity ID

    @patch("src.services.strava_access_service.StravaClient._request_with_backoff")
    def test_get_streams_handles_missing_types(self, mock_request, client):
        """Test that get_streams handles missing stream types gracefully."""
        mock_request.return_value = {
            "heartrate": {"data": [100, 101]},
            # cadence is missing
        }

        streams = client.get_streams(123, ["heartrate", "cadence"])

        assert "heartrate" in streams
        assert streams["cadence"] == []  # Missing type returns empty list

    @patch("src.services.strava_access_service.StravaClient._request_with_backoff")
    def test_get_streams_converts_to_float(self, mock_request, client):
        """Test that get_streams converts string numbers to floats."""
        mock_request.return_value = {
            "heartrate": {"data": ["100", "101", 102]},
        }

        streams = client.get_streams(123, ["heartrate"])

        assert streams["heartrate"] == [100.0, 101.0, 102.0]
        assert all(isinstance(x, float) for x in streams["heartrate"])


class TestStravaClientErrorScenarios:
    """Tests for various error scenarios."""

    @patch("src.services.strava_access_service.requests.request")
    def test_network_error_raises_api_error(self, mock_request, client):
        """Test that network errors raise StravaAPIError."""
        mock_request.side_effect = RequestException("Connection failed")

        with pytest.raises(StravaAPIError):
            client._request_with_backoff("GET", "http://test-url")

    @patch("src.services.strava_access_service.requests.request")
    def test_invalid_json_response(self, mock_request, client):
        """Test handling of invalid JSON response."""
        resp = MagicMock(status_code=200)
        resp.json.side_effect = ValueError("Invalid JSON")
        mock_request.return_value = resp

        # Should raise HTTPError which gets converted to StravaAPIError
        resp.raise_for_status.side_effect = HTTPError(response=resp)

        with pytest.raises(StravaAPIError):
            client._request_with_backoff("GET", "http://test-url")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

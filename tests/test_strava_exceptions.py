"""
Test Strava Custom Exceptions

Tests for custom exception classes used in Strava integration.
"""

import pytest
from src.utils.strava_exceptions import (
    StravaError,
    StravaAPIError,
    StravaRateLimitError,
    StravaAuthenticationError,
    StravaTokenError,
    StravaTokenNotFoundError,
    StravaTokenRevokedError,
    StravaTokenRefreshError,
    StravaIngestionError,
    StravaIngestionValidationError,
    StravaIngestionSyncError,
    StravaIngestionEnrichmentError,
    StravaAthleteAlreadyLinkedError,
    StravaOAuthError,
    StravaOAuthCodeExchangeError,
    StravaOAuthStateError,
    StravaConfigurationError,
)


class TestStravaError:
    """Tests for base StravaError exception."""

    def test_strava_error_basic(self):
        """Test basic StravaError creation."""
        error = StravaError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {}

    def test_strava_error_with_details(self):
        """Test StravaError with details."""
        error = StravaError("Test error", details={"key": "value"})
        assert error.message == "Test error"
        assert error.details == {"key": "value"}


class TestStravaAPIError:
    """Tests for StravaAPIError exception."""

    def test_strava_api_error_basic(self):
        """Test basic StravaAPIError creation."""
        error = StravaAPIError("API error", status_code=500)
        assert error.message == "API error"
        assert error.status_code == 500
        assert error.response_body is None

    def test_strava_api_error_with_response(self):
        """Test StravaAPIError with response body."""
        error = StravaAPIError(
            "API error", status_code=400, response_body="Bad request"
        )
        assert error.status_code == 400
        assert error.response_body == "Bad request"


class TestStravaRateLimitError:
    """Tests for StravaRateLimitError exception."""

    def test_strava_rate_limit_error(self):
        """Test StravaRateLimitError creation."""
        error = StravaRateLimitError(retry_after=60)
        assert error.status_code == 429
        assert error.retry_after == 60


class TestStravaAuthenticationError:
    """Tests for StravaAuthenticationError exception."""

    def test_strava_authentication_error(self):
        """Test StravaAuthenticationError creation."""
        error = StravaAuthenticationError()
        assert error.status_code == 401


class TestStravaTokenErrors:
    """Tests for token-related exceptions."""

    def test_strava_token_not_found_error(self):
        """Test StravaTokenNotFoundError."""
        error = StravaTokenNotFoundError(athlete_id=12345)
        assert error.athlete_id == 12345
        assert "12345" in error.message
        assert error.details["athlete_id"] == 12345

    def test_strava_token_revoked_error(self):
        """Test StravaTokenRevokedError."""
        error = StravaTokenRevokedError(athlete_id=12345)
        assert error.athlete_id == 12345
        assert "12345" in error.message

    def test_strava_token_refresh_error(self):
        """Test StravaTokenRefreshError."""
        error = StravaTokenRefreshError(athlete_id=12345, reason="Network error")
        assert error.athlete_id == 12345
        assert error.reason == "Network error"
        assert "Network error" in error.message


class TestStravaIngestionErrors:
    """Tests for ingestion-related exceptions."""

    def test_strava_ingestion_validation_error(self):
        """Test StravaIngestionValidationError."""
        errors = {"athlete_id": "required"}
        error = StravaIngestionValidationError(
            "Validation failed", validation_errors=errors
        )
        assert error.validation_errors == errors
        assert "Validation failed" in error.message

    def test_strava_ingestion_sync_error(self):
        """Test StravaIngestionSyncError."""
        error = StravaIngestionSyncError(athlete_id=12345, reason="API error")
        assert error.athlete_id == 12345
        assert error.reason == "API error"
        assert "12345" in error.message

    def test_strava_ingestion_enrichment_error(self):
        """Test StravaIngestionEnrichmentError."""
        error = StravaIngestionEnrichmentError(
            activity_id=67890, athlete_id=12345, reason="Stream fetch failed"
        )
        assert error.activity_id == 67890
        assert error.athlete_id == 12345
        assert error.reason == "Stream fetch failed"


class TestStravaOAuthErrors:
    """Tests for OAuth-related exceptions."""

    def test_strava_oauth_code_exchange_error(self):
        """Test StravaOAuthCodeExchangeError."""
        error = StravaOAuthCodeExchangeError(reason="Invalid code")
        assert error.reason == "Invalid code"
        assert "Invalid code" in error.message

    def test_strava_oauth_state_error(self):
        """Test StravaOAuthStateError."""
        error = StravaOAuthStateError(reason="Expired state")
        assert error.reason == "Expired state"
        assert "Expired state" in error.message

    def test_strava_athlete_already_linked_error(self):
        """Test StravaAthleteAlreadyLinkedError."""
        error = StravaAthleteAlreadyLinkedError(athlete_id=619645)
        assert error.athlete_id == 619645
        assert error.details.get("error_code") == "ATHLETE_ALREADY_LINKED"
        assert "already linked" in error.message.lower()


class TestStravaConfigurationError:
    """Tests for configuration-related exceptions."""

    def test_strava_configuration_error(self):
        """Test StravaConfigurationError."""
        error = StravaConfigurationError(missing_config="STRAVA_CLIENT_ID")
        assert error.missing_config == "STRAVA_CLIENT_ID"
        assert "STRAVA_CLIENT_ID" in error.message


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""

    def test_exception_inheritance(self):
        """Test that exceptions inherit correctly."""
        # API errors
        assert issubclass(StravaRateLimitError, StravaAPIError)
        assert issubclass(StravaAuthenticationError, StravaAPIError)
        assert issubclass(StravaAPIError, StravaError)

        # Token errors
        assert issubclass(StravaTokenNotFoundError, StravaTokenError)
        assert issubclass(StravaTokenRevokedError, StravaTokenError)
        assert issubclass(StravaTokenRefreshError, StravaTokenError)
        assert issubclass(StravaTokenError, StravaError)

        # Ingestion errors
        assert issubclass(StravaIngestionValidationError, StravaIngestionError)
        assert issubclass(StravaIngestionSyncError, StravaIngestionError)
        assert issubclass(StravaIngestionEnrichmentError, StravaIngestionError)
        assert issubclass(StravaIngestionError, StravaError)

        # OAuth errors
        assert issubclass(StravaOAuthCodeExchangeError, StravaOAuthError)
        assert issubclass(StravaOAuthStateError, StravaOAuthError)
        assert issubclass(StravaAthleteAlreadyLinkedError, StravaOAuthError)
        assert issubclass(StravaOAuthError, StravaError)

        # Configuration error
        assert issubclass(StravaConfigurationError, StravaError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

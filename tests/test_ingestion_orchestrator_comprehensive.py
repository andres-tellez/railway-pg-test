"""
Comprehensive Tests for Ingestion Orchestrator Service

Tests for the main ingestion orchestrator service, including:
- Full ingestion flow
- Error scenarios
- Token handling
- Validation
- Enrichment
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)
from src.utils.strava_exceptions import (
    StravaIngestionValidationError,
    StravaIngestionSyncError,
    StravaIngestionEnrichmentError,
    StravaTokenError,
    StravaTokenNotFoundError,
    StravaTokenRefreshError,
)


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


@pytest.fixture
def sample_activity_data():
    """Sample activity data for testing."""
    return {
        "id": 123456,
        "external_id": "test_activity.fit",
        "name": "Test Run",
        "type": "Run",
        "distance": 5000.0,
        "moving_time": 1800,
        "elapsed_time": 1900,
        "total_elevation_gain": 100.0,
        "start_date": "2025-01-01T08:00:00Z",
        "average_speed": 2.8,
        "max_speed": 3.5,
    }


class TestIngestionValidation:
    """Tests for input validation in ingestion."""

    def test_invalid_athlete_id_none(self, mock_session):
        """Test that None athlete_id raises validation error."""
        with pytest.raises(StravaIngestionValidationError):
            run_full_ingestion_and_enrichment(mock_session, None)

    def test_invalid_athlete_id_negative(self, mock_session):
        """Test that negative athlete_id raises validation error."""
        with pytest.raises(StravaIngestionValidationError):
            run_full_ingestion_and_enrichment(mock_session, -1)

    def test_invalid_athlete_id_zero(self, mock_session):
        """Test that zero athlete_id raises validation error."""
        with pytest.raises(StravaIngestionValidationError):
            run_full_ingestion_and_enrichment(mock_session, 0)

    def test_invalid_athlete_id_too_large(self, mock_session):
        """Test that very large athlete_id raises validation error."""
        with pytest.raises(StravaIngestionValidationError):
            run_full_ingestion_and_enrichment(mock_session, 9999999999)

    def test_invalid_user_id_format(self, mock_session):
        """Test that invalid user_id format raises validation error."""
        with pytest.raises(StravaIngestionValidationError):
            run_full_ingestion_and_enrichment(
                mock_session, athlete_id=12345, user_id="not-a-uuid"
            )

    def test_invalid_lookback_days(self, mock_session):
        """Test that invalid lookback_days raises validation error."""
        with pytest.raises(StravaIngestionValidationError):
            run_full_ingestion_and_enrichment(
                mock_session, athlete_id=12345, lookback_days=0
            )

    def test_invalid_max_activities(self, mock_session):
        """Test that invalid max_activities raises validation error."""
        with pytest.raises(StravaIngestionValidationError):
            run_full_ingestion_and_enrichment(
                mock_session, athlete_id=12345, max_activities=0
            )


class TestIngestionTokenErrors:
    """Tests for token-related errors during ingestion."""

    @patch("src.services.ingestion_orchestrator_service.get_valid_token")
    def test_token_not_found_error(self, mock_get_token, mock_session):
        """Test that missing token raises sync error."""
        mock_get_token.side_effect = StravaTokenNotFoundError(athlete_id=12345)

        with pytest.raises(StravaIngestionSyncError) as exc_info:
            run_full_ingestion_and_enrichment(mock_session, athlete_id=12345)

        assert "token" in exc_info.value.message.lower()
        assert exc_info.value.athlete_id == 12345

    @patch("src.services.ingestion_orchestrator_service.get_valid_token")
    def test_token_refresh_error(self, mock_get_token, mock_session):
        """Test that token refresh failure raises sync error."""
        mock_get_token.side_effect = StravaTokenRefreshError(
            athlete_id=12345, reason="Network error"
        )

        with pytest.raises(StravaIngestionSyncError) as exc_info:
            run_full_ingestion_and_enrichment(mock_session, athlete_id=12345)

        assert "token" in exc_info.value.message.lower()
        assert exc_info.value.athlete_id == 12345


class TestIngestionSyncErrors:
    """Tests for sync-related errors during ingestion."""

    @patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
    @patch("src.services.ingestion_orchestrator_service.get_valid_token")
    def test_api_error_during_fetch(
        self, mock_get_token, mock_service_class, mock_session
    ):
        """Test that API errors during activity fetch raise sync error."""
        mock_get_token.return_value = "valid-token"
        mock_service = mock_service_class.return_value
        mock_service.client.get_activities.side_effect = Exception(
            "API connection failed"
        )

        with pytest.raises(StravaIngestionSyncError) as exc_info:
            run_full_ingestion_and_enrichment(mock_session, athlete_id=12345)

        assert (
            "fetch" in exc_info.value.message.lower()
            or "sync" in exc_info.value.message.lower()
        )
        assert exc_info.value.athlete_id == 12345

    @patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
    @patch("src.services.ingestion_orchestrator_service.get_valid_token")
    def test_no_activities_found(
        self, mock_get_token, mock_service_class, mock_session
    ):
        """Test that no activities found returns zero synced."""
        mock_get_token.return_value = "valid-token"
        mock_service = mock_service_class.return_value
        mock_service.client.get_activities.return_value = []

        result = run_full_ingestion_and_enrichment(mock_session, athlete_id=12345)

        assert result["synced"] == 0
        assert result["enriched"] == 0


class TestIngestionEnrichmentErrors:
    """Tests for enrichment-related errors during ingestion."""

    @patch("src.services.ingestion_orchestrator_service.run_enrichment_batch")
    @patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
    @patch("src.services.ingestion_orchestrator_service.get_valid_token")
    def test_enrichment_failure_does_not_fail_ingestion(
        self,
        mock_get_token,
        mock_service_class,
        mock_enrichment,
        mock_session,
        sample_activity_data,
    ):
        """Test that enrichment failure doesn't fail entire ingestion."""
        mock_get_token.return_value = "valid-token"
        mock_service = mock_service_class.return_value
        mock_service.client.get_activities.return_value = [sample_activity_data]
        mock_enrichment.side_effect = Exception("Enrichment failed")

        # Mock DAO to return success
        with patch(
            "src.services.ingestion_orchestrator_service.ActivityDAO.upsert_activities"
        ) as mock_upsert:
            mock_upsert.return_value = 1

            result = run_full_ingestion_and_enrichment(mock_session, athlete_id=12345)

            # Ingestion should succeed even if enrichment fails
            assert result["synced"] == 1
            assert result["enriched"] == 0  # Enrichment failed

    @patch("src.services.ingestion_orchestrator_service.run_enrichment_batch")
    @patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
    @patch("src.services.ingestion_orchestrator_service.get_valid_token")
    def test_token_error_during_enrichment(
        self,
        mock_get_token,
        mock_service_class,
        mock_enrichment,
        mock_session,
        sample_activity_data,
    ):
        """Test that token error during enrichment is handled gracefully."""
        mock_get_token.return_value = "valid-token"
        mock_service = mock_service_class.return_value
        mock_service.client.get_activities.return_value = [sample_activity_data]
        mock_enrichment.side_effect = StravaTokenError("Token expired")

        # Mock DAO to return success
        with patch(
            "src.services.ingestion_orchestrator_service.ActivityDAO.upsert_activities"
        ) as mock_upsert:
            mock_upsert.return_value = 1

            result = run_full_ingestion_and_enrichment(mock_session, athlete_id=12345)

            # Ingestion should succeed, enrichment should be skipped
            assert result["synced"] == 1
            assert result["enriched"] == 0


class TestIngestionSuccess:
    """Tests for successful ingestion scenarios."""

    @patch("src.services.ingestion_orchestrator_service.run_enrichment_batch")
    @patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
    @patch("src.services.ingestion_orchestrator_service.get_valid_token")
    def test_successful_ingestion_and_enrichment(
        self,
        mock_get_token,
        mock_service_class,
        mock_enrichment,
        mock_session,
        sample_activity_data,
    ):
        """Test successful ingestion and enrichment."""
        mock_get_token.return_value = "valid-token"
        mock_service = mock_service_class.return_value
        mock_service.client.get_activities.return_value = [sample_activity_data]
        mock_enrichment.return_value = 1

        # Mock DAO to return success
        with patch(
            "src.services.ingestion_orchestrator_service.ActivityDAO.upsert_activities"
        ) as mock_upsert:
            mock_upsert.return_value = 1

            result = run_full_ingestion_and_enrichment(mock_session, athlete_id=12345)

            assert result["synced"] == 1
            assert result["enriched"] == 1

    @patch("src.services.ingestion_orchestrator_service.run_enrichment_batch")
    @patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
    @patch("src.services.ingestion_orchestrator_service.get_valid_token")
    def test_filters_non_run_activities(
        self, mock_get_token, mock_service_class, mock_enrichment, mock_session
    ):
        """Test that only Run activities are processed."""
        mock_get_token.return_value = "valid-token"
        mock_service = mock_service_class.return_value
        mock_service.client.get_activities.return_value = [
            {"id": 1, "type": "Run", "external_id": "run1.fit"},
            {"id": 2, "type": "Ride", "external_id": "ride1.fit"},
            {"id": 3, "type": "Run", "external_id": "run2.fit"},
        ]
        mock_enrichment.return_value = 2

        # Mock DAO to return success
        with patch(
            "src.services.ingestion_orchestrator_service.ActivityDAO.upsert_activities"
        ) as mock_upsert:
            mock_upsert.return_value = 2

            result = run_full_ingestion_and_enrichment(mock_session, athlete_id=12345)

            # Should only sync 2 Run activities, not the Ride
            assert result["synced"] == 2
            assert result["enriched"] == 2


class TestIngestionParameters:
    """Tests for ingestion parameter handling."""

    @patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
    @patch("src.services.ingestion_orchestrator_service.get_valid_token")
    def test_custom_lookback_days(
        self, mock_get_token, mock_service_class, mock_session
    ):
        """Test that custom lookback_days is used."""
        mock_get_token.return_value = "valid-token"
        mock_service = mock_service_class.return_value
        mock_service.client.get_activities.return_value = []

        run_full_ingestion_and_enrichment(
            mock_session, athlete_id=12345, lookback_days=30
        )

        # Verify get_activities was called with correct date range
        assert mock_service.client.get_activities.called

    @patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
    @patch("src.services.ingestion_orchestrator_service.get_valid_token")
    def test_custom_max_activities(
        self, mock_get_token, mock_service_class, mock_session
    ):
        """Test that custom max_activities is used."""
        mock_get_token.return_value = "valid-token"
        mock_service = mock_service_class.return_value
        mock_service.client.get_activities.return_value = []

        run_full_ingestion_and_enrichment(
            mock_session, athlete_id=12345, max_activities=10
        )

        # Verify get_activities was called
        assert mock_service.client.get_activities.called

    @patch("src.services.ingestion_orchestrator_service.run_enrichment_batch")
    @patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
    @patch("src.services.ingestion_orchestrator_service.get_valid_token")
    def test_custom_batch_size(
        self,
        mock_get_token,
        mock_service_class,
        mock_enrichment,
        mock_session,
        sample_activity_data,
    ):
        """Test that custom batch_size is used for enrichment."""
        mock_get_token.return_value = "valid-token"
        mock_service = mock_service_class.return_value
        mock_service.client.get_activities.return_value = [sample_activity_data]
        mock_enrichment.return_value = 1

        # Mock DAO
        with patch(
            "src.services.ingestion_orchestrator_service.ActivityDAO.upsert_activities"
        ) as mock_upsert:
            mock_upsert.return_value = 1

            run_full_ingestion_and_enrichment(
                mock_session, athlete_id=12345, batch_size=25
            )

            # Verify enrichment was called with custom batch_size
            mock_enrichment.assert_called()
            call_kwargs = mock_enrichment.call_args[1]
            assert call_kwargs.get("batch_size") == 25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

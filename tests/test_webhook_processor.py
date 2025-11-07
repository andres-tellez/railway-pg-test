"""
Test Webhook Processor Service

Comprehensive tests for webhook event processing.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
from src.services.webhook_processor_service import (
    process_webhook_event,
    _handle_activity_create,
    _handle_activity_update,
    _handle_activity_delete,
)
from src.db.models.webhook_events import WebhookEvent, WebhookEventStatus
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.activities import Activity
from src.utils.strava_exceptions import (
    StravaTokenError,
    StravaAPIError,
    StravaIngestionError,
)


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = MagicMock()
    return session


@pytest.fixture
def sample_webhook_event():
    """Create a sample webhook event."""
    event = MagicMock(spec=WebhookEvent)
    event.id = 1
    event.object_type = "activity"
    event.object_id = 123456
    event.aspect_type = "create"
    event.owner_id = 98765
    event.status = WebhookEventStatus.PENDING
    event.retry_count = 0
    return event


@pytest.fixture
def sample_user_athlete_link():
    """Create a sample user-athlete link."""
    link = MagicMock(spec=UserAthleteLink)
    link.user_id = "00000000-0000-0000-0000-000000000001"
    link.athlete_id = 98765
    return link


class TestProcessWebhookEvent:
    """Tests for process_webhook_event function."""

    @patch("src.services.webhook_processor_service._handle_activity_create")
    def test_process_activity_create_event(
        self,
        mock_handle_create,
        mock_session,
        sample_webhook_event,
        sample_user_athlete_link,
    ):
        """Test processing activity.create event."""
        # Setup
        mock_session.query.return_value.filter_by.return_value.first.return_value = (
            sample_webhook_event
        )
        mock_session.query.return_value.filter.return_value.first.return_value = (
            sample_user_athlete_link
        )
        mock_handle_create.return_value = True

        # Execute
        result = process_webhook_event(mock_session, 1)

        # Verify
        assert result is True
        mock_handle_create.assert_called_once()
        assert sample_webhook_event.status == WebhookEventStatus.PROCESSED
        mock_session.commit.assert_called()

    @patch("src.services.webhook_processor_service._handle_activity_update")
    def test_process_activity_update_event(
        self,
        mock_handle_update,
        mock_session,
        sample_webhook_event,
        sample_user_athlete_link,
    ):
        """Test processing activity.update event."""
        # Setup
        sample_webhook_event.aspect_type = "update"
        mock_session.query.return_value.filter_by.return_value.first.return_value = (
            sample_webhook_event
        )
        mock_session.query.return_value.filter.return_value.first.return_value = (
            sample_user_athlete_link
        )
        mock_handle_update.return_value = True

        # Execute
        result = process_webhook_event(mock_session, 1)

        # Verify
        assert result is True
        mock_handle_update.assert_called_once()

    @patch("src.services.webhook_processor_service._handle_activity_delete")
    def test_process_activity_delete_event(
        self,
        mock_handle_delete,
        mock_session,
        sample_webhook_event,
        sample_user_athlete_link,
    ):
        """Test processing activity.delete event."""
        # Setup
        sample_webhook_event.aspect_type = "delete"
        mock_session.query.return_value.filter_by.return_value.first.return_value = (
            sample_webhook_event
        )
        mock_session.query.return_value.filter.return_value.first.return_value = (
            sample_user_athlete_link
        )
        mock_handle_delete.return_value = True

        # Execute
        result = process_webhook_event(mock_session, 1)

        # Verify
        assert result is True
        mock_handle_delete.assert_called_once()

    def test_process_event_not_found(self, mock_session):
        """Test processing non-existent event."""
        # Setup
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Execute
        result = process_webhook_event(mock_session, 999)

        # Verify
        assert result is False
        mock_session.commit.assert_not_called()

    def test_process_event_no_user_athlete_link(
        self, mock_session, sample_webhook_event
    ):
        """Test processing event when user-athlete link doesn't exist."""
        # Setup
        mock_session.query.return_value.filter_by.return_value.first.return_value = (
            sample_webhook_event
        )
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Execute
        result = process_webhook_event(mock_session, 1)

        # Verify
        assert result is False
        assert sample_webhook_event.status == WebhookEventStatus.FAILED
        assert "No user-athlete link" in str(sample_webhook_event.error_message)

    def test_process_event_already_processed(self, mock_session, sample_webhook_event):
        """Test processing event that's already processed."""
        # Setup
        sample_webhook_event.status = WebhookEventStatus.PROCESSED
        mock_session.query.return_value.filter_by.return_value.first.return_value = (
            sample_webhook_event
        )

        # Execute
        result = process_webhook_event(mock_session, 1)

        # Verify
        assert result is True  # Already processed, return True

    @patch("src.services.webhook_processor_service._handle_activity_create")
    def test_process_event_handles_exception(
        self,
        mock_handle_create,
        mock_session,
        sample_webhook_event,
        sample_user_athlete_link,
    ):
        """Test processing event when handler raises exception."""
        # Setup
        mock_session.query.return_value.filter_by.return_value.first.return_value = (
            sample_webhook_event
        )
        mock_session.query.return_value.filter.return_value.first.return_value = (
            sample_user_athlete_link
        )
        mock_handle_create.side_effect = Exception("Test error")

        # Execute
        result = process_webhook_event(mock_session, 1)

        # Verify
        assert result is False
        assert sample_webhook_event.status == WebhookEventStatus.FAILED
        assert sample_webhook_event.retry_count == 1
        assert "Test error" in str(sample_webhook_event.error_message)
        mock_session.commit.assert_called()


class TestHandleActivityCreate:
    """Tests for _handle_activity_create function."""

    @patch("src.services.webhook_processor_service.get_valid_token")
    @patch("src.services.webhook_processor_service.StravaClient")
    @patch("src.services.webhook_processor_service.ActivityIngestionService")
    @patch("src.services.webhook_processor_service.enrich_one_activity_with_refresh")
    def test_handle_activity_create_success(
        self,
        mock_enrich,
        mock_service_class,
        mock_client_class,
        mock_get_token,
        mock_session,
        sample_webhook_event,
    ):
        """Test successful activity creation."""
        # Setup
        mock_get_token.return_value = "fake-token"
        mock_client = MagicMock()
        mock_client.get_activity.return_value = {
            "id": 123456,
            "type": "Run",
            "name": "Test Run",
            "distance": 5000,
            "external_id": "test.fit",
        }
        mock_client_class.return_value = mock_client
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # Execute
        result = _handle_activity_create(mock_session, sample_webhook_event, "user-123")

        # Verify
        assert result is True
        mock_client.get_activity.assert_called_once_with(123456)
        mock_service.ingest_specific.assert_called_once()

    @patch("src.services.webhook_processor_service.get_valid_token")
    def test_handle_activity_create_token_error(
        self, mock_get_token, mock_session, sample_webhook_event
    ):
        """Test activity creation when token retrieval fails."""
        # Setup
        mock_get_token.side_effect = StravaTokenError("Token not found", details={})

        # Execute
        result = _handle_activity_create(mock_session, sample_webhook_event, "user-123")

        # Verify
        assert result is False

    @patch("src.services.webhook_processor_service.get_valid_token")
    @patch("src.services.webhook_processor_service.StravaClient")
    def test_handle_activity_create_activity_not_found(
        self, mock_client_class, mock_get_token, mock_session, sample_webhook_event
    ):
        """Test activity creation when activity doesn't exist."""
        # Setup
        mock_get_token.return_value = "fake-token"
        mock_client = MagicMock()
        mock_client.get_activity.return_value = None
        mock_client_class.return_value = mock_client

        # Execute
        result = _handle_activity_create(mock_session, sample_webhook_event, "user-123")

        # Verify
        assert result is False

    @patch("src.services.webhook_processor_service.get_valid_token")
    @patch("src.services.webhook_processor_service.StravaClient")
    def test_handle_activity_create_api_error(
        self, mock_client_class, mock_get_token, mock_session, sample_webhook_event
    ):
        """Test activity creation when API call fails."""
        # Setup
        mock_get_token.return_value = "fake-token"
        mock_client = MagicMock()
        mock_client.get_activity.side_effect = StravaAPIError(
            "API error", status_code=500
        )
        mock_client_class.return_value = mock_client

        # Execute
        result = _handle_activity_create(mock_session, sample_webhook_event, "user-123")

        # Verify
        assert result is False


class TestHandleActivityUpdate:
    """Tests for _handle_activity_update function."""

    @patch("src.services.webhook_processor_service.get_valid_token")
    @patch("src.services.webhook_processor_service.enrich_one_activity_with_refresh")
    def test_handle_activity_update_success(
        self, mock_enrich, mock_get_token, mock_session, sample_webhook_event
    ):
        """Test successful activity update."""
        # Setup
        mock_get_token.return_value = "fake-token"
        mock_enrich.return_value = True

        # Mock activity exists
        mock_activity = MagicMock(spec=Activity)
        mock_session.query.return_value.filter_by.return_value.first.return_value = (
            mock_activity
        )

        # Execute
        result = _handle_activity_update(mock_session, sample_webhook_event, "user-123")

        # Verify
        assert result is True
        mock_enrich.assert_called_once()

    def test_handle_activity_update_activity_not_found(
        self, mock_session, sample_webhook_event
    ):
        """Test activity update when activity doesn't exist."""
        # Setup
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Execute
        result = _handle_activity_update(mock_session, sample_webhook_event, "user-123")

        # Verify
        assert result is False


class TestHandleActivityDelete:
    """Tests for _handle_activity_delete function."""

    def test_handle_activity_delete_success(self, mock_session, sample_webhook_event):
        """Test successful activity deletion."""
        # Setup
        mock_activity = MagicMock(spec=Activity)
        mock_session.query.return_value.filter_by.return_value.first.return_value = (
            mock_activity
        )

        # Execute
        result = _handle_activity_delete(mock_session, sample_webhook_event, "user-123")

        # Verify
        assert result is True
        mock_session.delete.assert_called_once_with(mock_activity)
        mock_session.commit.assert_called()

    def test_handle_activity_delete_activity_not_found(
        self, mock_session, sample_webhook_event
    ):
        """Test activity deletion when activity doesn't exist."""
        # Setup
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Execute
        result = _handle_activity_delete(mock_session, sample_webhook_event, "user-123")

        # Verify
        assert result is False
        mock_session.delete.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

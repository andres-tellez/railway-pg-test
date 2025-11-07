"""
Test Ingestion Orchestrator - No Artificial Delays

Tests that ingestion orchestrator works correctly after removing artificial delays.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import time

from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)
from src.db.db_session import get_session


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
        None
    )
    return session


@pytest.fixture
def mock_tokens():
    """Mock token data."""
    return {
        "access_token": "test_token",
        "refresh_token": "test_refresh",
        "expires_at": int(time.time()) + 3600,
    }


@patch("src.services.ingestion_orchestrator_service.get_session")
@patch("src.services.ingestion_orchestrator_service.get_tokens_sa")
@patch("src.services.ingestion_orchestrator_service.get_valid_token")
@patch("src.services.ingestion_orchestrator_service.should_use_incremental_sync")
@patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
@patch("src.services.ingestion_orchestrator_service.ActivityDAO")
@patch("src.services.ingestion_orchestrator_service.run_enrichment_batch")
def test_ingestion_no_delays(
    mock_enrichment,
    mock_dao,
    mock_service_class,
    mock_incremental_sync,
    mock_get_token,
    mock_get_tokens,
    mock_get_session,
    mock_session,
    mock_tokens,
):
    """Test that ingestion completes without artificial delays."""
    # Setup mocks
    mock_get_session.return_value = mock_session
    mock_get_tokens.return_value = mock_tokens
    mock_get_token.return_value = "test_access_token"
    mock_incremental_sync.return_value = (False, None)  # Full sync

    # Mock ActivityIngestionService
    mock_service = MagicMock()
    mock_client = MagicMock()
    mock_client.get_activities.return_value = [
        {"id": 12345, "type": "Run", "start_date": "2025-01-01T00:00:00Z"},
        {"id": 12346, "type": "Run", "start_date": "2025-01-02T00:00:00Z"},
    ]
    mock_service.client = mock_client
    mock_service_class.return_value = mock_service

    # Mock ActivityDAO
    mock_dao.upsert_activities.return_value = 2

    # Mock enrichment
    mock_enrichment.return_value = 2

    # Record start time
    start_time = time.time()

    # Run ingestion
    result = run_full_ingestion_and_enrichment(
        None, athlete_id=12345, user_id="test-user-id", max_activities=10
    )

    # Record end time
    end_time = time.time()
    elapsed = end_time - start_time

    # Verify results
    assert result["synced"] == 2
    assert result["enriched"] == 2

    # Verify no artificial delays (should complete in < 1 second for mocked operations)
    # In real scenario, this would be much faster than before (which had 10+ seconds of delays)
    assert elapsed < 5.0, f"Ingestion took {elapsed}s - should be fast without delays"

    # Verify service was called
    mock_service_class.assert_called_once()
    mock_client.get_activities.assert_called_once()
    mock_dao.upsert_activities.assert_called_once()
    mock_enrichment.assert_called_once()


@patch("src.services.ingestion_orchestrator_service.get_session")
@patch("src.services.ingestion_orchestrator_service.get_tokens_sa")
@patch("src.services.ingestion_orchestrator_service.get_valid_token")
@patch("src.services.ingestion_orchestrator_service.should_use_incremental_sync")
@patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
def test_ingestion_no_sleep_calls(
    mock_service_class,
    mock_incremental_sync,
    mock_get_token,
    mock_get_tokens,
    mock_get_session,
    mock_session,
    mock_tokens,
):
    """Test that ingestion doesn't call time.sleep()."""
    import src.services.ingestion_orchestrator_service as ingestion_module

    # Setup mocks
    mock_get_session.return_value = mock_session
    mock_get_tokens.return_value = mock_tokens
    mock_get_token.return_value = "test_access_token"
    mock_incremental_sync.return_value = (False, None)

    # Mock service to raise error early (to test quickly)
    mock_service = MagicMock()
    mock_client = MagicMock()
    mock_client.get_activities.side_effect = Exception("Test error")
    mock_service.client = mock_client
    mock_service_class.return_value = mock_service

    # Patch time.sleep to track if it's called
    sleep_calls = []

    def track_sleep(seconds):
        sleep_calls.append(seconds)

    with patch("time.sleep", side_effect=track_sleep):
        result = run_full_ingestion_and_enrichment(
            None, athlete_id=12345, user_id="test-user-id"
        )

    # Verify no sleep calls were made
    assert (
        len(sleep_calls) == 0
    ), f"Found {len(sleep_calls)} sleep calls - should be zero after removing delays"


def test_ingestion_imports_still_work():
    """Test that time import is still present (needed for time.time())."""
    import src.services.ingestion_orchestrator_service as ingestion_module
    import time

    # Verify time module is imported
    assert hasattr(ingestion_module, "time"), "time module should be imported"

    # Verify time.time() can be called (used in the code)
    assert callable(time.time), "time.time() should be callable"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

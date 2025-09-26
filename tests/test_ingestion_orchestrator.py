# tests/test_ingestion_orchestrator.py

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from src.services.ingestion_orchestrator_service import (
    ingest_specific_activity,
    ingest_between_dates,
)


@pytest.fixture
def session():
    """Mocked DB session fixture"""
    return MagicMock()


@patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
def test_ingest_specific_activity_not_found(mock_service, session):
    athlete_id = 123
    activity_id = 456

    mock_service_instance = mock_service.return_value
    mock_service_instance.client.get_activity.return_value = None

    result = ingest_specific_activity(session, athlete_id, activity_id)

    mock_service_instance.client.get_activity.assert_called_once_with(activity_id)
    assert result == 0


@patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
def test_ingest_between_dates_no_activities(mock_service, session):
    athlete_id = 123
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 1, 3)

    mock_service_instance = mock_service.return_value
    mock_service_instance.client.get_activities.return_value = []

    result = ingest_between_dates(session, athlete_id, start_date, end_date)

    mock_service_instance.client.get_activities.assert_called_once()
    assert result == 0

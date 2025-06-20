import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from src.services.ingestion_orchestrator_service import ingest_specific_activity, ingest_between_dates

@pytest.fixture
def session():
    # Return a mock or test DB session
    return MagicMock()

@patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
@patch("src.services.ingestion_orchestrator_service.ActivityDAO.upsert_activities")
@patch("src.services.ingestion_orchestrator_service.enrich_one_activity_with_refresh")
def test_ingest_specific_activity(mock_enrich, mock_upsert, mock_service, session):
    athlete_id = 123
    activity_id = 456

    mock_service_instance = mock_service.return_value
    mock_service_instance.client.get_activity.return_value = {"id": activity_id, "name": "Test Activity"}

    mock_upsert.return_value = 1
    mock_enrich.return_value = None

    result = ingest_specific_activity(session, athlete_id, activity_id)

    mock_service_instance.client.get_activity.assert_called_once_with(activity_id)
    mock_upsert.assert_called_once_with(session, athlete_id, [mock_service_instance.client.get_activity.return_value])
    mock_enrich.assert_called_once_with(session, athlete_id, activity_id)
    assert result == 1

@patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
@patch("src.services.ingestion_orchestrator_service.ActivityDAO.upsert_activities")
@patch("src.services.ingestion_orchestrator_service.enrich_one_activity_with_refresh")
def test_ingest_between_dates(mock_enrich, mock_upsert, mock_service, session):
    athlete_id = 123
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 1, 3)

    mock_service_instance = mock_service.return_value
    mock_service_instance.client.get_activities.return_value = [
        {"id": 1, "name": "A1"},
        {"id": 2, "name": "A2"}
    ]

    mock_upsert.return_value = 2
    mock_enrich.return_value = None

    result = ingest_between_dates(session, athlete_id, start_date, end_date, batch_size=1)

    mock_service_instance.client.get_activities.assert_called_once()
    mock_upsert.assert_called_once_with(session, athlete_id, mock_service_instance.client.get_activities.return_value)
    assert mock_enrich.call_count == 2
    assert result == 2

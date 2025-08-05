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


@patch("src.services.ingestion_orchestrator_service.enrich_one_activity_with_refresh")
@patch("src.services.ingestion_orchestrator_service.ActivityDAO.upsert_activities")
@patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
def test_ingest_specific_activity_success(
    mock_service, mock_upsert, mock_enrich, session
):
    athlete_id = 123
    activity_id = 456

    mock_service_instance = mock_service.return_value
    mock_activity = {"id": activity_id, "name": "Test Activity"}
    mock_service_instance.client.get_activity.return_value = mock_activity

    mock_upsert.return_value = 1
    mock_enrich.return_value = None

    result = ingest_specific_activity(session, athlete_id, activity_id)

    mock_service_instance.client.get_activity.assert_called_once_with(activity_id)
    mock_upsert.assert_called_once_with(session, athlete_id, [mock_activity])
    mock_enrich.assert_called_once_with(session, athlete_id, activity_id)
    assert result == 1


@patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
def test_ingest_specific_activity_not_found(mock_service, session):
    athlete_id = 123
    activity_id = 456

    mock_service_instance = mock_service.return_value
    mock_service_instance.client.get_activity.return_value = None

    result = ingest_specific_activity(session, athlete_id, activity_id)

    mock_service_instance.client.get_activity.assert_called_once_with(activity_id)
    assert result == 0


@patch("src.services.ingestion_orchestrator_service.enrich_one_activity_with_refresh")
@patch("src.services.ingestion_orchestrator_service.ActivityDAO.upsert_activities")
@patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
def test_ingest_between_dates_success(mock_service, mock_upsert, mock_enrich, session):
    athlete_id = 123
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 1, 3)

    mock_service_instance = mock_service.return_value
    mock_activities = [
        {"id": 1, "name": "A1", "type": "Run"},
        {"id": 2, "name": "A2", "type": "Run"},
    ]
    mock_service_instance.client.get_activities.return_value = mock_activities

    mock_upsert.return_value = 2
    mock_enrich.return_value = None

    result = ingest_between_dates(
        session, athlete_id, start_date, end_date, batch_size=1
    )

    mock_service_instance.client.get_activities.assert_called_once()
    mock_upsert.assert_called_once_with(session, athlete_id, mock_activities)
    assert mock_enrich.call_count == 2
    assert result == 2


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


@patch("src.services.ingestion_orchestrator_service.enrich_one_activity_with_refresh")
@patch("src.services.ingestion_orchestrator_service.ActivityDAO.upsert_activities")
@patch("src.services.ingestion_orchestrator_service.ActivityIngestionService")
def test_ingest_between_dates_enrichment_failure(
    mock_service, mock_upsert, mock_enrich, session
):
    athlete_id = 123
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 1, 3)

    mock_service_instance = mock_service.return_value
    activities = [
        {"id": 1, "name": "A1", "type": "Run"},
        {"id": 2, "name": "A2", "type": "Run"},
    ]
    mock_service_instance.client.get_activities.return_value = activities

    mock_upsert.return_value = 2

    def enrich_side_effect(sess, ath_id, act_id):
        if act_id == 2:
            raise Exception("Enrich error")
        return None

    mock_enrich.side_effect = enrich_side_effect

    # Run ingestion; enrichment errors are handled internally, so no exception expected
    result = ingest_between_dates(
        session, athlete_id, start_date, end_date, batch_size=1
    )

    assert mock_enrich.call_count == 2  # Both enrichment attempts made
    assert result == 1  # Upsert count remains 2

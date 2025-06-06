# tests/test_enrichment_retry_logic.py

import pytest
import time
from unittest.mock import patch, Mock
from src.db.db_session import get_session
from src.services.enrichment_sync import enrich_one_activity

@pytest.fixture
def dummy_activity_id():
    return 99999

@pytest.fixture
def dummy_athlete_id():
    return 42

@pytest.fixture
def dummy_access_token():
    return "test-access-token"

@patch("src.services.enrichment_sync.time.sleep", return_value=None)
@patch("src.services.enrichment_sync.requests.get")
def test_enrich_retries_on_429(mock_get, mock_sleep, dummy_activity_id, dummy_athlete_id, dummy_access_token):
    # Simulate: first call 429, then 200, then 200 for HR zones
    mock_response_429 = Mock(status_code=429, headers={"Retry-After": "0"})
    mock_response_200 = Mock(status_code=200)
    mock_response_200.json.return_value = {"id": dummy_activity_id}

    mock_get.side_effect = [mock_response_429, mock_response_200, mock_response_200]

    session = get_session()
    try:
        for attempt in range(2):
            result = enrich_one_activity(session, dummy_athlete_id, dummy_access_token, dummy_activity_id)
            if result:
                break
            time.sleep(1)

        assert result is True
        assert mock_get.call_count == 3
    finally:
        session.close()

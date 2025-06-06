# tests/test_enrichment_no_hr_zones.py

import pytest
from unittest.mock import patch, Mock
from src.services.enrichment_sync import fetch_hr_zone_percentages

@patch("src.services.enrichment_sync.requests.get")
def test_fetch_hr_zone_percentages_handles_missing_data(mock_get):
    # Strava responds without HR zones
    mock_response = Mock(status_code=200)
    mock_response.json.return_value = [{"type": "power"}]  # No heartrate zones

    mock_get.return_value = mock_response

    activity_id = 123456
    access_token = "test-access"

    result = fetch_hr_zone_percentages(activity_id, access_token)
    assert result is None  # correctly handled as None

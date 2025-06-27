from unittest.mock import patch, MagicMock
import pytest
import os

@pytest.fixture(scope="session", autouse=True)
def set_env_vars():
    os.environ["CRON_SECRET_KEY"] = "devkey123"



@patch("src.services.activity_service.StravaClient")
@patch("src.services.activity_service.get_valid_token", return_value="fake-token")
@patch("src.services.activity_service.run_enrichment_batch", return_value=1)
@patch("src.routes.activity_routes.ActivityIngestionService")
def test_sync_success(mock_ingestor, mock_enrich, mock_token, mock_strava, client):
    with patch("src.utils.config.CRON_SECRET_KEY", "devkey123"):
        instance = mock_ingestor.return_value
        instance.ingest_recent.return_value = 5
        mock_strava.return_value.get_activities.return_value = []

        resp = client.get("/sync/sync/123?key=devkey123")
        assert resp.status_code == 200
        assert resp.json == {"inserted": 5}

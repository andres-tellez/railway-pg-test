from unittest.mock import patch, MagicMock

@patch("src.services.activity_service.StravaClient")
@patch("src.services.activity_service.get_valid_token", return_value="fake-token")
@patch("src.services.activity_service.run_enrichment_batch", return_value=1)
@patch("src.routes.activity_routes.ActivityIngestionService")  # ✅ Patch from where it's used
def test_sync_success(mock_ingestor, mock_enrich, mock_token, mock_strava, client):
    instance = mock_ingestor.return_value
    instance.ingest_recent.return_value = 5
    mock_strava.return_value.get_activities.return_value = []

    resp = client.get("/sync/sync/123?key=devkey123")
    assert resp.status_code == 200
    assert resp.json == {"inserted": 5}

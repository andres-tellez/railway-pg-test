import pytest
from unittest.mock import patch, Mock

# ✅ This test uses normal (unpatched) client fixture
@pytest.mark.parametrize(
    "key,code",
    [
        ("wrong", 401),
        ("devkey123", 500),  # valid key but no tokens exist → causes ingestion to fail
    ],
)
def test_sync_auth_and_error(client, key, code):
    resp = client.get(f"/sync-strava-to-db/123?key={key}")
    expected_code = 401 if key == "wrong" else 500
    assert resp.status_code == expected_code


# ✅ Fully isolated test that mocks ingestion service directly
@patch("src.routes.sync_routes.ActivityIngestionService")
def test_sync_success(mock_ingestion_service, client):
    mock_instance = Mock()
    mock_instance.ingest_recent.return_value = 10
    mock_ingestion_service.return_value = mock_instance

    resp = client.get("/sync-strava-to-db/123?key=devkey123")
    assert resp.status_code == 200
    assert resp.get_json() == {"inserted": 10}

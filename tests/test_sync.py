import pytest
from unittest.mock import patch

@pytest.mark.parametrize(
    "key,code",
    [
        ("wrong", 401),
        ("devkey123", 401),  # when no tokens exist
    ],
)
def test_sync_auth_and_error(client, key, code):
    resp = client.get(f"/sync-strava-to-db/123?key={key}")
    assert resp.status_code == code

@patch("src.routes.sync_routes.sync_recent")
@patch("src.routes.sync_routes.ensure_fresh_access_token")
def test_sync_success(mock_ensure_fresh_access_token, mock_sync_recent, monkeypatch, client):
    # ✅ Set CRON_SECRET_KEY for authorization
    monkeypatch.setenv("CRON_SECRET_KEY", "devkey123")

    # ✅ Mock ensure_fresh_access_token to avoid real DB lookup
    mock_ensure_fresh_access_token.return_value = "mock-token"

    # ✅ Mock sync_recent to avoid real Strava API call
    mock_sync_recent.return_value = 10

    resp = client.get("/sync-strava-to-db/123?key=devkey123")
    assert resp.status_code == 200
    assert resp.get_json() == {"synced": 10}

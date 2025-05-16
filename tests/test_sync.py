# tests/test_sync.py
import pytest
from unittest.mock import patch


@pytest.mark.parametrize(
    "key,code",
    [
        ("wrong", 401),
        ("test-cron-key", 500),  # no schema yet triggers JSON error, not crash
    ],
)
def test_sync_auth_and_error(client, key, code):
    resp = client.get(f"/sync-strava-to-db/123?key={key}")
    assert resp.status_code == code


def test_sync_success(monkeypatch, client):
    # Stub out get_valid_access_token
    monkeypatch.setenv("CRON_SECRET_KEY", "test-cron-key")
    monkeypatch.setattr(
        "src.routes.sync_routes.get_valid_access_token", lambda athlete_id: "fake-token"
    )

    # Stub out HTTP to Strava entirely
    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: type("R", (), {"status_code": 200, "json": lambda: []}),
    )
    # Now your sync_recent_activities will see an empty list and return 0
    resp = client.get("/sync-strava-to-db/123?key=test-cron-key")
    assert resp.status_code == 200
    assert resp.get_json() == {"synced": 0}

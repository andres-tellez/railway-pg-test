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
    monkeypatch.setenv("CRON_SECRET_KEY", "test-cron-key")
    # stub out internals
    monkeypatch.setattr(
        "src.routes.sync_routes.get_valid_access_token", lambda x: "tok"
    )
    monkeypatch.setattr(
        "src.services.activity_sync.sync_recent_activities", lambda a, t: 2
    )
    resp = client.get("/sync-strava-to-db/123?key=test-cron-key")
    assert resp.status_code == 200
    assert resp.get_json() == {"synced": 2}

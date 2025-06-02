# tests/test_sync.py

import pytest

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

def test_sync_success(monkeypatch, client):
    # ✅ Set CRON_SECRET_KEY for authorization
    monkeypatch.setenv("CRON_SECRET_KEY", "devkey123")

    # ✅ Patch token DAO directly — this fully bypasses session
    monkeypatch.setattr(
        "src.routes.sync_routes.get_valid_access_token_sa",
        lambda session, athlete_id: "fake-token"
    )

    # ✅ Patch sync_recent_activities directly — no need to patch get_session
    monkeypatch.setattr(
        "src.routes.sync_routes.sync_recent_activities",
        lambda session, athlete_id, access_token: 0
    )

    resp = client.get("/sync-strava-to-db/123?key=devkey123")
    assert resp.status_code == 200
    assert resp.get_json() == {"synced": 0}

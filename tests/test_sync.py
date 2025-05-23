# tests/test_sync.py
import pytest

@pytest.mark.parametrize(
    "key,code",
    [
        ("wrong", 401),
        ("devkey123", 500),  # schema exists, but we'll simulate empty sync
    ],
)
def test_sync_auth_and_error(client, key, code):
    resp = client.get(f"/sync-strava-to-db/123?key={key}")
    assert resp.status_code == code

def test_sync_success(monkeypatch, client):
    # Match the CRON_SECRET_KEY expected by route
    monkeypatch.setenv("CRON_SECRET_KEY", "devkey123")

    # Mock token retrieval
    monkeypatch.setattr(
        "src.routes.sync_routes.get_valid_access_token", lambda athlete_id: "fake-token"
    )

    # Mock Strava API call to return empty activity list
    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: type("R", (), {
            "status_code": 200,
            "json": staticmethod(lambda: [])
        })(),
    )

    resp = client.get("/sync-strava-to-db/123?key=devkey123")
    assert resp.status_code == 200
    assert resp.get_json() == {"synced": 0}

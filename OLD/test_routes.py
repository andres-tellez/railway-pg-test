# tests/test_routes.py

from unittest.mock import patch

def test_auth_login(client):
    payload = {"username": "foo", "password": "bar"}

    # Patch the function as imported in the auth blueprint
    with patch("src.routes.auth.login_user") as login_user:
        login_user.return_value = ("tokA", "tokR")
        resp = client.post("/auth/login", json=payload)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"access_token": "tokA", "refresh_token": "tokR"}


def test_enrich_status(client):
    resp = client.get("/enrich/status")
    assert resp.status_code == 200
    assert resp.get_json() == {"enrich": "up"}


def test_enrich_single(client):
    # Patch the function as imported in the enrich blueprint
    with patch("src.routes.enrich.enrich_activity") as enrich_activity:
        enrich_activity.return_value = {"id": 123, "foo": "bar"}
        resp = client.post("/enrich/activity/123")

    assert resp.status_code == 200
    assert resp.get_json() == {"id": 123, "foo": "bar"}


def test_backfill(client):
    # Patch the backfill stub
    with patch("src.routes.enrich.backfill_activities") as backfill:
        backfill.return_value = 42
        resp = client.post("/enrich/backfill")

    assert resp.status_code == 200
    assert resp.get_json() == {"backfilled": 42}

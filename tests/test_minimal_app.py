# tests/test_minimal_app.py
import os
import json
import pytest

# Ensure we load the real .env for DATABASE_URL, STRAVA_CLIENT_*, etc.
from dotenv import load_dotenv
load_dotenv()

from minimal_app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()

def test_ping(client):
    res = client.get("/ping")
    assert res.status_code == 200
    assert res.data == b"pong"

def test_connect_strava_redirect(client):
    # Assumes STRAVA_CLIENT_ID is set in .env
    res = client.get("/connect-strava")
    assert res.status_code == 302
    loc = res.headers["Location"]
    assert "strava.com/oauth/authorize" in loc
    assert f"client_id={os.getenv('STRAVA_CLIENT_ID')}" in loc

def test_oauth_callback_missing_code(client):
    res = client.get("/oauth/callback")
    assert res.status_code == 400
    assert res.get_json() == {"error": "Missing code"}

def test_enrich_unauthorized(client):
    # calling enrich without key
    res = client.get("/enrich-activities/1")
    assert res.status_code == 401
    assert res.get_json() == {"error": "Unauthorized"}

def test_enrich_lookup_error(monkeypatch, client):
    # stub out enrich_batch to throw LookupError
    from services.activity_enrichment import enrich_batch
    monkeypatch.setattr(
        "services.activity_enrichment.enrich_batch",
        lambda *args, **kwargs: (_ for _ in ()).throw(LookupError())
    )
    # provide a valid key
    key = os.getenv("CRON_SECRET_KEY") or "no-secret"
    res = client.get(f"/enrich-activities/999?key={key}")
    assert res.status_code == 404
    assert res.get_json() == {"error": "No tokens for that athlete"}

def test_enrich_happy_path(monkeypatch, client):
    # stub enrich_batch to return fixed values
    monkeypatch.setenv("CRON_SECRET_KEY", "abc123")
    def fake_batch(aid, key, limit, offset, cid, cs):
        return (2, 5, offset + limit)
    monkeypatch.setattr(
        "services.activity_enrichment.enrich_batch",
        fake_batch
    )
    res = client.get("/enrich-activities/42?key=abc123&limit=5&offset=0")
    assert res.status_code == 200
    assert res.get_json() == {"enriched": 2, "processed": 5, "offset": 5}

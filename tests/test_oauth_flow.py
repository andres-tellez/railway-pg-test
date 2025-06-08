import pytest
from unittest.mock import patch, Mock
import requests

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("STRAVA_CLIENT_ID", "12345")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("REDIRECT_URI", "http://localhost/oauth/callback")

@patch("src.routes.oauth.ActivityIngestionService")
@patch("requests.post")
def test_oauth_callback_success(mock_post, mock_ingestion_service, client, sqlalchemy_session):
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "athlete": {"id": 999},
        "access_token": "access_token_value",
        "refresh_token": "refresh_token_value",
        "expires_at": 9999999999
    }
    mock_post.return_value = mock_response

    mock_instance = mock_ingestion_service.return_value
    mock_instance.ingest_full_history.return_value = 10

    resp = client.get("/oauth/callback?code=fakecode")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "message" in data
    assert "OAuth success" in data["message"]

def test_oauth_callback_missing_code(client):
    resp = client.get("/oauth/callback")
    assert resp.status_code == 400
    assert "error" in resp.get_json()

@patch("requests.post")
def test_oauth_callback_strava_http_error(mock_post, client):
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Strava error")
    mock_response.text = "Bad Request"
    mock_post.return_value = mock_response

    resp = client.get("/oauth/callback?code=badcode")
    assert resp.status_code == 502
    assert "error" in resp.get_json()

@patch("requests.post")
def test_oauth_callback_incomplete_response(mock_post, client):
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"athlete": {}}
    mock_post.return_value = mock_response

    resp = client.get("/oauth/callback?code=incomplete")
    assert resp.status_code == 502
    assert "error" in resp.get_json()

def test_oauth_callback_missing_env(monkeypatch, client):
    monkeypatch.delenv("STRAVA_CLIENT_ID", raising=False)
    monkeypatch.delenv("STRAVA_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("REDIRECT_URI", raising=False)

    resp = client.get("/oauth/callback?code=fakecode")
    assert resp.status_code == 500
    assert "error" in resp.get_json()

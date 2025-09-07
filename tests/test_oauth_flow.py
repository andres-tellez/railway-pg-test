import os
import requests
from unittest.mock import patch, Mock


def test_oauth_callback_missing_code(client):
    resp = client.get("/auth/callback")
    assert resp.status_code == 400


@patch("requests.post")
def test_oauth_callback_strava_http_error(mock_post, client):
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "Strava error"
    )
    mock_response.text = "Bad Request"
    mock_post.return_value = mock_response

    resp = client.get("/auth/callback?code=badcode")
    assert resp.status_code == 502


@patch("requests.post")
def test_oauth_callback_incomplete_response(mock_post, client):
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"athlete": {}}  # Simulates missing athlete_id
    mock_post.return_value = mock_response

    resp = client.get("/auth/callback?code=incomplete")
    assert resp.status_code == 500


def test_oauth_callback_missing_env(monkeypatch, client):
    monkeypatch.delenv("STRAVA_CLIENT_ID", raising=False)
    monkeypatch.delenv("STRAVA_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("REDIRECT_URI", raising=False)

    resp = client.get("/auth/callback?code=fakecode")
    assert resp.status_code == 502

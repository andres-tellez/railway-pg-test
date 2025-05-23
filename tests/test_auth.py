# tests/test_auth.py

import os
import time
import pytest


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASS", "secret")
    monkeypatch.setenv("SECRET_KEY", "testsecret")


def test_login_refresh_logout(client):
    """Test successful login, token refresh, and logout flow."""
    resp = client.post("/auth/login", json={"username": "admin", "password": "secret"})
    assert resp.status_code == 200
    tokens = resp.get_json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    time.sleep(1)  # Ensure new token gets a different timestamp

    resp = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    new_access = resp.get_json()["access_token"]
    assert new_access != tokens["access_token"]

    resp = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    assert resp.get_json()["message"] == "logged out"


def test_invalid_login_rejected(client):
    """Test that invalid credentials are rejected."""
    resp = client.post("/auth/login", json={"username": "wrong", "password": "bad"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_invalid_refresh_token(client):
    """Test that an invalid refresh token is rejected."""
    resp = client.post("/auth/refresh", json={"refresh_token": "not.a.real.token"})
    assert resp.status_code == 401
    assert "error" in resp.get_json()

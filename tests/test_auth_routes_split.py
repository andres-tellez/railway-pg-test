"""
Tests for auth routes after split.

Tests that all authentication endpoints are accessible and respond correctly.
"""

import pytest
from flask import Flask
from src.app import create_app


@pytest.fixture
def app():
    """Create Flask app for testing."""
    return create_app(test_config={"TESTING": True})


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def test_auth0_login_callback_missing_token(client):
    """Test Auth0 login callback with missing token."""
    response = client.post("/auth/login/callback", json={})

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "status" in data
    assert data["status"] == 400


def test_strava_login_redirect_missing_config(client):
    """Test Strava login redirect (may fail without config, but should handle gracefully)."""
    response = client.get("/auth/strava-login")

    # Should either redirect or return error, but not crash
    assert response.status_code in [302, 500, 400]


def test_strava_callback_missing_params(client):
    """Test Strava callback with missing parameters."""
    response = client.get("/auth/strava/callback")

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "status" in data
    assert data["status"] == 400


def test_strava_callback_post_missing_params(client):
    """Test Strava callback POST with missing parameters."""
    response = client.post("/auth/strava/callback", json={})

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "status" in data
    assert data["status"] == 400


def test_token_refresh_unauthorized(client):
    """Test token refresh without auth."""
    response = client.post("/auth/refresh/123")

    assert response.status_code == 401
    data = response.get_json()
    assert "error" in data
    assert "status" in data
    assert data["status"] == 401


def test_logout_endpoint_exists(client):
    """Test logout endpoint exists (may fail without auth, but endpoint should exist)."""
    response = client.post("/auth/logout/123")

    # Should return some response (not 404)
    assert response.status_code != 404


def test_debug_set_endpoint(client):
    """Test debug set endpoint."""
    response = client.get("/auth/debug/set")

    assert response.status_code == 200
    data = response.get_json()
    assert "status" in data
    assert data["status"] == 200


def test_debug_show_endpoint(client):
    """Test debug show endpoint."""
    response = client.get("/auth/debug/show")

    assert response.status_code == 200
    data = response.get_json()
    assert "status" in data
    assert data["status"] == 200


def test_monitor_tokens_endpoint(client):
    """Test monitor tokens endpoint."""
    response = client.get("/auth/monitor-tokens")

    # Should return 200 (even if empty list) or 500 (if DB error)
    assert response.status_code in [200, 500]


def test_all_auth_routes_registered(app):
    """Test that all expected auth routes are registered."""
    routes = [str(rule) for rule in app.url_map.iter_rules() if "auth" in str(rule)]

    expected_routes = [
        "/auth/callback",
        "/auth/debug/set",
        "/auth/debug/show",
        "/auth/login/callback",
        "/auth/logout/<int:athlete_id>",
        "/auth/monitor-tokens",
        "/auth/refresh/<int:athlete_id>",
        "/auth/strava-login",
        "/auth/strava/callback",
        "/auth/strava/connect",
    ]

    for expected in expected_routes:
        # Check if route exists (with or without angle brackets)
        found = any(
            expected.replace("<int:athlete_id>", "") in r or expected in r
            for r in routes
        )
        assert found, f"Route {expected} not found. Found routes: {routes}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

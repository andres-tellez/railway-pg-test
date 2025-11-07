"""
Tests for authentication rate limiter.

Tests rate limiting functionality for auth endpoints.
"""

import pytest
import time
from flask import Flask
from src.utils.auth_rate_limiter import (
    rate_limit_auth,
    reset_rate_limits,
    get_rate_limit_stats,
)


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def cleanup():
    """Cleanup rate limits after each test."""
    yield
    reset_rate_limits()


def test_rate_limit_allows_requests(app, client, cleanup):
    """Test that requests within limit are allowed."""

    @app.route("/test-endpoint")
    @rate_limit_auth("general")
    def test_route():
        return {"status": "ok"}, 200

    # Make requests within limit (20 per 5 minutes)
    for i in range(5):
        response = client.get("/test-endpoint")
        assert response.status_code == 200


def test_rate_limit_blocks_exceeding_requests(app, client, cleanup):
    """Test that exceeding rate limit returns 429."""

    @app.route("/test-endpoint")
    @rate_limit_auth("login")  # 10 per 5 minutes
    def test_route():
        return {"status": "ok"}, 200

    # Make requests up to limit
    for i in range(10):
        response = client.get("/test-endpoint")
        assert response.status_code == 200

    # Next request should be blocked
    response = client.get("/test-endpoint")
    assert response.status_code == 429
    data = response.get_json()
    assert data["error_code"] == "RATE_LIMIT_EXCEEDED"
    assert "retry_after_seconds" in data


def test_rate_limit_reset(app, client, cleanup):
    """Test that rate limits can be reset."""

    @app.route("/test-endpoint")
    @rate_limit_auth("login")
    def test_route():
        return {"status": "ok"}, 200

    # Make requests up to limit
    for i in range(10):
        response = client.get("/test-endpoint")
        assert response.status_code == 200

    # Should be blocked
    response = client.get("/test-endpoint")
    assert response.status_code == 429

    # Reset limits
    reset_rate_limits()

    # Should work again
    response = client.get("/test-endpoint")
    assert response.status_code == 200


def test_rate_limit_stats(app, client, cleanup):
    """Test that rate limit stats can be retrieved."""

    @app.route("/test-endpoint")
    @rate_limit_auth("general")
    def test_route():
        return {"status": "ok"}, 200

    # Make some requests
    for i in range(3):
        client.get("/test-endpoint")

    # Get stats
    stats = get_rate_limit_stats()
    assert len(stats) > 0
    # Stats should contain request counts
    for ident, stat in stats.items():
        assert "request_count" in stat


def test_different_rate_limit_types(app, client, cleanup):
    """Test that different rate limit types have separate limits."""

    @app.route("/login")
    @rate_limit_auth("login")  # 10 per 5 minutes
    def login():
        return {"status": "ok"}, 200

    @app.route("/refresh")
    @rate_limit_auth("token_refresh")  # 30 per 15 minutes
    def refresh():
        return {"status": "ok"}, 200

    # Exhaust login limit
    for i in range(10):
        response = client.get("/login")
        assert response.status_code == 200

    # Login should be blocked
    response = client.get("/login")
    assert response.status_code == 429

    # But refresh should still work (different limit)
    response = client.get("/refresh")
    assert response.status_code == 200

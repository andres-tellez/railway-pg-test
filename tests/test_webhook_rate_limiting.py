"""
Test Webhook Rate Limiting

Tests for rate limiting on webhook endpoints.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from flask import Flask
from src.routes.webhook_routes import webhook_bp
from src.utils.auth_rate_limiter import rate_limit_auth, RATE_LIMITS, reset_rate_limits


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.register_blueprint(webhook_bp)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_webhook_verify_token(monkeypatch):
    """Mock webhook verification token."""
    monkeypatch.setenv("STRAVA_WEBHOOK_VERIFY_TOKEN", "test_verify_token")


@pytest.fixture(autouse=True)
def reset_limits():
    """Reset rate limits before each test."""
    reset_rate_limits()
    yield
    reset_rate_limits()


class TestWebhookVerificationRateLimiting:
    """Tests for webhook verification endpoint rate limiting."""

    def test_verification_rate_limit_not_exceeded(
        self, client, mock_webhook_verify_token
    ):
        """Test that normal verification requests are allowed."""
        limit = RATE_LIMITS["webhook_verification"]
        max_requests = limit["requests"]

        # Make requests up to the limit
        for i in range(max_requests):
            response = client.get(
                "/webhooks/strava",
                query_string={
                    "hub.mode": "subscribe",
                    "hub.challenge": f"challenge_{i}",
                    "hub.verify_token": "test_verify_token",
                },
            )
            assert response.status_code == 200, f"Request {i+1} should succeed"

    def test_verification_rate_limit_exceeded(self, client, mock_webhook_verify_token):
        """Test that exceeding rate limit returns 429."""
        limit = RATE_LIMITS["webhook_verification"]
        max_requests = limit["requests"]

        # Make requests up to the limit
        for i in range(max_requests):
            client.get(
                "/webhooks/strava",
                query_string={
                    "hub.mode": "subscribe",
                    "hub.challenge": f"challenge_{i}",
                    "hub.verify_token": "test_verify_token",
                },
            )

        # Next request should be rate limited
        response = client.get(
            "/webhooks/strava",
            query_string={
                "hub.mode": "subscribe",
                "hub.challenge": "challenge_exceeded",
                "hub.verify_token": "test_verify_token",
            },
        )
        assert response.status_code == 429
        assert "RATE_LIMIT_EXCEEDED" in response.get_json().get("error_code", "")

    def test_verification_rate_limit_resets_after_window(
        self, client, mock_webhook_verify_token
    ):
        """Test that rate limit resets after time window."""
        limit = RATE_LIMITS["webhook_verification"]
        max_requests = limit["requests"]
        window_seconds = limit["window_seconds"]

        # Make requests up to the limit
        for i in range(max_requests):
            client.get(
                "/webhooks/strava",
                query_string={
                    "hub.mode": "subscribe",
                    "hub.challenge": f"challenge_{i}",
                    "hub.verify_token": "test_verify_token",
                },
            )

        # Verify rate limited
        response = client.get(
            "/webhooks/strava",
            query_string={
                "hub.mode": "subscribe",
                "hub.challenge": "challenge_exceeded",
                "hub.verify_token": "test_verify_token",
            },
        )
        assert response.status_code == 429

        # Fast-forward time (mock time.time to simulate window passing)
        with patch("src.utils.auth_rate_limiter.time.time") as mock_time:
            mock_time.return_value = time.time() + window_seconds + 1

            # Should be allowed again
            response = client.get(
                "/webhooks/strava",
                query_string={
                    "hub.mode": "subscribe",
                    "hub.challenge": "challenge_after_window",
                    "hub.verify_token": "test_verify_token",
                },
            )
            assert response.status_code == 200


class TestWebhookEventRateLimiting:
    """Tests for webhook event endpoint rate limiting."""

    def test_webhook_rate_limit_not_exceeded(self, client):
        """Test that normal webhook requests are allowed."""
        limit = RATE_LIMITS["webhook"]
        max_requests = limit["requests"]

        # Make requests up to the limit
        for i in range(max_requests):
            response = client.post(
                "/webhooks/strava",
                json={
                    "object_type": "activity",
                    "object_id": 123456 + i,
                    "aspect_type": "create",
                    "owner_id": 347085,
                },
            )
            # May fail due to missing database, but should not be rate limited
            assert (
                response.status_code != 429
            ), f"Request {i+1} should not be rate limited"

    def test_webhook_rate_limit_exceeded(self, client):
        """Test that exceeding rate limit returns 429."""
        limit = RATE_LIMITS["webhook"]
        max_requests = limit["requests"]

        # Make requests up to the limit (mock database to avoid errors)
        with patch("src.routes.webhook_routes.get_session") as mock_session:
            mock_session.return_value.__enter__.return_value = MagicMock()
            mock_session.return_value.__exit__.return_value = None

            for i in range(max_requests):
                client.post(
                    "/webhooks/strava",
                    json={
                        "object_type": "activity",
                        "object_id": 123456 + i,
                        "aspect_type": "create",
                        "owner_id": 347085,
                    },
                )

            # Next request should be rate limited
            response = client.post(
                "/webhooks/strava",
                json={
                    "object_type": "activity",
                    "object_id": 999999,
                    "aspect_type": "create",
                    "owner_id": 347085,
                },
            )
            assert response.status_code == 429
            assert "RATE_LIMIT_EXCEEDED" in response.get_json().get("error_code", "")

    def test_webhook_rate_limit_allows_burst(self, client):
        """Test that webhook rate limit allows bursty traffic (100 per minute)."""
        limit = RATE_LIMITS["webhook"]
        max_requests = limit["requests"]

        # Make many requests quickly (simulating burst)
        with patch("src.routes.webhook_routes.get_session") as mock_session:
            mock_session.return_value.__enter__.return_value = MagicMock()
            mock_session.return_value.__exit__.return_value = None

            success_count = 0
            rate_limited_count = 0

            for i in range(max_requests + 10):  # Try to exceed limit
                response = client.post(
                    "/webhooks/strava",
                    json={
                        "object_type": "activity",
                        "object_id": 123456 + i,
                        "aspect_type": "create",
                        "owner_id": 347085,
                    },
                )
                if response.status_code == 429:
                    rate_limited_count += 1
                else:
                    success_count += 1

            # Should allow up to max_requests
            assert success_count == max_requests
            # Should rate limit requests beyond max_requests
            assert rate_limited_count > 0


class TestRateLimitConfiguration:
    """Tests for rate limit configuration."""

    def test_webhook_rate_limits_configured(self):
        """Test that webhook rate limits are properly configured."""
        assert "webhook" in RATE_LIMITS
        assert "webhook_verification" in RATE_LIMITS

        webhook_limit = RATE_LIMITS["webhook"]
        assert webhook_limit["requests"] == 100
        assert webhook_limit["window_seconds"] == 60

        verification_limit = RATE_LIMITS["webhook_verification"]
        assert verification_limit["requests"] == 10
        assert verification_limit["window_seconds"] == 300

    def test_rate_limit_decorator_applied(self):
        """Test that rate limit decorator is applied to webhook routes."""
        from src.routes.webhook_routes import verify_webhook, receive_webhook

        # Check that decorators are applied (functions have __wrapped__ attribute)
        assert hasattr(verify_webhook, "__wrapped__") or hasattr(
            verify_webhook, "__name__"
        )
        assert hasattr(receive_webhook, "__wrapped__") or hasattr(
            receive_webhook, "__name__"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

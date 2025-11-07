"""
Comprehensive Error Scenario Tests for Strava Routes

Tests for error handling in Strava OAuth and connection routes.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from src.routes.strava_routes import strava_bp, strava_connection_bp
from src.utils.strava_exceptions import (
    StravaOAuthCodeExchangeError,
    StravaTokenError,
    StravaTokenNotFoundError,
    StravaTokenRefreshError,
    StravaAPIError,
)


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.register_blueprint(strava_bp)
    app.register_blueprint(strava_connection_bp)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("STRAVA_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("STRAVA_REDIRECT_URI", "https://localhost:5000/auth/callback")
    monkeypatch.setenv("FRONTEND_REDIRECT", "https://localhost:5173/setup")


class TestStravaCallbackErrorScenarios:
    """Tests for error scenarios in OAuth callback handling."""

    @patch("src.routes.strava_routes.process_strava_callback")
    @patch("src.routes.strava_routes.validate_state_token")
    @patch("src.routes.strava_routes.get_session")
    def test_oauth_code_exchange_error(
        self, mock_get_session, mock_validate_state, mock_process, client, mock_env_vars
    ):
        """Test that OAuth code exchange errors return safe error messages."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_validate_state.return_value = (True, None)
        mock_process.side_effect = StravaOAuthCodeExchangeError(
            reason="Invalid code", message="Failed to exchange OAuth code"
        )

        response = client.get(
            "/auth/strava/callback",
            query_string={"code": "test_code", "state": "test_state"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data or "message" in data
        # Verify error message is safe (doesn't leak internal details)
        error_msg = data.get("error") or data.get("message", "")
        assert "database" not in error_msg.lower()
        assert "file" not in error_msg.lower()
        assert "traceback" not in error_msg.lower()

    @patch("src.routes.strava_routes.process_strava_callback")
    @patch("src.routes.strava_routes.validate_state_token")
    @patch("src.routes.strava_routes.get_session")
    def test_token_not_found_error(
        self, mock_get_session, mock_validate_state, mock_process, client, mock_env_vars
    ):
        """Test that token not found errors return safe error messages."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_validate_state.return_value = (True, None)
        mock_process.side_effect = StravaTokenNotFoundError(athlete_id=12345)

        response = client.get(
            "/auth/strava/callback",
            query_string={"code": "test_code", "state": "test_state"},
        )

        assert response.status_code == 400
        data = response.get_json()
        # Error message should be sanitized
        error_msg = data.get("error") or data.get("message", "")
        assert "authentication" in error_msg.lower() or "token" in error_msg.lower()

    @patch("src.routes.strava_routes.process_strava_callback")
    @patch("src.routes.strava_routes.validate_state_token")
    @patch("src.routes.strava_routes.get_session")
    def test_token_refresh_error(
        self, mock_get_session, mock_validate_state, mock_process, client, mock_env_vars
    ):
        """Test that token refresh errors return safe error messages."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_validate_state.return_value = (True, None)
        mock_process.side_effect = StravaTokenRefreshError(
            athlete_id=12345, reason="Network timeout"
        )

        response = client.get(
            "/auth/strava/callback",
            query_string={"code": "test_code", "state": "test_state"},
        )

        assert response.status_code == 400
        data = response.get_json()
        # Error message should be sanitized
        error_msg = data.get("error") or data.get("message", "")
        assert "authentication" in error_msg.lower() or "token" in error_msg.lower()

    @patch("src.routes.strava_routes.process_strava_callback")
    @patch("src.routes.strava_routes.validate_state_token")
    @patch("src.routes.strava_routes.get_session")
    def test_api_error_returns_500(
        self, mock_get_session, mock_validate_state, mock_process, client, mock_env_vars
    ):
        """Test that API errors return 500 status code."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_validate_state.return_value = (True, None)
        mock_process.side_effect = StravaAPIError("API request failed", status_code=500)

        response = client.get(
            "/auth/strava/callback",
            query_string={"code": "test_code", "state": "test_state"},
        )

        assert response.status_code == 500
        data = response.get_json()
        # Error message should be safe
        error_msg = data.get("error") or data.get("message", "")
        assert "internal" in error_msg.lower() or "error" in error_msg.lower()

    @patch("src.routes.strava_routes.process_strava_callback")
    @patch("src.routes.strava_routes.validate_state_token")
    @patch("src.routes.strava_routes.get_session")
    def test_generic_exception_returns_safe_message(
        self, mock_get_session, mock_validate_state, mock_process, client, mock_env_vars
    ):
        """Test that generic exceptions return safe error messages."""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_validate_state.return_value = (True, None)
        mock_process.side_effect = Exception(
            "Database connection failed: postgresql://user:password@host/db"
        )

        response = client.get(
            "/auth/strava/callback",
            query_string={"code": "test_code", "state": "test_state"},
        )

        assert response.status_code == 500
        data = response.get_json()
        error_msg = data.get("error") or data.get("message", "")
        # Verify no sensitive information leaked
        assert "postgresql://" not in error_msg
        assert "password" not in error_msg
        assert "database connection failed" not in error_msg.lower()


class TestStravaCallbackPOSTErrorScenarios:
    """Tests for error scenarios in POST callback handling."""

    @patch("src.routes.strava_routes.process_strava_callback")
    @patch("src.routes.strava_routes.get_session")
    def test_post_oauth_code_exchange_error(
        self, mock_get_session, mock_process, client, mock_env_vars
    ):
        """Test that POST OAuth code exchange errors return safe messages."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_get_session.return_value.__exit__.return_value = None
        mock_process.side_effect = StravaOAuthCodeExchangeError(
            reason="Invalid code", message="Failed to exchange OAuth code"
        )

        response = client.post(
            "/auth/strava/callback", json={"code": "test_code", "sub": "auth0|123"}
        )

        assert response.status_code == 400
        data = response.get_json()
        # Verify error message is safe
        error_msg = data.get("error") or data.get("message", "")
        assert "database" not in error_msg.lower()
        assert "file" not in error_msg.lower()

    @patch("src.routes.strava_routes.process_strava_callback")
    @patch("src.routes.strava_routes.get_session")
    def test_post_missing_code(
        self, mock_get_session, mock_process, client, mock_env_vars
    ):
        """Test that missing code returns validation error."""
        response = client.post("/auth/strava/callback", json={"sub": "auth0|123"})

        assert response.status_code == 400
        data = response.get_json()
        assert "code" in str(data).lower() or "required" in str(data).lower()

    @patch("src.routes.strava_routes.process_strava_callback")
    @patch("src.routes.strava_routes.get_session")
    def test_post_missing_sub(
        self, mock_get_session, mock_process, client, mock_env_vars
    ):
        """Test that missing sub returns validation error."""
        response = client.post("/auth/strava/callback", json={"code": "test_code"})

        assert response.status_code == 400
        data = response.get_json()
        assert "sub" in str(data).lower() or "required" in str(data).lower()


class TestStravaConnectionErrorScenarios:
    """Tests for error scenarios in connection management routes."""

    @patch("src.routes.strava_routes.get_authenticated_user_with_athlete")
    def test_disconnect_no_athlete_link(self, mock_get_user_athlete, client):
        """Test that disconnecting without athlete link returns 404."""
        from src.utils.response_utils import not_found_response

        mock_get_user_athlete.return_value = (
            "user_id",
            None,
            not_found_response("Strava connection"),
        )

        response = client.delete("/api/strava/disconnect")

        assert response.status_code == 404

    @patch("src.routes.strava_routes.get_authenticated_user_id")
    def test_status_no_authentication(self, mock_get_user_id, client):
        """Test that status check without authentication returns 401."""
        from src.utils.response_utils import unauthorized_response

        mock_get_user_id.return_value = (None, unauthorized_response())

        response = client.get("/api/strava/status")

        assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

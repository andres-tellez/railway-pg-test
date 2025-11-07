"""
Test Strava Routes

Comprehensive tests for Strava OAuth and connection management routes.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from flask import Flask
from src.routes.strava_routes import strava_bp, strava_connection_bp
from src.utils.strava_exceptions import (
    StravaOAuthError,
    StravaOAuthCodeExchangeError,
    StravaTokenError,
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


class TestStravaLoginRedirect:
    """Tests for /auth/strava-login endpoint."""

    @patch("src.routes.strava_routes.verify_and_decode")
    @patch("src.routes.strava_routes.generate_state_token")
    def test_strava_login_redirect_with_jwt(
        self, mock_generate_state, mock_verify, client, mock_env_vars
    ):
        """Test login redirect with JWT cookie."""
        # Setup
        mock_verify.return_value = {"sub": "auth0|123"}
        mock_generate_state.return_value = "state_token_123"

        # Execute
        response = client.get(
            "/auth/strava-login", headers={"Cookie": "user_jwt=test_jwt"}
        )

        # Verify
        assert response.status_code == 302
        assert "strava.com/oauth/authorize" in response.location
        assert "state_token_123" in response.location
        mock_generate_state.assert_called_once_with("auth0|123")

    def test_strava_login_redirect_without_jwt(self, client, mock_env_vars):
        """Test login redirect without JWT (uses query param)."""
        # Execute
        response = client.get("/auth/strava-login?user_id=auth0|123")

        # Verify
        assert response.status_code == 302
        assert "strava.com/oauth/authorize" in response.location

    def test_strava_login_redirect_missing_client_id(self, client, monkeypatch):
        """Test login redirect when STRAVA_CLIENT_ID is missing."""
        # Setup
        monkeypatch.delenv("STRAVA_CLIENT_ID", raising=False)

        # Execute
        response = client.get("/auth/strava-login")

        # Verify
        assert response.status_code == 500
        assert "CONFIG_ERROR" in response.get_json().get("error_code", "")


class TestStravaCallbackGet:
    """Tests for /auth/strava/callback GET endpoint."""

    @patch("src.routes.strava_routes.validate_state_token")
    @patch("src.routes.strava_routes.process_strava_callback")
    @patch("src.routes.strava_routes.run_background_job")
    @patch("src.routes.strava_routes.get_session")
    def test_callback_success(
        self,
        mock_get_session,
        mock_background_job,
        mock_process_callback,
        mock_validate_state,
        client,
        mock_env_vars,
    ):
        """Test successful OAuth callback."""
        # Setup
        mock_validate_state.return_value = (True, None)
        mock_process_callback.return_value = (98765, "user-123")
        mock_session = MagicMock()
        mock_session.get.return_value = "user-123"
        mock_get_session.return_value = mock_session

        # Execute
        response = client.get(
            "/auth/strava/callback?code=test_code&state=test_state",
            headers={"Cookie": "session=test_session"},
        )

        # Verify
        assert response.status_code == 302
        assert "strava=connected" in response.location
        mock_process_callback.assert_called_once()
        mock_background_job.assert_called_once()

    @patch("src.routes.strava_routes.validate_state_token")
    def test_callback_invalid_state(self, mock_validate_state, client, mock_env_vars):
        """Test callback with invalid state token."""
        # Setup
        mock_validate_state.return_value = (False, "Invalid state")

        # Execute
        response = client.get(
            "/auth/strava/callback?code=test_code&state=invalid_state"
        )

        # Verify
        assert response.status_code == 403
        assert "CSRF_PROTECTION" in response.get_json().get("error_code", "")

    @patch("src.routes.strava_routes.validate_state_token")
    @patch("src.routes.strava_routes.process_strava_callback")
    @patch("src.routes.strava_routes.get_session")
    def test_callback_oauth_error(
        self,
        mock_get_session,
        mock_process_callback,
        mock_validate_state,
        client,
        mock_env_vars,
    ):
        """Test callback when OAuth processing fails."""
        # Setup
        mock_validate_state.return_value = (True, None)
        mock_process_callback.side_effect = StravaOAuthCodeExchangeError(
            reason="Invalid code", message="OAuth exchange failed"
        )
        mock_session = MagicMock()
        mock_session.get.return_value = "user-123"
        mock_get_session.return_value = mock_session

        # Execute
        response = client.get(
            "/auth/strava/callback?code=invalid_code&state=test_state"
        )

        # Verify
        assert response.status_code == 400
        assert "StravaOAuthCodeExchangeError" in response.get_json().get(
            "error_code", ""
        )


class TestStravaCallbackPost:
    """Tests for /auth/strava/callback POST endpoint."""

    @patch("src.routes.strava_routes.process_strava_callback")
    @patch("src.routes.strava_routes.run_background_job")
    @patch("src.routes.strava_routes.get_session")
    def test_callback_post_success(
        self,
        mock_get_session,
        mock_background_job,
        mock_process_callback,
        client,
        mock_env_vars,
    ):
        """Test successful POST callback."""
        # Setup
        mock_process_callback.return_value = (98765, "user-123")
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_get_session.return_value.__exit__.return_value = None

        # Execute
        response = client.post(
            "/auth/strava/callback",
            json={"code": "test_code", "sub": "auth0|123"},
            content_type="application/json",
        )

        # Verify
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["athlete_id"] == 98765
        assert data["data"]["user_id"] == "user-123"

    def test_callback_post_missing_code(self, client, mock_env_vars):
        """Test POST callback with missing code."""
        # Execute
        response = client.post(
            "/auth/strava/callback",
            json={"sub": "auth0|123"},
            content_type="application/json",
        )

        # Verify
        assert response.status_code == 400
        assert "validation" in response.get_json().get("error", "").lower()

    def test_callback_post_missing_sub(self, client, mock_env_vars):
        """Test POST callback with missing sub."""
        # Execute
        response = client.post(
            "/auth/strava/callback",
            json={"code": "test_code"},
            content_type="application/json",
        )

        # Verify
        assert response.status_code == 400
        assert "sub" in response.get_json().get("error", "").lower()

    @patch("src.routes.strava_routes.process_strava_callback")
    @patch("src.routes.strava_routes.get_session")
    def test_callback_post_token_error(
        self,
        mock_get_session,
        mock_process_callback,
        client,
        mock_env_vars,
    ):
        """Test POST callback when token exchange fails."""
        # Setup
        mock_process_callback.side_effect = StravaTokenError("Token error", details={})
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_get_session.return_value.__exit__.return_value = None

        # Execute
        response = client.post(
            "/auth/strava/callback",
            json={"code": "test_code", "sub": "auth0|123"},
            content_type="application/json",
        )

        # Verify
        assert response.status_code == 400
        assert "StravaTokenError" in response.get_json().get("error_code", "")


class TestDisconnectStrava:
    """Tests for /api/strava/disconnect endpoint."""

    @patch("src.routes.strava_routes.get_authenticated_user_with_athlete")
    @patch("src.routes.strava_routes.delete_tokens_sa")
    @patch("src.routes.strava_routes.delete_by_user_id")
    @patch("src.routes.strava_routes.get_session")
    def test_disconnect_success(
        self,
        mock_get_session,
        mock_delete_link,
        mock_delete_tokens,
        mock_get_user_athlete,
        client,
    ):
        """Test successful Strava disconnection."""
        # Setup
        mock_athlete_link = MagicMock()
        mock_athlete_link.athlete_id = 98765
        mock_get_user_athlete.return_value = ("user-123", mock_athlete_link, None)
        mock_delete_tokens.return_value = 1
        mock_delete_link.return_value = True
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.count.return_value = 10
        mock_get_session.return_value = mock_session

        # Mock requires_auth decorator
        with patch("src.routes.strava_routes.requires_auth", lambda f: f):
            # Execute
            response = client.delete("/api/strava/disconnect")

        # Verify
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["deleted"]["tokens"] == 1
        assert data["data"]["deleted"]["athlete_link"] is True

    @patch("src.routes.strava_routes.get_authenticated_user_with_athlete")
    @patch("src.routes.strava_routes.get_session")
    def test_disconnect_no_connection(
        self, mock_get_session, mock_get_user_athlete, client
    ):
        """Test disconnect when no Strava connection exists."""
        # Setup
        from src.utils.response_utils import not_found_response

        mock_get_user_athlete.return_value = (
            "user-123",
            None,
            not_found_response(resource="Strava connection"),
        )
        mock_get_session.return_value = MagicMock()

        # Mock requires_auth decorator
        with patch("src.routes.strava_routes.requires_auth", lambda f: f):
            # Execute
            response = client.delete("/api/strava/disconnect")

        # Verify
        assert response.status_code == 404
        assert "No Strava account connected" in response.get_json().get("error", "")


class TestGetStravaStatus:
    """Tests for /api/strava/status endpoint."""

    @patch("src.routes.strava_routes.get_authenticated_user_with_athlete")
    @patch("src.routes.strava_routes.get_session")
    def test_get_status_connected(
        self, mock_get_session, mock_get_user_athlete, client
    ):
        """Test getting status when Strava is connected."""
        # Setup
        mock_athlete_link = MagicMock()
        mock_athlete_link.athlete_id = 98765
        mock_athlete_link.created_at = None
        mock_get_user_athlete.return_value = ("user-123", mock_athlete_link, None)
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.count.return_value = 25
        mock_get_session.return_value = mock_session

        # Mock requires_auth decorator
        with patch("src.routes.strava_routes.requires_auth", lambda f: f):
            # Execute
            response = client.get("/api/strava/status")

        # Verify
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["connected"] is True
        assert data["data"]["athlete_id"] == 98765
        assert data["data"]["activity_count"] == 25

    @patch("src.routes.strava_routes.get_authenticated_user_with_athlete")
    @patch("src.routes.strava_routes.get_session")
    def test_get_status_not_connected(
        self, mock_get_session, mock_get_user_athlete, client
    ):
        """Test getting status when Strava is not connected."""
        # Setup
        from src.utils.response_utils import not_found_response

        mock_get_user_athlete.return_value = (
            "user-123",
            None,
            not_found_response(resource="Strava connection"),
        )
        mock_get_session.return_value = MagicMock()

        # Mock requires_auth decorator
        with patch("src.routes.strava_routes.requires_auth", lambda f: f):
            # Execute
            response = client.get("/api/strava/status")

        # Verify
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["connected"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

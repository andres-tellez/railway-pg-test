"""
Tests for Auth0 JWT utilities.

Tests JWT verification, token validation, and the @requires_auth decorator.
"""

import pytest
import time
from unittest.mock import patch, MagicMock, Mock
from flask import Flask, request
from jose import jwt
from datetime import datetime, timedelta

from src.utils.auth0_jwt import verify_and_decode, requires_auth
from src.utils.config import config


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test_secret"
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_jwks():
    """Mock JWKS response from Auth0."""
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-kid",
                "use": "sig",
                "n": "test-n-value",
                "e": "AQAB",
            }
        ]
    }


@pytest.fixture
def valid_token_payload():
    """Create a valid JWT token payload for testing."""
    return {
        "sub": "auth0|test-user-123",
        "email": "test@example.com",
        "aud": config.AUTH0_AUDIENCE or "https://api.smartcoach.dev",
        "iss": f"https://{config.AUTH0_DOMAIN or 'test.auth0.com'}/",
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
    }


class TestVerifyAndDecode:
    """Tests for verify_and_decode function."""

    @patch("src.utils.auth0_jwt._get_rsa_key_for_kid")
    def test_verify_valid_token(self, mock_get_key, valid_token_payload):
        """Test verifying a valid JWT token."""
        # Mock RSA key
        mock_key = {
            "kty": "RSA",
            "kid": "test-kid",
            "use": "sig",
            "n": "test-n",
            "e": "AQAB",
        }
        mock_get_key.return_value = mock_key

        # Mock the entire verification chain
        with patch("src.utils.auth0_jwt.jwt.get_unverified_header") as mock_header:
            mock_header.return_value = {"kid": "test-kid"}

            with patch("src.utils.auth0_jwt.jwt.decode") as mock_decode:
                mock_decode.return_value = valid_token_payload

                result = verify_and_decode("mock.token.here")

                assert result == valid_token_payload
                mock_decode.assert_called_once()
                mock_get_key.assert_called_once_with("test-kid")

    def test_verify_missing_kid(self):
        """Test that missing kid in token header raises error."""
        with patch("src.utils.auth0_jwt.jwt.get_unverified_header") as mock_header:
            mock_header.return_value = {}  # No kid

            with pytest.raises(Exception):
                verify_and_decode("invalid.token")

    @patch("src.utils.auth0_jwt._get_rsa_key_for_kid")
    def test_verify_no_key_found(self, mock_get_key):
        """Test that missing RSA key raises error."""
        mock_get_key.return_value = None

        with patch("src.utils.auth0_jwt.jwt.get_unverified_header") as mock_header:
            mock_header.return_value = {"kid": "test-kid"}

            with pytest.raises(Exception, match="Unable to find appropriate key"):
                verify_and_decode("mock.token.here")


class TestRequiresAuth:
    """Tests for @requires_auth decorator."""

    @pytest.fixture
    def test_route(self, app):
        """Create a test route with @requires_auth decorator."""

        @app.route("/test-protected")
        @requires_auth
        def protected_route():
            from flask import g

            return {"user_id": g.user_id, "sub": g.current_user.get("sub")}

        return protected_route

    def test_missing_authorization_header(self, client, test_route):
        """Test that missing Authorization header returns 401."""
        response = client.get("/test-protected")

        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data
        assert data.get("reason") == "no_bearer"

    def test_invalid_authorization_format(self, client, test_route):
        """Test that invalid Authorization format returns 401."""
        response = client.get(
            "/test-protected", headers={"Authorization": "InvalidFormat token"}
        )

        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_invalid_token(self, client, test_route):
        """Test that invalid token returns 401."""
        with patch("src.utils.auth0_jwt.verify_and_decode") as mock_verify:
            mock_verify.side_effect = Exception("Invalid token")

            response = client.get(
                "/test-protected",
                headers={"Authorization": "Bearer invalid.token.here"},
            )

            assert response.status_code == 401
            data = response.get_json()
            assert "error" in data

    @patch("src.utils.auth0_jwt.verify_and_decode")
    @patch("src.utils.auth0_jwt.resolve_user_id_from_auth_provider")
    def test_valid_token_no_sub(self, mock_resolve, mock_verify, client, test_route):
        """Test that token without sub claim returns 401."""
        mock_verify.return_value = {"email": "test@example.com"}  # No sub

        response = client.get(
            "/test-protected", headers={"Authorization": "Bearer valid.token.here"}
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data.get("reason") == "no_sub"

    @patch("src.utils.auth0_jwt.verify_and_decode")
    @patch("src.utils.auth0_jwt.resolve_user_id_from_auth_provider")
    def test_valid_token_no_user_id(
        self, mock_resolve, mock_verify, client, test_route
    ):
        """Test that token with sub but no resolved user_id returns 401."""
        mock_verify.return_value = {"sub": "auth0|test-user"}
        mock_resolve.return_value = None  # Could not resolve user_id

        response = client.get(
            "/test-protected", headers={"Authorization": "Bearer valid.token.here"}
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data.get("reason") == "no_internal_user_id"

    @patch("src.utils.auth0_jwt.verify_and_decode")
    @patch("src.utils.auth0_jwt.resolve_user_id_from_auth_provider")
    def test_valid_token_success(self, mock_resolve, mock_verify, client, test_route):
        """Test that valid token with resolved user_id succeeds."""
        claims = {
            "sub": "auth0|test-user-123",
            "email": "test@example.com",
        }
        mock_verify.return_value = claims
        mock_resolve.return_value = "user-uuid-123"

        response = client.get(
            "/test-protected", headers={"Authorization": "Bearer valid.token.here"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["user_id"] == "user-uuid-123"
        assert data["sub"] == "auth0|test-user-123"

    @patch("src.utils.auth0_jwt.verify_and_decode")
    @patch("src.utils.auth0_jwt.resolve_user_id_from_auth_provider")
    def test_identity_resolution_failure_returns_500(
        self, mock_resolve, mock_verify, client, test_route
    ):
        """DB/identity failures should not be reported as invalid token."""
        mock_verify.return_value = {"sub": "auth0|test-user"}
        mock_resolve.side_effect = RuntimeError("db blew up")

        response = client.get(
            "/test-protected", headers={"Authorization": "Bearer valid.token.here"}
        )

        assert response.status_code == 500
        data = response.get_json()
        assert data.get("error") == "internal_error"
        assert data.get("reason") == "identity_resolution_failed"


class TestJWKSCaching:
    """Tests for JWKS caching behavior."""

    @patch("src.utils.auth0_jwt.requests.get")
    def test_jwks_fetch_and_cache(self, mock_get, mock_jwks):
        """Test that JWKS is fetched and cached."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Set up JWKS_URL for testing
        with patch(
            "src.utils.auth0_jwt.JWKS_URL",
            "https://test.auth0.com/.well-known/jwks.json",
        ):
            # First call should fetch
            from src.utils.auth0_jwt import _fetch_jwks

            result1 = _fetch_jwks()

            # Second call should also fetch (cache is handled separately)
            result2 = _fetch_jwks()

            assert result1 == mock_jwks
            assert result2 == mock_jwks
            assert mock_get.call_count == 2

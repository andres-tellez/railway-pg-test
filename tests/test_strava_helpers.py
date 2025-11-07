"""
Test Strava Helper Utilities

Tests for shared utility functions that eliminate code repetition.
"""

import pytest
from flask import Flask, g
from unittest.mock import patch, MagicMock
from src.utils.strava_helpers import (
    get_authenticated_user_id,
    get_user_athlete_link,
    get_authenticated_user_with_athlete,
    get_frontend_redirect_url,
    is_uuid_format,
    normalize_redirect_uri,
)


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


class TestGetAuthenticatedUserId:
    """Tests for get_authenticated_user_id function."""

    def test_get_authenticated_user_id_success(self, app):
        """Test getting authenticated user ID."""
        with app.app_context():
            g.user_id = "123e4567-e89b-12d3-a456-426614174000"
            user_id, error = get_authenticated_user_id()
            assert user_id == "123e4567-e89b-12d3-a456-426614174000"
            assert error is None

    def test_get_authenticated_user_id_not_authenticated(self, app):
        """Test getting user ID when not authenticated."""
        with app.app_context():
            if hasattr(g, "user_id"):
                delattr(g, "user_id")
            user_id, error = get_authenticated_user_id()
            assert user_id is None
            assert error is not None
            assert error[1] == 401


class TestGetUserAthleteLink:
    """Tests for get_user_athlete_link function."""

    def test_get_user_athlete_link_found(self, app):
        """Test getting athlete link when found."""
        with app.app_context():
            from src.db.models.user_athletes import UserAthleteLink
            from unittest.mock import patch

            mock_link = MagicMock(spec=UserAthleteLink)
            mock_link.athlete_id = 12345

            with patch(
                "src.utils.strava_helpers.get_by_user_id", return_value=mock_link
            ):
                athlete_link, error = get_user_athlete_link("user-id")
                assert athlete_link == mock_link
                assert error is None

    def test_get_user_athlete_link_not_found(self, app):
        """Test getting athlete link when not found."""
        with app.app_context():
            with patch("src.utils.strava_helpers.get_by_user_id", return_value=None):
                athlete_link, error = get_user_athlete_link("user-id")
                assert athlete_link is None
                assert error is not None
                assert error[1] == 404


class TestGetAuthenticatedUserWithAthlete:
    """Tests for get_authenticated_user_with_athlete function."""

    def test_get_authenticated_user_with_athlete_success(self, app):
        """Test getting authenticated user with athlete link."""
        with app.app_context():
            g.user_id = "123e4567-e89b-12d3-a456-426614174000"
            from src.db.models.user_athletes import UserAthleteLink
            from unittest.mock import patch

            mock_link = MagicMock(spec=UserAthleteLink)
            mock_link.athlete_id = 12345

            with patch(
                "src.utils.strava_helpers.get_by_user_id", return_value=mock_link
            ):
                user_id, athlete_link, error = get_authenticated_user_with_athlete()
                assert user_id == "123e4567-e89b-12d3-a456-426614174000"
                assert athlete_link == mock_link
                assert error is None

    def test_get_authenticated_user_with_athlete_not_authenticated(self, app):
        """Test when user is not authenticated."""
        with app.app_context():
            if hasattr(g, "user_id"):
                delattr(g, "user_id")
            user_id, athlete_link, error = get_authenticated_user_with_athlete()
            assert user_id is None
            assert athlete_link is None
            assert error is not None
            assert error[1] == 401


class TestGetFrontendRedirectUrl:
    """Tests for get_frontend_redirect_url function."""

    def test_get_frontend_redirect_url_from_env(self, app):
        """Test getting redirect URL from environment."""
        with patch.dict("os.environ", {"FRONTEND_REDIRECT": "https://example.com/app"}):
            url = get_frontend_redirect_url()
            assert url == "https://example.com/app"

    def test_get_frontend_redirect_url_default(self, app):
        """Test getting default redirect URL."""
        with patch.dict("os.environ", {}, clear=True):
            url = get_frontend_redirect_url()
            assert url == "https://localhost:5173/setup"

    def test_get_frontend_redirect_url_removes_trailing_slash(self, app):
        """Test that trailing slash is removed."""
        with patch.dict(
            "os.environ", {"FRONTEND_REDIRECT": "https://example.com/app/"}
        ):
            url = get_frontend_redirect_url()
            assert url == "https://example.com/app"


class TestIsUuidFormat:
    """Tests for is_uuid_format function."""

    def test_is_uuid_format_valid(self):
        """Test valid UUID format."""
        assert is_uuid_format("123e4567-e89b-12d3-a456-426614174000") is True

    def test_is_uuid_format_invalid(self):
        """Test invalid UUID format."""
        assert is_uuid_format("not-a-uuid") is False
        assert is_uuid_format("12345") is False
        assert is_uuid_format("") is False

    def test_is_uuid_format_none(self):
        """Test None value."""
        assert is_uuid_format(None) is False


class TestNormalizeRedirectUri:
    """Tests for normalize_redirect_uri function."""

    def test_normalize_redirect_uri_http_localhost(self):
        """Test normalizing HTTP localhost to HTTPS."""
        uri = normalize_redirect_uri("http://localhost:5000/callback")
        assert uri == "https://localhost:5000/callback"

    def test_normalize_redirect_uri_http_127(self):
        """Test normalizing HTTP 127.0.0.1 to HTTPS."""
        uri = normalize_redirect_uri("http://127.0.0.1:5000/callback")
        assert uri == "https://127.0.0.1:5000/callback"

    def test_normalize_redirect_uri_https_unchanged(self):
        """Test that HTTPS URIs are unchanged."""
        uri = normalize_redirect_uri("https://example.com/callback")
        assert uri == "https://example.com/callback"

    def test_normalize_redirect_uri_removes_trailing_semicolon(self):
        """Test that trailing semicolon is removed."""
        uri = normalize_redirect_uri("https://example.com/callback;")
        assert uri == "https://example.com/callback"

    def test_normalize_redirect_uri_strips_whitespace(self):
        """Test that whitespace is stripped."""
        uri = normalize_redirect_uri("  https://example.com/callback  ")
        assert uri == "https://example.com/callback"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

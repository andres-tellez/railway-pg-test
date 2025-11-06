"""
Tests for authentication helper utilities.

Tests the utility functions that reduce code repetition in auth routes.
"""

import pytest
from unittest.mock import patch
from flask import Flask, g
from src.utils.auth_helpers import get_sub_from_claims, get_user_id_from_request
from src.utils.response_utils import validation_error_response, not_found_response


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    return app


def test_get_sub_from_claims_with_valid_sub(app):
    """Test get_sub_from_claims with valid sub."""
    with app.app_context():
        g.current_user = {"sub": "auth0|test-user-123", "email": "test@example.com"}

        sub, error = get_sub_from_claims()

        assert sub == "auth0|test-user-123"
        assert error is None


def test_get_sub_from_claims_without_sub(app):
    """Test get_sub_from_claims without sub claim."""
    with app.app_context():
        g.current_user = {"email": "test@example.com"}  # No sub

        sub, error = get_sub_from_claims()

        assert sub is None
        assert error is not None
        # Error should be a validation error response tuple
        response, status_code = error
        assert status_code == 400


def test_get_sub_from_claims_with_empty_claims(app):
    """Test get_sub_from_claims with empty claims."""
    with app.app_context():
        g.current_user = {}

        sub, error = get_sub_from_claims()

        assert sub is None
        assert error is not None


def test_get_sub_from_claims_with_provided_claims(app):
    """Test get_sub_from_claims with explicitly provided claims."""
    claims = {"sub": "auth0|test-user-456", "email": "test@example.com"}

    sub, error = get_sub_from_claims(claims)

    assert sub == "auth0|test-user-456"
    assert error is None


def test_get_user_id_from_request_missing_sub(app):
    """Test get_user_id_from_request when sub is missing."""
    with app.app_context():
        g.current_user = {"email": "test@example.com"}  # No sub

        user_id, error = get_user_id_from_request()

        assert user_id is None
        assert error is not None
        response, status_code = error
        assert status_code == 400


def test_get_user_id_from_request_create_if_missing(app):
    """Test get_user_id_from_request with create_if_missing=True."""
    with app.app_context():
        g.current_user = {
            "sub": "auth0|test-user-789",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User",
            "picture": "https://example.com/pic.jpg",
        }

        # Mock the resolve_user_id_from_auth_provider to return a user_id
        with patch(
            "src.utils.auth_helpers.resolve_user_id_from_auth_provider"
        ) as mock_resolve:
            mock_resolve.return_value = "user-uuid-123"

            user_id, error = get_user_id_from_request(create_if_missing=True)

            assert user_id == "user-uuid-123"
            assert error is None
            mock_resolve.assert_called_once_with(
                "auth0|test-user-789", g.current_user, create_if_missing=True
            )


def test_get_user_id_from_request_no_user_found(app):
    """Test get_user_id_from_request when user_id cannot be resolved."""
    with app.app_context():
        g.current_user = {"sub": "auth0|test-user-999"}

        with patch(
            "src.utils.auth_helpers.resolve_user_id_from_auth_provider"
        ) as mock_resolve:
            mock_resolve.return_value = None  # User not found

            user_id, error = get_user_id_from_request()

            assert user_id is None
            assert error is not None
            response, status_code = error
            assert status_code == 404


def test_get_user_id_from_request_with_provided_claims(app):
    """Test get_user_id_from_request with explicitly provided claims."""
    claims = {"sub": "auth0|test-user-111", "email": "test@example.com"}

    with patch(
        "src.utils.auth_helpers.resolve_user_id_from_auth_provider"
    ) as mock_resolve:
        mock_resolve.return_value = "user-uuid-456"

        user_id, error = get_user_id_from_request(claims, create_if_missing=False)

        assert user_id == "user-uuid-456"
        assert error is None
        mock_resolve.assert_called_once_with(
            "auth0|test-user-111", claims, create_if_missing=False
        )

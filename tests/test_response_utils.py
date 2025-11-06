"""
Tests for response utilities.

Tests the standardized response formatting functions.
"""

import pytest
from flask import Flask
from src.utils.response_utils import (
    success_response,
    error_response,
    unauthorized_response,
    not_found_response,
    validation_error_response,
    internal_error_response,
)


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    return app


def test_success_response_with_data(app):
    """Test success_response with data."""
    with app.app_context():
        response, status_code = success_response({"user_id": "123"})

        assert status_code == 200
        assert response.json["status"] == 200
        assert response.json["data"] == {"user_id": "123"}


def test_success_response_with_message(app):
    """Test success_response with message."""
    with app.app_context():
        response, status_code = success_response(
            data={"user_id": "123"}, message="User created"
        )

        assert status_code == 200
        assert response.json["status"] == 200
        assert response.json["data"] == {"user_id": "123"}
        assert response.json["message"] == "User created"


def test_success_response_custom_status(app):
    """Test success_response with custom status code."""
    with app.app_context():
        response, status_code = success_response(data={"id": 1}, status_code=201)

        assert status_code == 201
        assert response.json["status"] == 201


def test_error_response_basic(app):
    """Test basic error_response."""
    with app.app_context():
        response, status_code = error_response("Something went wrong")

        assert status_code == 400
        assert response.json["status"] == 400
        assert response.json["error"] == "Something went wrong"


def test_error_response_with_error_code(app):
    """Test error_response with error code."""
    with app.app_context():
        response, status_code = error_response(
            "User not found", status_code=404, error_code="USER_NOT_FOUND"
        )

        assert status_code == 404
        assert response.json["status"] == 404
        assert response.json["error"] == "User not found"
        assert response.json["error_code"] == "USER_NOT_FOUND"


def test_error_response_with_details(app):
    """Test error_response with details."""
    with app.app_context():
        response, status_code = error_response(
            "Validation failed", details={"field": "email", "reason": "invalid format"}
        )

        assert status_code == 400
        assert response.json["error"] == "Validation failed"
        assert response.json["details"] == {
            "field": "email",
            "reason": "invalid format",
        }


def test_unauthorized_response(app):
    """Test unauthorized_response."""
    with app.app_context():
        response, status_code = unauthorized_response(reason="no_bearer")

        assert status_code == 401
        assert response.json["status"] == 401
        assert response.json["error_code"] == "UNAUTHORIZED"
        assert response.json["reason"] == "no_bearer"


def test_not_found_response(app):
    """Test not_found_response."""
    with app.app_context():
        response, status_code = not_found_response(resource="User")

        assert status_code == 404
        assert response.json["status"] == 404
        assert response.json["error_code"] == "NOT_FOUND"
        assert "User not found" in response.json["error"]


def test_validation_error_response(app):
    """Test validation_error_response."""
    with app.app_context():
        response, status_code = validation_error_response(
            "Invalid email format",
            field="email",
            errors={"email": "must be a valid email address"},
        )

        assert status_code == 400
        assert response.json["status"] == 400
        assert response.json["error_code"] == "VALIDATION_ERROR"
        assert response.json["details"]["field"] == "email"
        assert "email" in response.json["details"]["errors"]


def test_internal_error_response(app):
    """Test internal_error_response."""
    with app.app_context():
        response, status_code = internal_error_response("Database error")

        assert status_code == 500
        assert response.json["status"] == 500
        assert response.json["error_code"] == "INTERNAL_ERROR"
        assert response.json["error"] == "Database error"


def test_error_message_sanitization(app):
    """Test that long error messages are truncated."""
    with app.app_context():
        long_message = "A" * 600
        response, status_code = error_response(long_message)

        assert len(response.json["error"]) <= 503  # 500 + "..."
        assert response.json["error"].endswith("...")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

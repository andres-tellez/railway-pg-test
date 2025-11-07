"""
Test Strava Integration Error Responses

Tests that all error responses use standardized response_utils.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

from src.routes.strava_routes import strava_connection_bp
from src.routes.webhook_routes import webhook_bp
from src.utils.response_utils import (
    success_response,
    error_response,
    validation_error_response,
    internal_error_response,
    unauthorized_response,
    not_found_response,
)


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(strava_connection_bp)
    app.register_blueprint(webhook_bp)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


def test_no_jsonify_in_strava_routes():
    """Test that strava_routes.py doesn't use jsonify directly."""
    import os
    import re

    file_path = "src/routes/strava_routes.py"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                # Skip comments and docstrings
                if (
                    stripped.startswith("#")
                    or stripped.startswith('"""')
                    or stripped.startswith("'''")
                ):
                    continue
                # Check for jsonify( calls (excluding imports)
                if (
                    re.search(r"\bjsonify\s*\(", line)
                    and "from flask import" not in line
                ):
                    pytest.fail(
                        f"Found jsonify() call in {file_path} at line {i}: {line}"
                    )


def test_webhook_routes_uses_response_utils():
    """Test that webhook routes use response_utils (except special case)."""
    import os
    import re

    file_path = "src/routes/webhook_routes.py"
    jsonify_calls = []

    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                # Skip comments and docstrings
                if (
                    stripped.startswith("#")
                    or stripped.startswith('"""')
                    or stripped.startswith("'''")
                ):
                    continue
                # Check for jsonify( calls
                if (
                    re.search(r"\bjsonify\s*\(", line)
                    and "from flask import" not in line
                ):
                    # Allow special case for webhook verification challenge (Strava protocol requirement)
                    if "hub.challenge" in line:
                        continue  # This is acceptable - Strava protocol requirement
                    jsonify_calls.append((i, line))

    # Should only have the webhook verification challenge (which is acceptable)
    assert len(jsonify_calls) == 0, f"Found unexpected jsonify() calls: {jsonify_calls}"


def test_strava_routes_imports_response_utils():
    """Test that strava_routes imports response_utils functions."""
    import src.routes.strava_routes as strava_module

    # Check that response_utils functions are imported
    assert hasattr(strava_module, "success_response"), "Should import success_response"
    assert hasattr(strava_module, "error_response"), "Should import error_response"
    assert hasattr(
        strava_module, "unauthorized_response"
    ), "Should import unauthorized_response"
    assert hasattr(
        strava_module, "not_found_response"
    ), "Should import not_found_response"
    assert hasattr(
        strava_module, "internal_error_response"
    ), "Should import internal_error_response"


def test_webhook_routes_imports_response_utils():
    """Test that webhook_routes imports response_utils functions."""
    import src.routes.webhook_routes as webhook_module

    # Check that response_utils functions are imported
    assert hasattr(webhook_module, "success_response"), "Should import success_response"
    assert hasattr(webhook_module, "error_response"), "Should import error_response"
    assert hasattr(
        webhook_module, "validation_error_response"
    ), "Should import validation_error_response"
    assert hasattr(
        webhook_module, "internal_error_response"
    ), "Should import internal_error_response"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

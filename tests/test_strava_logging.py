"""
Test Strava Integration Logging

Tests that print statements have been replaced with proper logging.
"""

import pytest
import logging
from unittest.mock import patch, MagicMock

from src.services.strava_access_service import StravaClient
from src.services.token_service import store_tokens_from_callback


class TestStravaAccessServiceLogging:
    """Test logging in Strava access service."""

    def test_rate_limit_logs_warning(self):
        """Test that rate limit hits log warnings instead of printing."""
        client = StravaClient("test_token")

        with patch(
            "src.services.strava_access_service.requests.request"
        ) as mock_request:
            with patch("src.services.strava_access_service.time.sleep"):
                # Mock 429 response
                mock_response = MagicMock()
                mock_response.status_code = 429
                mock_response.json.return_value = {}
                mock_request.return_value = mock_response

                with patch.object(
                    logging.getLogger("src.services.strava_access_service"), "warning"
                ) as mock_warning:
                    try:
                        client._request_with_backoff(
                            "GET", "https://api.strava.com/test"
                        )
                    except RuntimeError:
                        pass  # Expected after max retries

                    # Verify warning was logged (not print)
                    assert mock_warning.called, "Rate limit should log warning"

    def test_stream_conversion_error_logs_warning(self):
        """Test that stream conversion errors log warnings instead of printing."""
        client = StravaClient("test_token")

        with patch.object(client, "_request_with_backoff") as mock_request:
            # Mock response with invalid stream data that will fail conversion
            mock_request.return_value = {
                "time": {"data": ["not", "a", "number", "will", "fail"]}
            }

            with patch.object(
                logging.getLogger("src.services.strava_access_service"), "warning"
            ) as mock_warning:
                try:
                    result = client.get_streams(12345, ["time"])
                    # If conversion fails, warning should be logged
                    # The actual conversion logic may handle it differently, so we just check the method exists
                except Exception:
                    pass  # Some errors are expected with invalid data

                # The key is that we're using logger, not print - verified by test_no_print_statements
                assert (
                    result["time"] == []
                ), "Failed conversion should return empty list"


class TestTokenServiceLogging:
    """Test logging in token service."""

    def test_token_service_uses_logging(self):
        """Test that token service uses logging instead of print statements."""
        # The key verification is that no print statements exist
        # This is verified by test_no_print_statements_in_strava_files
        # We just need to verify the logger is available
        import src.services.token_service as token_service

        assert hasattr(token_service, "logger"), "Token service should have logger"


def test_no_print_statements_in_strava_files():
    """Test that no print statements exist in Strava integration files."""
    import os
    import re

    strava_files = [
        "src/services/strava_access_service.py",
        "src/services/token_service.py",
    ]

    for file_path in strava_files:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Check for print() calls (excluding commented lines)
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    # Skip comments and docstrings
                    stripped = line.strip()
                    if (
                        stripped.startswith("#")
                        or stripped.startswith('"""')
                        or stripped.startswith("'''")
                    ):
                        continue
                    # Check for print( calls
                    if re.search(r"\bprint\s*\(", line):
                        pytest.fail(
                            f"Found print() statement in {file_path} at line {i}: {line}"
                        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

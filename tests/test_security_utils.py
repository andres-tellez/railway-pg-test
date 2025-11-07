"""
Tests for Security Utilities

Tests for security functions including:
- Error message sanitization
- Input sanitization
- Exception details sanitization
"""

import pytest
from src.utils.security_utils import (
    sanitize_error_message,
    sanitize_user_input,
    sanitize_exception_details,
    get_safe_error_message,
    is_safe_string,
)


class TestSanitizeErrorMessage:
    """Tests for error message sanitization."""

    def test_removes_password_patterns(self):
        """Test that password patterns are removed."""
        error = Exception("Database connection failed: password=secret123")
        sanitized = sanitize_error_message(error)
        assert "password=secret123" not in sanitized
        assert "[REDACTED]" in sanitized or "password" not in sanitized.lower()

    def test_removes_token_patterns(self):
        """Test that token patterns are removed."""
        error = Exception("API request failed: access_token=abc123xyz")
        sanitized = sanitize_error_message(error)
        assert "access_token=abc123xyz" not in sanitized
        assert "[REDACTED]" in sanitized or "token" not in sanitized.lower()

    def test_removes_file_paths(self):
        """Test that file paths are removed."""
        error = Exception("Error in /app/src/services/token_service.py line 123")
        sanitized = sanitize_error_message(error)
        assert "/app/src/services/token_service.py" not in sanitized
        assert "[PATH]" in sanitized or "token_service.py" not in sanitized

    def test_removes_stack_traces(self):
        """Test that stack traces are removed."""
        error = Exception("Traceback (most recent call last):\n  File test.py, line 1")
        sanitized = sanitize_error_message(error)
        assert "Traceback" not in sanitized
        assert "[STACK_TRACE]" in sanitized or "traceback" not in sanitized.lower()

    def test_oauth_context_returns_auth_message(self):
        """Test that OAuth context returns authentication error message."""
        error = Exception("Token exchange failed")
        sanitized = sanitize_error_message(error, context="oauth")
        assert "authentication" in sanitized.lower() or "failed" in sanitized.lower()

    def test_webhook_context_returns_internal_message(self):
        """Test that webhook context returns internal error message."""
        error = Exception("Processing failed")
        sanitized = sanitize_error_message(error, context="webhook")
        assert "internal" in sanitized.lower() or "webhook" in sanitized.lower()

    def test_database_error_returns_database_message(self):
        """Test that database errors return database error message."""
        error = Exception("Database connection failed")
        sanitized = sanitize_error_message(error, context="general")
        assert "database" in sanitized.lower()


class TestSanitizeUserInput:
    """Tests for user input sanitization."""

    def test_removes_null_bytes(self):
        """Test that null bytes are removed."""
        input_str = "test\x00string"
        sanitized = sanitize_user_input(input_str)
        assert "\x00" not in sanitized
        assert "test" in sanitized
        assert "string" in sanitized

    def test_truncates_long_input(self):
        """Test that long input is truncated."""
        input_str = "a" * 2000
        sanitized = sanitize_user_input(input_str, max_length=1000)
        assert len(sanitized) <= 1000

    def test_removes_control_characters(self):
        """Test that control characters are removed."""
        input_str = "test\x01\x02\x03string"
        sanitized = sanitize_user_input(input_str)
        assert "\x01" not in sanitized
        assert "\x02" not in sanitized
        assert "\x03" not in sanitized
        assert "test" in sanitized
        assert "string" in sanitized

    def test_preserves_newline_tab_carriage_return(self):
        """Test that newline, tab, and carriage return are preserved."""
        input_str = "line1\nline2\tline3\rline4"
        sanitized = sanitize_user_input(input_str)
        assert "\n" in sanitized
        assert "\t" in sanitized
        assert "\r" in sanitized

    def test_handles_non_string_input(self):
        """Test that non-string input is converted to string."""
        sanitized = sanitize_user_input(12345)
        assert isinstance(sanitized, str)
        assert "12345" in sanitized


class TestSanitizeExceptionDetails:
    """Tests for exception details sanitization."""

    def test_redacts_sensitive_keys(self):
        """Test that sensitive keys are redacted."""
        details = {
            "password": "secret123",
            "access_token": "abc123",
            "database_url": "postgresql://user:pass@host/db",
            "safe_key": "safe_value",
        }
        sanitized = sanitize_exception_details(details)
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["access_token"] == "[REDACTED]"
        assert sanitized["database_url"] == "[REDACTED]"
        assert sanitized["safe_key"] == "safe_value"

    def test_sanitizes_string_values(self):
        """Test that string values are sanitized."""
        details = {"error_message": "Database connection failed: password=secret123"}
        sanitized = sanitize_exception_details(details)
        assert "password=secret123" not in sanitized["error_message"]

    def test_recursively_sanitizes_nested_dicts(self):
        """Test that nested dictionaries are recursively sanitized."""
        details = {"nested": {"password": "secret123", "safe_key": "safe_value"}}
        sanitized = sanitize_exception_details(details)
        assert sanitized["nested"]["password"] == "[REDACTED]"
        assert sanitized["nested"]["safe_key"] == "safe_value"

    def test_handles_empty_dict(self):
        """Test that empty dictionary is handled."""
        sanitized = sanitize_exception_details({})
        assert sanitized == {}

    def test_handles_non_dict_input(self):
        """Test that non-dict input returns empty dict."""
        sanitized = sanitize_exception_details("not a dict")
        assert sanitized == {}


class TestGetSafeErrorMessage:
    """Tests for get_safe_error_message function."""

    def test_database_error_returns_database_message(self):
        """Test that database errors return database message."""
        error = Exception("Database connection failed")
        message = get_safe_error_message(error)
        assert "database" in message.lower()

    def test_network_error_returns_network_message(self):
        """Test that network errors return network message."""
        error = Exception("Network timeout occurred")
        message = get_safe_error_message(error)
        assert "network" in message.lower()

    def test_auth_error_returns_auth_message(self):
        """Test that auth errors return auth message."""
        error = Exception("Token expired")
        message = get_safe_error_message(error)
        assert "authentication" in message.lower() or "auth" in message.lower()

    def test_validation_error_returns_validation_message(self):
        """Test that validation errors return validation message."""
        error = Exception("Invalid input provided")
        message = get_safe_error_message(error)
        assert "invalid" in message.lower() or "validation" in message.lower()

    def test_rate_limit_error_returns_rate_limit_message(self):
        """Test that rate limit errors return rate limit message."""
        error = Exception("Rate limit exceeded 429")
        message = get_safe_error_message(error)
        assert "too many" in message.lower() or "rate" in message.lower()

    def test_unknown_error_uses_sanitized_message(self):
        """Test that unknown errors use sanitized message."""
        error = Exception("Some unknown error with password=secret123")
        message = get_safe_error_message(error)
        assert "password=secret123" not in message
        assert len(message) > 0


class TestIsSafeString:
    """Tests for is_safe_string function."""

    def test_safe_alphanumeric_string(self):
        """Test that alphanumeric string is safe."""
        assert is_safe_string("test123") is True

    def test_safe_string_with_punctuation(self):
        """Test that string with punctuation is safe."""
        assert is_safe_string("test-string_123") is True

    def test_unsafe_string_with_control_chars(self):
        """Test that string with control characters is unsafe."""
        assert is_safe_string("test\x00string") is False

    def test_non_string_input_returns_false(self):
        """Test that non-string input returns False."""
        assert is_safe_string(12345) is False
        assert is_safe_string(None) is False

    def test_custom_allowed_chars(self):
        """Test that custom allowed characters pattern works."""
        custom_pattern = r"^[a-z0-9]+$"
        assert is_safe_string("test123", allowed_chars=custom_pattern) is True
        assert is_safe_string("TEST123", allowed_chars=custom_pattern) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

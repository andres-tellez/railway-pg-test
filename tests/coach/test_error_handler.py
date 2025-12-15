"""
Tests for error handling utilities.

These tests verify that errors are handled correctly with
appropriate logging and fallback behavior.
"""

import pytest
import logging
from coach.utils.error_handler import CoachErrorHandler, ErrorSeverity, CoachError


class TestCoachErrorHandler:
    """Test error handler functionality."""

    def test_handle_critical_error(self, caplog):
        """Test handling a critical error."""
        error = ValueError("Critical failure")

        with caplog.at_level(logging.CRITICAL):
            result = CoachErrorHandler.handle(
                error=error,
                severity=ErrorSeverity.CRITICAL,
                component="TestComponent",
                user_id="test-user-123",
            )

        assert result is None
        assert "CRITICAL error" in caplog.text
        assert "TestComponent" in caplog.text

    def test_handle_high_severity_error(self, caplog):
        """Test handling a high severity error."""
        error = RuntimeError("High severity issue")

        with caplog.at_level(logging.ERROR):
            result = CoachErrorHandler.handle(
                error=error, severity=ErrorSeverity.HIGH, component="TestComponent"
            )

        assert result is None
        assert "HIGH severity error" in caplog.text

    def test_handle_with_fallback_value(self):
        """Test error handling returns fallback value."""
        error = ValueError("Test error")
        fallback = {"status": "fallback"}

        result = CoachErrorHandler.handle(
            error=error,
            severity=ErrorSeverity.MEDIUM,
            component="TestComponent",
            fallback_value=fallback,
        )

        assert result == fallback

    def test_handle_runner_state_builder_error(self):
        """Test RunnerStateBuilder error handling with fallback."""
        error = ValueError("Failed to build runner state")
        user_id = "test-user-123"

        fallback_state = CoachErrorHandler.handle_runner_state_builder_error(
            error=error, user_id=user_id
        )

        assert fallback_state is not None
        assert fallback_state["version"] == "1.0.0"
        assert fallback_state["runner_state"]["phase"] == "Unknown"
        assert fallback_state["runner_state"]["week_of_block"] == 0

    def test_handle_llm_timeout_no_retry(self):
        """Test LLM timeout handling on first attempt."""
        error = TimeoutError("LLM request timeout")
        user_id = "test-user-123"

        result = CoachErrorHandler.handle_llm_timeout(
            error=error, user_id=user_id, retry_count=0
        )

        assert result is None

    def test_handle_llm_timeout_after_retry(self, caplog):
        """Test LLM timeout handling after retry."""
        error = TimeoutError("LLM request timeout")
        user_id = "test-user-123"

        with caplog.at_level(logging.ERROR):
            result = CoachErrorHandler.handle_llm_timeout(
                error=error, user_id=user_id, retry_count=1  # After retry
            )

        assert result is None
        assert "HIGH severity error" in caplog.text

    def test_handle_context_too_large(self):
        """Test context too large error handling."""
        error = ValueError("Context exceeds maximum size")

        result = CoachErrorHandler.handle_context_too_large(
            error=error, component="ContextCompressor", context_size=5000, max_size=3000
        )

        assert result == {}  # Empty dict signals need to compress

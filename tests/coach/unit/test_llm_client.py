"""
Unit tests for LLMClient.

Tests the Coach-specific LLM client wrapper.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from coach.llm.llm_client import LLMClient, LLMRequest, LLMResponse
from src.services.security.external_apis.openai_service import (
    OpenAIResponse,
    RateLimitExceededError,
    CostLimitExceededError,
)


class TestLLMClient:
    """Test LLMClient with mocked OpenAIService."""

    def test_chat_completion_success(self):
        """Test successful LLM call."""
        # Mock OpenAIService
        mock_service = Mock()
        mock_openai_response = OpenAIResponse(
            content="Test response",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            cost=0.001,
            model="gpt-4o",
        )
        mock_service.chat_completion.return_value = mock_openai_response

        # Create LLMClient with mocked service
        client = LLMClient(service=mock_service)

        # Create request
        request = LLMRequest(
            messages=[{"role": "user", "content": "Test question"}],
            user_id="test_user",
        )

        # Call chat_completion
        response = client.chat_completion(request)

        # Verify response
        assert response.content == "Test response"
        assert response.usage["total_tokens"] == 150
        assert response.cost == 0.001
        assert response.model == "gpt-4o"

        # Verify service was called correctly
        mock_service.chat_completion.assert_called_once()
        call_args = mock_service.chat_completion.call_args
        assert call_args.kwargs["user_id"] == "test_user"
        assert len(call_args.kwargs["messages"]) == 1

    def test_chat_completion_with_overrides(self):
        """Test LLM call with parameter overrides."""
        mock_service = Mock()
        mock_openai_response = OpenAIResponse(
            content="Test",
            usage={"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
            cost=0.0005,
            model="gpt-4o",
        )
        mock_service.chat_completion.return_value = mock_openai_response

        client = LLMClient(service=mock_service)

        request = LLMRequest(
            messages=[{"role": "user", "content": "Test"}],
            user_id="test_user",
            model="gpt-3.5-turbo",
            temperature=0.5,
            max_tokens=100,
            timeout=60.0,
        )

        response = client.chat_completion(request)

        # Verify overrides were passed
        call_args = mock_service.chat_completion.call_args
        assert call_args.kwargs["model"] == "gpt-3.5-turbo"
        assert call_args.kwargs["temperature"] == 0.5
        assert call_args.kwargs["max_tokens"] == 100
        assert call_args.kwargs["timeout"] == 60.0

    def test_chat_completion_uses_config_defaults(self):
        """Test that LLM call uses Config defaults when not overridden."""
        mock_service = Mock()
        mock_openai_response = OpenAIResponse(
            content="Test",
            usage={"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
            cost=0.0005,
            model="gpt-4o",
        )
        mock_service.chat_completion.return_value = mock_openai_response

        client = LLMClient(service=mock_service)

        request = LLMRequest(
            messages=[{"role": "user", "content": "Test"}],
            user_id="test_user",
        )

        response = client.chat_completion(request)

        # Verify service was called (config defaults will be used from real Config)
        mock_service.chat_completion.assert_called_once()
        call_args = mock_service.chat_completion.call_args
        # Verify that defaults were applied (model and temperature should not be None)
        assert "model" in call_args.kwargs
        assert call_args.kwargs["model"] is not None
        assert "temperature" in call_args.kwargs
        assert call_args.kwargs["temperature"] is not None

    def test_chat_completion_rate_limit_error(self):
        """Test that RateLimitExceededError is re-raised."""
        mock_service = Mock()
        mock_service.chat_completion.side_effect = RateLimitExceededError(
            retry_after=60.0
        )

        client = LLMClient(service=mock_service)

        request = LLMRequest(
            messages=[{"role": "user", "content": "Test"}],
            user_id="test_user",
        )

        with pytest.raises(RateLimitExceededError) as exc_info:
            client.chat_completion(request)

        assert exc_info.value.retry_after == 60.0

    def test_chat_completion_cost_limit_error(self):
        """Test that CostLimitExceededError is re-raised."""
        mock_service = Mock()
        mock_service.chat_completion.side_effect = CostLimitExceededError(
            "Daily cost limit exceeded", exceeded_by=10.0
        )

        client = LLMClient(service=mock_service)

        request = LLMRequest(
            messages=[{"role": "user", "content": "Test"}],
            user_id="test_user",
        )

        with pytest.raises(CostLimitExceededError) as exc_info:
            client.chat_completion(request)

        assert "Daily cost limit exceeded" in str(exc_info.value)

    def test_chat_completion_handles_other_errors(self):
        """Test that other errors are handled with CoachErrorHandler."""
        mock_service = Mock()
        mock_service.chat_completion.side_effect = ValueError("Invalid request")

        client = LLMClient(service=mock_service)

        request = LLMRequest(
            messages=[{"role": "user", "content": "Test"}],
            user_id="test_user",
        )

        with patch("coach.llm.llm_client.CoachErrorHandler") as mock_error_handler:
            with pytest.raises(ValueError):
                client.chat_completion(request)

            # Verify error was handled
            mock_error_handler.handle.assert_called_once()
            call_args = mock_error_handler.handle.call_args
            assert call_args.kwargs["user_id"] == "test_user"
            assert call_args.kwargs["component"] == "LLMClient.chat_completion"

    def test_chat_completion_simple_interface(self):
        """Test simplified chat_completion_simple interface."""
        mock_service = Mock()
        mock_openai_response = OpenAIResponse(
            content="Simple response",
            usage={"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
            cost=0.0005,
            model="gpt-4o",
        )
        mock_service.chat_completion.return_value = mock_openai_response

        client = LLMClient(service=mock_service)

        messages = [{"role": "user", "content": "Test question"}]
        response = client.chat_completion_simple(
            messages, "test_user", model="gpt-3.5-turbo"
        )

        assert response.content == "Simple response"
        assert response.model == "gpt-4o"

        # Verify service was called with correct parameters
        call_args = mock_service.chat_completion.call_args
        assert call_args.kwargs["model"] == "gpt-3.5-turbo"
        assert call_args.kwargs["user_id"] == "test_user"

    def test_chat_completion_simple_with_require_json(self):
        """Test chat_completion_simple with require_json flag."""
        mock_service = Mock()
        mock_openai_response = OpenAIResponse(
            content='{"answer": "test"}',
            usage={"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
            cost=0.0005,
            model="gpt-4o",
        )
        mock_service.chat_completion.return_value = mock_openai_response

        client = LLMClient(service=mock_service)

        messages = [{"role": "user", "content": "Test"}]
        response = client.chat_completion_simple(
            messages, "test_user", require_json=True
        )

        assert response.content == '{"answer": "test"}'

        # Verify require_json was passed
        call_args = mock_service.chat_completion.call_args
        assert call_args.kwargs.get("require_json") is True

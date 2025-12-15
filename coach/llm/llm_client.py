"""
LLMClient for Coach system.

Thin wrapper around OpenAIService that provides Coach-specific interface
and configuration management.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from coach.utils.config import Config
from coach.utils.error_handler import CoachErrorHandler, ErrorSeverity

from src.services.security.external_apis.openai_service import (
    OpenAIService,
    OpenAIResponse,
    RateLimitExceededError,
    CostLimitExceededError,
    get_openai_service,
)


@dataclass
class LLMRequest:
    """Request parameters for LLM call."""

    messages: List[Dict[str, str]]
    user_id: str
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[float] = None
    require_json: bool = False


@dataclass
class LLMResponse:
    """Response from LLM call."""

    content: str
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    cost: float
    model: str


class LLMClient:
    """
    Coach-specific LLM client.

    Wraps OpenAIService with Coach configuration and error handling.
    """

    def __init__(self, service: Optional[OpenAIService] = None):
        """
        Initialize LLMClient.

        Args:
            service: Optional OpenAIService instance (for testing).
                    If None, uses global service instance.
        """
        self._service = service if service else get_openai_service()
        self._config = Config()

    def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """
        Make LLM chat completion call with Coach configuration.

        Args:
            request: LLMRequest with messages, user_id, and optional overrides

        Returns:
            LLMResponse with content, usage, cost, and model

        Raises:
            RateLimitExceededError: If rate limit exceeded
            CostLimitExceededError: If cost limit exceeded
            ValueError: If request is invalid
            Exception: For OpenAI API errors
        """
        try:
            # Get defaults from config or use fallbacks
            model = request.model or self._config.get_llm_config(
                "default_model", "gpt-4o"
            )
            temperature = (
                request.temperature
                if request.temperature is not None
                else self._config.get_llm_config("default_temperature", 0.7)
            )
            max_tokens = (
                request.max_tokens
                if request.max_tokens is not None
                else self._config.get_llm_config("default_max_tokens", None)
            )
            timeout = (
                request.timeout
                if request.timeout is not None
                else self._config.get_llm_config("default_timeout", 30.0)
            )

            # Call OpenAIService
            response = self._service.chat_completion(
                messages=request.messages,
                user_id=request.user_id,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                require_json=request.require_json,
            )

            # Convert to Coach-specific response format
            return LLMResponse(
                content=response.content,
                usage=response.usage,
                cost=response.cost,
                model=response.model,
            )

        except (RateLimitExceededError, CostLimitExceededError) as e:
            # Re-raise security errors (caller should handle)
            raise

        except Exception as e:
            # Handle other errors with CoachErrorHandler
            CoachErrorHandler.handle(
                error=e,
                severity=ErrorSeverity.HIGH,
                component="LLMClient.chat_completion",
                user_id=request.user_id,
                metadata={
                    "model": model if "model" in locals() else "unknown",
                    "message_count": len(request.messages),
                },
            )
            raise

    def chat_completion_simple(
        self,
        messages: List[Dict[str, str]],
        user_id: str,
        **kwargs,
    ) -> LLMResponse:
        """
        Simplified interface for making LLM calls.

        Args:
            messages: List of message dicts with 'role' and 'content'
            user_id: User identifier
            **kwargs: Optional overrides (model, temperature, max_tokens, timeout, require_json)

        Returns:
            LLMResponse with content, usage, cost, and model
        """
        request = LLMRequest(
            messages=messages,
            user_id=user_id,
            model=kwargs.get("model"),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            timeout=kwargs.get("timeout"),
            require_json=kwargs.get("require_json", False),
        )

        return self.chat_completion(request)

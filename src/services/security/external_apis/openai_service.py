"""
Unified OpenAI Service
======================

Centralized service for all OpenAI API interactions with automatic security controls.

This service provides:
- Automatic rate limiting (per-user)
- Automatic cost tracking (per-user and global)
- Standardized token extraction
- Consistent error handling
- Single source of truth for pricing

Architecture Principles:
-----------------------
1. All OpenAI calls MUST go through this service
2. User ID is REQUIRED for all calls (for tracking)
3. Rate limiting and cost tracking are AUTOMATIC
4. No direct OpenAI client calls allowed

Usage:
------
    from src.services.security.external_apis.openai_service import OpenAIService

    service = OpenAIService()
    response = service.chat_completion(
        messages=[{"role": "user", "content": "Hello"}],
        model="gpt-4o",
        user_id="user-123",  # Required
        temperature=0.7,
    )

    print(response.content)
    print(f"Cost: ${response.cost:.6f}")
    print(f"Tokens: {response.usage['total_tokens']}")
"""

import os
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from openai import OpenAI

from src.services.security.external_apis.openai_rate_limiter import (
    can_make_request,
    record_request,
)
from src.services.security.external_apis.openai_cost_tracker import (
    check_cost_limits,
    record_request_cost,
    MODEL_PRICING,
)

logger = logging.getLogger(__name__)


@dataclass
class OpenAIResponse:
    """Standardized OpenAI API response with usage and cost information."""

    content: str
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    cost: float
    model: str
    request_id: Optional[str] = None


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after:.1f} seconds.")


class CostLimitExceededError(Exception):
    """Raised when cost limit is exceeded."""

    def __init__(self, message: str, exceeded_by: Optional[float] = None):
        self.message = message
        self.exceeded_by = exceeded_by
        super().__init__(message)


class OpenAIService:
    """
    Unified service for all OpenAI API interactions.

    Provides automatic rate limiting, cost tracking, and standardized responses.
    """

    def __init__(self, client: Optional[OpenAI] = None):
        """
        Initialize OpenAI service.

        Args:
            client: Optional OpenAI client instance. If not provided, creates one from env.
        """
        if client is not None:
            self._client = client
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self._client = OpenAI(api_key=api_key)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        user_id: str,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 30.0,
        require_json: bool = False,
        **kwargs,
    ) -> OpenAIResponse:
        """
        Make OpenAI chat completion call with automatic security controls.

        Args:
            messages: List of message dicts with 'role' and 'content'
            user_id: User identifier (REQUIRED for rate limiting and cost tracking)
            model: Model to use (default: gpt-4o)
            temperature: Sampling temperature (default: 0.7)
            max_tokens: Maximum tokens in response
            timeout: Request timeout in seconds (default: 30.0)
            require_json: If True, enforces JSON response format
            **kwargs: Additional parameters passed to OpenAI API

        Returns:
            OpenAIResponse with content, usage, cost, and model

        Raises:
            RateLimitExceededError: If rate limit exceeded
            CostLimitExceededError: If cost limit exceeded
            ValueError: If request is invalid
            Exception: For OpenAI API errors

        Security Controls Applied Automatically:
        - Rate limiting checked before API call
        - Cost limits checked before API call
        - Request recorded for rate limiting
        - Cost tracked after successful call
        """
        if not user_id:
            raise ValueError(
                "user_id is required for OpenAI API calls (for security tracking)"
            )

        # Check rate limit
        allowed, retry_after = can_make_request(user_id)
        if not allowed:
            logger.warning(
                f"OpenAI rate limit exceeded for user {user_id}. "
                f"Retry after {retry_after:.1f} seconds"
            )
            raise RateLimitExceededError(retry_after)

        # Check cost limits
        cost_allowed, cost_error, cost_exceeded_by = check_cost_limits(user_id)
        if not cost_allowed:
            logger.warning(
                f"OpenAI cost limit exceeded for user {user_id}. "
                f"Error: {cost_error}"
            )
            raise CostLimitExceededError(
                cost_error or "Daily cost limit exceeded.", cost_exceeded_by
            )

        # Build API parameters
        call_params: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "messages": messages,
            "timeout": timeout,
            **kwargs,  # Allow additional parameters
        }

        if max_tokens is not None:
            call_params["max_tokens"] = max_tokens

        if require_json:
            call_params["response_format"] = {"type": "json_object"}

        try:
            # Make API call
            response = self._client.chat.completions.create(**call_params)

            # Extract response content
            if not response or not response.choices:
                raise ValueError("Empty response from OpenAI API")

            content = response.choices[0].message.content
            if content is None:
                raise ValueError(
                    "OpenAI returned None content - possibly hit token limit"
                )

            # Extract token usage (standardized format)
            usage_dict = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
            try:
                usage = getattr(response, "usage", None)
                if usage:
                    usage_dict = {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    }
            except Exception:
                pass

            # Calculate cost
            cost = record_request_cost(
                user_id=user_id,
                model=model,
                prompt_tokens=usage_dict["prompt_tokens"],
                completion_tokens=usage_dict["completion_tokens"],
            )

            # Record successful request (for rate limiting)
            record_request(user_id)

            # Extract request ID if available
            request_id = getattr(response, "id", None)

            logger.debug(
                f"OpenAI API call successful: user={user_id}, model={model}, "
                f"tokens={usage_dict['total_tokens']}, cost=${cost:.6f}"
            )

            return OpenAIResponse(
                content=content.strip(),
                usage=usage_dict,
                cost=cost,
                model=model,
                request_id=request_id,
            )

        except Exception as e:
            logger.error(
                f"OpenAI API call failed: user={user_id}, model={model}, error={e}"
            )
            # Don't record failed requests for rate limiting or cost tracking
            raise


def get_openai_service() -> OpenAIService:
    """
    Get global OpenAIService instance.

    Returns:
        OpenAIService instance (singleton pattern)
    """
    if not hasattr(get_openai_service, "_instance"):
        get_openai_service._instance = OpenAIService()  # type: ignore
    return get_openai_service._instance  # type: ignore

import logging
from typing import Any, Dict, List, Optional

from src.services.security.external_apis.openai_service import (
    OpenAIService,
    RateLimitExceededError,
    CostLimitExceededError,
    get_openai_service,
)

logger = logging.getLogger(__name__)


class OpenAIClientAdapter:
    """
    Adapter for OpenAI SDK that matches LLMClient protocol.

    Uses unified OpenAIService with automatic rate limiting and cost tracking.

    NOTE: user_id should be provided in config dict for security tracking.
    If not provided, a warning is logged and a fallback ID is used.
    """

    def __init__(self, client: Any = None) -> None:
        """
        Initialize adapter.

        Args:
            client: Optional OpenAIService instance (for testing).
                    If None, uses global service instance.
        """
        if isinstance(client, OpenAIService):
            self._service = client
        else:
            # Use global service instance
            self._service = get_openai_service()

    def completion(self, messages: List[Dict[str, str]], config: Dict[str, Any]) -> str:
        """
        Call OpenAI API and return the response content as a string.

        Uses unified OpenAIService with automatic security controls.

        Args:
            messages: List of message dicts with 'role' and 'content'
            config: Dict with:
                - 'model': Model name (default: 'gpt-4')
                - 'temperature': Sampling temperature (default: 0.7)
                - 'response_format': Optional response format dict
                - 'timeout': Request timeout in seconds (default: 30.0)
                - 'user_id': User identifier (REQUIRED for security tracking)
                - 'max_tokens': Optional max tokens
                - Other OpenAI API parameters

        Returns:
            Response content as string

        Raises:
            RateLimitExceededError: If rate limit exceeded
            CostLimitExceededError: If cost limit exceeded
            ValueError: If request is invalid
            Exception: For OpenAI API errors
        """
        model = config.get("model", "gpt-4")
        temperature = config.get("temperature", 0.7)
        response_format = config.get("response_format")
        timeout = config.get("timeout", 30.0)
        max_tokens = config.get("max_tokens")
        user_id = config.get("user_id")

        # user_id is required for security tracking
        if not user_id:
            logger.warning(
                "OpenAIClientAdapter: user_id not provided in config. "
                "Using fallback 'system' for tracking. "
                "Please provide user_id in config for proper rate limiting and cost tracking."
            )
            user_id = "system"  # Fallback for backward compatibility

        try:
            # Use unified OpenAI service (automatic rate limiting + cost tracking)
            response = self._service.chat_completion(
                messages=messages,
                user_id=str(user_id),
                model=model,
                temperature=temperature,
                timeout=timeout,
                max_tokens=max_tokens,
                require_json=bool(
                    response_format and response_format.get("type") == "json_object"
                ),
            )

            return response.content

        except (RateLimitExceededError, CostLimitExceededError) as e:
            # Re-raise security errors (caller should handle)
            logger.error(f"OpenAI security limit exceeded: {e}")
            raise
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

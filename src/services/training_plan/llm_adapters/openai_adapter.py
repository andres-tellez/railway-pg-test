import os
import logging
from typing import Any, Dict, List

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

logger = logging.getLogger(__name__)


class OpenAIClientAdapter:
    """
    Adapter for OpenAI SDK that matches LLMClient protocol.

    Uses the new OpenAI SDK (v1.0+) with chat.completions.create().
    Falls back gracefully if SDK not available.
    """

    def __init__(self, client: Any = None) -> None:
        if client is not None:
            self._client = client
        elif OpenAI is not None:
            # Create client from env (uses OPENAI_API_KEY)
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self._client = OpenAI(api_key=api_key)
        else:
            raise ValueError(
                "OpenAI SDK not available - install with: pip install openai"
            )

    def completion(self, messages: List[Dict[str, str]], config: Dict[str, Any]) -> str:
        """
        Call OpenAI API and return the response content as a string.

        Args:
            messages: List of message dicts with 'role' and 'content'
            config: Dict with 'model', 'temperature', 'response_format', etc.

        Returns:
            Response content as string

        Raises:
            Exception: For network errors, API errors, timeouts, etc.
        """
        model = config.get("model", "gpt-4")
        temperature = config.get("temperature", 0.7)
        response_format = config.get("response_format")
        timeout = config.get("timeout", 30.0)

        # Build API params
        call_params: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "messages": messages,
            "timeout": timeout,
        }

        # Only add response_format if provided (OpenAI supports JSON mode)
        if response_format:
            call_params["response_format"] = response_format

        try:
            response = self._client.chat.completions.create(**call_params)

            # Extract content
            if not response or not response.choices:
                raise ValueError("Empty response from OpenAI API")

            content = response.choices[0].message.content
            if content is None:
                raise ValueError(
                    "OpenAI returned None content - possibly hit token limit"
                )

            # Optional: log token usage
            usage = getattr(response, "usage", None)
            if usage:
                logger.debug(
                    f"OpenAI token usage: prompt={usage.prompt_tokens} "
                    f"completion={usage.completion_tokens} total={usage.total_tokens}"
                )

            return content.strip()

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

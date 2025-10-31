import os
from typing import Any, Dict, List
import logging

logger = logging.getLogger(__name__)


class FakeEnvLLMClient:
    """
    Simple fake client that returns a JSON string from env (for offline tests/smoke).
    Falls back to a tiny valid plan if FAKE_LLM_JSON_RESPONSE is not provided.
    """

    def __init__(self) -> None:
        self._default = '{"plan_name":"EnvFake","weeks":[{"week_number":1,"workouts":[{"day":"Mon","workout_type":"Easy Run","distance_miles":3.0}]}]}'

    def completion(self, messages: List[Dict[str, str]], config: Dict[str, Any]) -> str:
        return os.getenv("FAKE_LLM_JSON_RESPONSE", self._default)


def create_llm_client() -> Any:
    """
    Create LLM client based on environment variable.

    Environment variables:
        TRAINING_PLAN_LLM_PROVIDER: "fake" (default) or "openai"
        OPENAI_API_KEY: Required if provider is "openai"
        FAKE_LLM_JSON_RESPONSE: Optional JSON string for fake provider (for testing)
    """
    provider = (os.getenv("TRAINING_PLAN_LLM_PROVIDER") or "fake").lower()
    logger.info(f"[LLM_FACTORY] Provider selected: {provider}")
    if provider == "fake":
        return FakeEnvLLMClient()
    if provider == "openai":
        from .llm_adapters.openai_adapter import OpenAIClientAdapter

        # Creates client from OPENAI_API_KEY env var
        api_key_present = bool(os.getenv("OPENAI_API_KEY"))
        logger.info(
            f"[LLM_FACTORY] Using OpenAI adapter. OPENAI_API_KEY present={api_key_present}"
        )
        return OpenAIClientAdapter()
    raise ValueError(f"Unknown TRAINING_PLAN_LLM_PROVIDER: {provider}")

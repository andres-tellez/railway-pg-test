"""LLM provider adapters for Layer 4."""

from .base import LLMClient
from .openai_adapter import OpenAIClientAdapter

__all__ = ["LLMClient", "OpenAIClientAdapter"]

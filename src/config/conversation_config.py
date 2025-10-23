# src/config/conversation_config.py

import os
from typing import Dict, List


class ConversationConfig:
    """Centralized configuration for conversation system - highly tweakable"""

    # GPT Model Configuration
    GPT_MODEL = os.getenv("OPENAI_CONVERSATION_MODEL", "gpt-3.5-turbo")
    GPT_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    GPT_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "500"))
    GPT_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "30"))

    # Context Limits (simplified for comprehensive loading)
    CONTEXT_LIMITS = {
        "max_conversation_history": int(os.getenv("MAX_CONVERSATION_HISTORY", "10")),
        "max_activities": int(
            os.getenv("MAX_ACTIVITIES", "20")
        ),  # Increased for comprehensive loading
        "max_context_tokens": int(os.getenv("MAX_CONTEXT_TOKENS", "2000")),
    }

    # Context Triggers - REMOVED: Using comprehensive data loading instead
    # This simplifies the system and improves reliability by always loading recent data

    # Cache Settings (simplified - caching disabled for simplicity)
    CACHE_SETTINGS = {
        "enable_cache": False,  # Disabled for simplicity
    }

    # Compliance Settings
    COMPLIANCE = {
        "require_consent": os.getenv("REQUIRE_CONSENT", "true").lower() == "true",
        "enable_transparency": os.getenv("ENABLE_TRANSPARENCY", "true").lower()
        == "true",
        "log_interactions": os.getenv("LOG_INTERACTIONS", "true").lower() == "true",
        "data_retention_days": int(os.getenv("DATA_RETENTION_DAYS", "730")),  # 2 years
    }

    # Database View Names (simplified)
    DATABASE_VIEWS = {
        "activities": "v_activities_running_plan",
    }

    @classmethod
    def get_context_limit(cls, context_type: str) -> int:
        """Get context limit for specific type"""
        return cls.CONTEXT_LIMITS.get(f"max_{context_type}", 10)

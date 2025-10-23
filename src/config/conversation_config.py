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

    # Context Limits (easily tweakable)
    CONTEXT_LIMITS = {
        "max_conversation_history": int(os.getenv("MAX_CONVERSATION_HISTORY", "10")),
        "max_activities": int(os.getenv("MAX_ACTIVITIES", "10")),
        "max_training_workouts": int(os.getenv("MAX_TRAINING_WORKOUTS", "7")),
        "max_splits": int(os.getenv("MAX_SPLITS", "50")),
        "max_context_tokens": int(os.getenv("MAX_CONTEXT_TOKENS", "2000")),
    }

    # Context Triggers (easily tweakable keywords)
    CONTEXT_TRIGGERS = {
        "training_plan": [
            "plan",
            "training",
            "workout",
            "schedule",
            "race",
            "taper",
            "mileage",
        ],
        "activities": [
            "run",
            "pace",
            "performance",
            "time",
            "distance",
            "mile",
            "speed",
        ],
        "splits": ["split", "mile", "pace", "consistency", "speed", "heart rate"],
        "profile": [
            "goal",
            "level",
            "experience",
            "weight",
            "height",
            "age",
            "preference",
        ],
        "health": ["heart rate", "hr", "health", "medical", "injury", "pain"],
    }

    # Cache Settings (easily tweakable)
    CACHE_SETTINGS = {
        "ttl_minutes": int(os.getenv("CACHE_TTL_MINUTES", "5")),
        "max_size": int(os.getenv("CACHE_MAX_SIZE", "100")),
        "enable_cache": os.getenv("ENABLE_CACHE", "true").lower() == "true",
    }

    # Performance Settings
    PERFORMANCE = {
        "enable_async": os.getenv("ENABLE_ASYNC", "true").lower() == "true",
        "connection_pool_size": int(os.getenv("CONNECTION_POOL_SIZE", "10")),
        "query_timeout": int(os.getenv("QUERY_TIMEOUT", "30")),
        "enable_compression": os.getenv("ENABLE_COMPRESSION", "true").lower() == "true",
    }

    # Compliance Settings
    COMPLIANCE = {
        "require_consent": os.getenv("REQUIRE_CONSENT", "true").lower() == "true",
        "enable_transparency": os.getenv("ENABLE_TRANSPARENCY", "true").lower()
        == "true",
        "log_interactions": os.getenv("LOG_INTERACTIONS", "true").lower() == "true",
        "data_retention_days": int(os.getenv("DATA_RETENTION_DAYS", "730")),  # 2 years
    }

    # Database View Names (easily tweakable)
    DATABASE_VIEWS = {
        "activities": os.getenv("ACTIVITIES_VIEW", "v_activities_running_plan"),
        "splits": os.getenv("SPLITS_VIEW", "v_splits_running_plan"),
    }

    @classmethod
    def should_load_context(cls, message_content: str, context_type: str) -> bool:
        """Determine if context should be loaded based on message content"""
        message_lower = message_content.lower()
        keywords = cls.CONTEXT_TRIGGERS.get(context_type, [])
        return any(keyword in message_lower for keyword in keywords)

    @classmethod
    def get_context_limit(cls, context_type: str) -> int:
        """Get context limit for specific type"""
        return cls.CONTEXT_LIMITS.get(f"max_{context_type}", 10)

    @classmethod
    def is_cache_enabled(cls) -> bool:
        """Check if caching is enabled"""
        return cls.CACHE_SETTINGS["enable_cache"]

    @classmethod
    def is_async_enabled(cls) -> bool:
        """Check if async operations are enabled"""
        return cls.PERFORMANCE["enable_async"]

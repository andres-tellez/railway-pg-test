"""
Configuration management for Coach system.

Loads configuration from environment variables and config files.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Centralized configuration for Coach system."""

    BASE_DIR = Path(__file__).parent.parent.parent
    CONFIG_DIR = BASE_DIR / "config"

    # Feature flags
    COACH_V2_ENABLED = os.getenv("COACH_V2_ENABLED", "false").lower() == "true"
    COACH_SHADOW_MODE_ENABLED = (
        os.getenv("COACH_SHADOW_MODE_ENABLED", "false").lower() == "true"
    )
    COACH_SHADOW_MODE_PERCENTAGE = int(os.getenv("COACH_SHADOW_MODE_PERCENTAGE", "10"))

    # LLM Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_CONVERSATION_MODEL", "gpt-4o")
    OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "30.0"))

    # Cache Configuration
    RUNNER_STATE_CACHE_TTL = int(
        os.getenv("RUNNER_STATE_CACHE_TTL", "86400")
    )  # 24 hours

    # Cost Tracking
    COST_ALERT_SINGLE_REQUEST_THRESHOLD = float(
        os.getenv("COST_ALERT_SINGLE_REQUEST_THRESHOLD", "0.10")
    )
    COST_ALERT_USER_DAILY_THRESHOLD = float(
        os.getenv("COST_ALERT_USER_DAILY_THRESHOLD", "0.50")
    )
    COST_ALERT_GLOBAL_DAILY_THRESHOLD = float(
        os.getenv("COST_ALERT_GLOBAL_DAILY_THRESHOLD", "100.0")
    )

    # Performance
    MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "3000"))

    _config_cache: Dict[str, Any] = {}

    @classmethod
    def load_yaml_config(cls, filename: str) -> Dict[str, Any]:
        """
        Load YAML config file.

        Args:
            filename: Name of config file

        Returns:
            Config dict
        """
        if filename not in cls._config_cache:
            config_file = cls.CONFIG_DIR / filename
            if config_file.exists():
                with open(config_file, "r") as f:
                    cls._config_cache[filename] = yaml.safe_load(f)
            else:
                cls._config_cache[filename] = {}

        return cls._config_cache[filename]

    @classmethod
    def get_model_pricing(cls) -> Dict[str, Dict[str, float]]:
        """
        Get model pricing configuration.

        Returns:
            Dict mapping model names to input/output prices per 1M tokens
        """
        pricing_config = cls.load_yaml_config("model_pricing.yaml")
        return pricing_config.get(
            "models",
            {
                "gpt-4o": {"input": 2.50, "output": 10.00},
                "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            },
        )

    @classmethod
    def get_thresholds(cls, key: Optional[str] = None, default: Any = None) -> Any:
        """
        Get threshold configuration.

        Args:
            key: Optional key to get specific threshold value (dot-separated path)
            default: Default value if key not found

        Returns:
            Dict of threshold values if key is None, or specific value if key provided
        """
        thresholds = cls.load_yaml_config("thresholds.yaml")
        if key is None:
            return thresholds
        # Support dot-separated keys like "long_run_distance_threshold"
        keys = key.split(".")
        val = thresholds
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    @classmethod
    def get_safety_flags(cls) -> Dict[str, Any]:
        """Get safety flags configuration."""
        safety_flags_path = cls.CONFIG_DIR / "safety_flags.yaml"
        if safety_flags_path.exists():
            with open(safety_flags_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {
            "critical_flags": [],
            "moderate_flags": [],
            "pattern_flags": [],
        }

    @classmethod
    def get_llm_config(cls, key: Optional[str] = None, default: Any = None) -> Any:
        """
        Get LLM configuration.

        Args:
            key: Optional key to get specific config value (dot-separated path)
            default: Default value if key not found

        Returns:
            Dict of LLM config values if key is None, or specific value if key provided
        """
        # For now, use environment variables with fallbacks
        # Could be extended to load from llm_config.yaml if needed
        config = {
            "default_model": cls.OPENAI_MODEL,
            "default_temperature": cls.OPENAI_TEMPERATURE,
            "default_max_tokens": cls.OPENAI_MAX_TOKENS,
            "default_timeout": cls.OPENAI_TIMEOUT,
        }

        if key is None:
            return config

        # Support dot-separated keys
        keys = key.split(".")
        val = config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default

        return val if val is not None else default

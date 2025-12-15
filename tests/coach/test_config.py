"""
Tests for configuration management.

These tests verify that configuration is loaded correctly
from environment variables and config files.
"""

import pytest
import os
from coach.utils.config import Config


class TestConfig:
    """Test configuration management."""

    def test_feature_flags_defaults(self):
        """Test feature flags have correct defaults."""
        # Note: These tests may need environment isolation
        assert isinstance(Config.COACH_V2_ENABLED, bool)
        assert isinstance(Config.COACH_SHADOW_MODE_ENABLED, bool)
        assert Config.COACH_SHADOW_MODE_PERCENTAGE >= 0
        assert Config.COACH_SHADOW_MODE_PERCENTAGE <= 100

    def test_llm_config_defaults(self):
        """Test LLM configuration has correct defaults."""
        assert Config.OPENAI_MODEL == "gpt-4o"
        assert 0.0 <= Config.OPENAI_TEMPERATURE <= 2.0
        assert Config.OPENAI_MAX_TOKENS > 0
        assert Config.OPENAI_TIMEOUT > 0

    def test_get_model_pricing(self):
        """Test loading model pricing config."""
        pricing = Config.get_model_pricing()
        assert isinstance(pricing, dict)
        assert "gpt-4o" in pricing
        assert "input" in pricing["gpt-4o"]
        assert "output" in pricing["gpt-4o"]

    def test_get_thresholds(self):
        """Test loading thresholds config."""
        thresholds = Config.get_thresholds()
        assert isinstance(thresholds, dict)
        # Should have common thresholds
        assert "hr_drift_bpm" in thresholds or thresholds == {}

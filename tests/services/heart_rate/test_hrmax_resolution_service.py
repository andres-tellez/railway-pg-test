"""
Tests for HRMax Resolution Service
"""

import pytest
from datetime import datetime, timedelta
from src.services.heart_rate.hrmax_resolution_service import HRMaxResolutionService


class TestHRMaxResolution:
    """Test HRmax resolution logic."""

    def test_user_override_always_wins(self):
        """Test that USER override always takes precedence."""
        profile = {
            "max_hr": 185,
            "max_hr_source": "USER",
        }

        effective = HRMaxResolutionService.get_effective_max_hr(profile)

        assert effective == 185

    def test_user_override_invalid_returns_none(self):
        """Test that invalid user override returns None."""
        profile = {
            "max_hr": 250,  # Invalid
            "max_hr_source": "USER",
        }

        effective = HRMaxResolutionService.get_effective_max_hr(profile)

        assert effective is None

    def test_auto_source_returns_max_hr(self):
        """Test that AUTO source returns max_hr."""
        profile = {
            "max_hr": 180,
            "max_hr_source": "AUTO",
        }

        effective = HRMaxResolutionService.get_effective_max_hr(profile)

        assert effective == 180

    def test_strava_source_returns_max_hr(self):
        """Test that STRAVA source returns max_hr."""
        profile = {
            "max_hr": 175,
            "max_hr_source": "STRAVA",
        }

        effective = HRMaxResolutionService.get_effective_max_hr(profile)

        assert effective == 175

    def test_no_source_returns_none(self):
        """Test that no source returns None (must estimate)."""
        profile = {
            "max_hr": 180,
            "max_hr_source": None,
        }

        effective = HRMaxResolutionService.get_effective_max_hr(profile)

        assert effective is None

    def test_should_allow_auto_recalculation_user_override(self):
        """Test that USER override prevents auto-recalculation."""
        profile = {
            "max_hr_source": "USER",
        }

        should_recalc = HRMaxResolutionService.should_allow_auto_recalculation(profile)

        assert should_recalc is False

    def test_should_allow_auto_recalculation_auto_source(self):
        """Test that AUTO source allows auto-recalculation."""
        profile = {
            "max_hr_source": "AUTO",
        }

        should_recalc = HRMaxResolutionService.should_allow_auto_recalculation(profile)

        assert should_recalc is True

    def test_should_recalculate_no_stored_hrmax(self):
        """Test that missing HRmax triggers recalculation."""
        profile = {
            "max_hr": None,
            "max_hr_source": "AUTO",
        }

        should_recalc = HRMaxResolutionService.should_recalculate_hrmax(profile)

        assert should_recalc is True

    def test_should_recalculate_time_threshold(self):
        """Test that >30 days since calculation triggers recalculation."""
        profile = {
            "max_hr": 180,
            "max_hr_source": "AUTO",
            "hrmax_calculated_at": datetime.now() - timedelta(days=31),
        }

        should_recalc = HRMaxResolutionService.should_recalculate_hrmax(profile)

        assert should_recalc is True

    def test_should_recalculate_new_peak(self):
        """Test that new peak triggers recalculation."""
        profile = {
            "max_hr": 180,
            "max_hr_source": "AUTO",
            "hrmax_calculated_at": datetime.now() - timedelta(days=1),
        }

        should_recalc = HRMaxResolutionService.should_recalculate_hrmax(
            profile, new_activity_max_hr=185  # +5 bpm > threshold of 2
        )

        assert should_recalc is True

    def test_should_not_recalculate_user_override(self):
        """Test that USER override prevents recalculation."""
        profile = {
            "max_hr": 180,
            "max_hr_source": "USER",
        }

        should_recalc = HRMaxResolutionService.should_recalculate_hrmax(
            profile, new_activity_max_hr=190
        )

        assert should_recalc is False

    def test_update_max_hr_data_user_source(self):
        """Test updating profile with USER source."""
        profile_data = {}

        updated = HRMaxResolutionService.update_max_hr_data(
            profile_data, new_max_hr=185, source="USER"
        )

        assert updated["max_hr"] == 185
        assert updated["max_hr_source"] == "USER"
        assert updated.get("hrmax_calculated_at") is None

    def test_update_max_hr_data_auto_source(self):
        """Test updating profile with AUTO source."""
        profile_data = {}

        updated = HRMaxResolutionService.update_max_hr_data(
            profile_data,
            new_max_hr=180,
            source="AUTO",
            confidence="HIGH",
            activity_count=25,
        )

        assert updated["max_hr"] == 180
        assert updated["max_hr_source"] == "AUTO"
        assert updated["hrmax_confidence"] == "HIGH"
        assert updated["hrmax_activity_count"] == 25
        assert updated.get("hrmax_calculated_at") is not None

    def test_update_max_hr_data_invalid_user_override_raises(self):
        """Test that invalid user override raises ValueError."""
        profile_data = {}

        with pytest.raises(ValueError, match="Invalid user override"):
            HRMaxResolutionService.update_max_hr_data(
                profile_data, new_max_hr=250, source="USER"
            )

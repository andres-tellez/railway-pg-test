"""
Tests for HRMax Resolution Service
"""

import pytest
from datetime import datetime, timedelta
from src.services.heart_rate.hrmax_resolution_service import HRMaxResolutionService


class TestHRMaxResolution:
    """Test HRmax resolution logic."""

    def test_active_manual_valid(self):
        profile = {
            "max_hr_manual": 185,
            "max_hr_auto": 180,
            "max_hr_active": "manual",
        }
        assert HRMaxResolutionService.get_effective_max_hr(profile) == 185

    def test_active_auto(self):
        profile = {
            "max_hr_manual": 185,
            "max_hr_auto": 180,
            "max_hr_active": "auto",
        }
        assert HRMaxResolutionService.get_effective_max_hr(profile) == 180

    def test_active_manual_invalid_falls_back_to_auto(self):
        profile = {
            "max_hr_manual": 250,
            "max_hr_auto": 178,
            "max_hr_active": "manual",
        }
        assert HRMaxResolutionService.get_effective_max_hr(profile) == 178

    def test_unset_active_prefers_manual_then_auto(self):
        assert (
            HRMaxResolutionService.get_effective_max_hr(
                {"max_hr_manual": 182, "max_hr_auto": 175}
            )
            == 182
        )
        assert (
            HRMaxResolutionService.get_effective_max_hr(
                {"max_hr_manual": None, "max_hr_auto": 176}
            )
            == 176
        )

    def test_should_allow_auto_recalculation_always_true(self):
        assert HRMaxResolutionService.should_allow_auto_recalculation({}) is True
        assert (
            HRMaxResolutionService.should_allow_auto_recalculation(
                {"max_hr_manual": 180}
            )
            is True
        )

    def test_should_recalculate_no_stored_auto(self):
        profile = {"max_hr_auto": None, "max_hr_manual": 180}
        assert HRMaxResolutionService.should_recalculate_hrmax(profile) is True

    def test_should_recalculate_time_threshold(self):
        profile = {
            "max_hr_auto": 180,
            "hrmax_calculated_at": datetime.now() - timedelta(days=31),
        }
        assert HRMaxResolutionService.should_recalculate_hrmax(profile) is True

    def test_should_recalculate_new_peak(self):
        profile = {
            "max_hr_auto": 180,
            "hrmax_calculated_at": datetime.now() - timedelta(days=1),
        }
        assert (
            HRMaxResolutionService.should_recalculate_hrmax(
                profile, new_activity_max_hr=185
            )
            is True
        )

    def test_should_not_recalculate_recent_auto_small_peak(self):
        profile = {
            "max_hr_auto": 180,
            "max_hr_manual": 175,
            "hrmax_calculated_at": datetime.now() - timedelta(days=1),
        }
        assert (
            HRMaxResolutionService.should_recalculate_hrmax(
                profile, new_activity_max_hr=181
            )
            is False
        )

    def test_update_max_hr_data_user_source(self):
        profile_data = {}
        updated = HRMaxResolutionService.update_max_hr_data(
            profile_data, new_max_hr=185, source="USER"
        )
        assert updated["max_hr_manual"] == 185
        assert updated.get("hrmax_calculated_at") is None
        assert updated.get("max_hr_auto") is None

    def test_update_max_hr_data_auto_source(self):
        profile_data = {}
        updated = HRMaxResolutionService.update_max_hr_data(
            profile_data,
            new_max_hr=180,
            source="AUTO",
            confidence="HIGH",
            activity_count=25,
        )
        assert updated["max_hr_auto"] == 180
        assert updated["hrmax_confidence"] == "HIGH"
        assert updated["hrmax_activity_count"] == 25
        assert updated.get("hrmax_calculated_at") is not None

    def test_update_max_hr_data_invalid_user_override_raises(self):
        profile_data = {}
        with pytest.raises(ValueError, match="Invalid manual HRmax"):
            HRMaxResolutionService.update_max_hr_data(
                profile_data, new_max_hr=250, source="USER"
            )

    def test_auto_hrmax_estimate_rejects_low_confidence(self):
        ok, reason = HRMaxResolutionService.auto_hrmax_estimate_is_trustworthy(
            {"max_hr_manual": 172}, 165, "LOW"
        )
        assert ok is False
        assert reason == "low_confidence"

    def test_auto_hrmax_estimate_rejects_divergence_from_manual(self):
        ok, reason = HRMaxResolutionService.auto_hrmax_estimate_is_trustworthy(
            {"max_hr_manual": 172}, 156, "HIGH"
        )
        assert ok is False
        assert reason == "diverges_from_manual"

    def test_auto_hrmax_estimate_accepts_close_to_manual(self):
        ok, reason = HRMaxResolutionService.auto_hrmax_estimate_is_trustworthy(
            {"max_hr_manual": 172}, 168, "MEDIUM"
        )
        assert ok is True
        assert reason is None

    def test_stored_auto_unreliable_when_low_confidence(self):
        assert (
            HRMaxResolutionService.stored_max_hr_auto_is_unreliable(
                {
                    "max_hr_auto": 165,
                    "hrmax_confidence": "LOW",
                }
            )
            is True
        )

    def test_stored_auto_unreliable_when_diverges_from_manual(self):
        assert (
            HRMaxResolutionService.stored_max_hr_auto_is_unreliable(
                {
                    "max_hr_auto": 156,
                    "hrmax_confidence": "HIGH",
                    "max_hr_manual": 172,
                }
            )
            is True
        )

    def test_stored_auto_reliable_when_aligned(self):
        assert (
            HRMaxResolutionService.stored_max_hr_auto_is_unreliable(
                {
                    "max_hr_auto": 170,
                    "hrmax_confidence": "MEDIUM",
                    "max_hr_manual": 172,
                }
            )
            is False
        )

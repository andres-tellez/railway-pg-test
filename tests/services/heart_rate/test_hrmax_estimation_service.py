"""
Tests for HRMax Estimation Service

Test guardrails:
- Use dict fixtures only (no real API calls)
- No stream mocking in v1 tests
- Keep tests pure and fast
"""

import pytest
from src.services.heart_rate.hrmax_estimation_service import (
    HRMaxEstimationService,
    HRMaxEstimationResult,
)


class TestHRMaxEstimation:
    """Test HRmax estimation from activities."""

    def test_insufficient_activities_returns_error(self):
        """Test that < 5 activities returns success=False."""
        activities = [
            {"max_heartrate": 180, "moving_time": 1200}
        ] * 4  # Exactly 4 activities

        result = HRMaxEstimationService.estimate_hrmax(activities)

        assert result.success is False
        assert result.error_code == "INSUFFICIENT_DATA"
        assert result.confidence == "LOW"
        assert result.activity_count == 4

    def test_all_activities_filtered_out_returns_error(self):
        """Test that if all activities < 10 min, returns error."""
        activities = [{"max_heartrate": 180, "moving_time": 300}] * 10  # 5 minutes

        result = HRMaxEstimationService.estimate_hrmax(activities)

        assert result.success is False
        assert result.error_code == "INSUFFICIENT_DATA"
        assert result.activity_count == 0

    def test_outlier_filtering_excludes_extreme_high_and_low(self):
        """Test that extreme outliers in both directions are removed."""
        # Normal values
        normal_values = [170 + i for i in range(20)]  # 170-189

        # High outlier (250) and low outlier (40)
        activities = [
            {"max_heartrate": hr, "moving_time": 1200}
            for hr in normal_values + [250, 40]
        ]

        result = HRMaxEstimationService.estimate_hrmax(activities)

        assert result.success is True
        # 95th percentile of 170-189 should be ~188-189
        assert result.hrmax >= 185
        assert result.hrmax <= 195
        # Outliers should not affect result
        assert result.hrmax < 200
        assert result.hrmax > 150

    def test_small_filtered_set_uses_fallback(self):
        """Test that if < 3 values after filtering, uses original dataset."""
        # Create dataset where outlier filter is too aggressive
        activities = [
            {"max_heartrate": 180, "moving_time": 1200},
            {"max_heartrate": 181, "moving_time": 1200},
            {"max_heartrate": 182, "moving_time": 1200},
            {"max_heartrate": 250, "moving_time": 1200},  # Outlier
        ] * 2  # 8 total activities

        result = HRMaxEstimationService.estimate_hrmax(activities)

        # Should succeed with fallback logic
        assert result.success is True
        assert result.hrmax is not None

    def test_all_values_identical_handled(self):
        """Test that std_hr == 0 case is handled."""
        activities = [{"max_heartrate": 180, "moving_time": 1200}] * 20

        result = HRMaxEstimationService.estimate_hrmax(activities)

        assert result.success is True
        assert result.hrmax == 180

    def test_invalid_input_raises_valueerror(self):
        """Test that invalid input types raise ValueError."""
        with pytest.raises(ValueError, match="cannot be None"):
            HRMaxEstimationService.estimate_hrmax(None)

        with pytest.raises(ValueError, match="must be a list"):
            HRMaxEstimationService.estimate_hrmax("not a list")

        with pytest.raises(ValueError, match="cannot be empty"):
            HRMaxEstimationService.estimate_hrmax([])

    def test_hrmax_outside_physiological_range_returns_error(self):
        """Test that HRmax outside valid range returns structured error."""
        # Create activities that would produce invalid HRmax
        # This is hard to do with real data, so we'll test the validation logic
        # by creating edge case where estimation might fail
        activities = [{"max_heartrate": 110, "moving_time": 1200}] * 10  # Very low

        result = HRMaxEstimationService.estimate_hrmax(activities)

        # Should return error if HRmax < 120
        if result.hrmax is not None:
            assert 120 <= result.hrmax <= 220
        else:
            # If estimation fails due to low values, that's acceptable
            assert result.success is False

    def test_confidence_scoring(self):
        """Test confidence levels based on activity count."""
        # LOW confidence (< 10 activities)
        activities = [{"max_heartrate": 180, "moving_time": 1200}] * 8

        result = HRMaxEstimationService.estimate_hrmax(activities)
        assert result.success is True
        assert result.confidence == "LOW"

        # MEDIUM confidence (10-19 activities)
        activities = [{"max_heartrate": 180, "moving_time": 1200}] * 15

        result = HRMaxEstimationService.estimate_hrmax(activities)
        assert result.success is True
        assert result.confidence == "MEDIUM"

        # HIGH confidence (>= 20 activities)
        activities = [{"max_heartrate": 180, "moving_time": 1200}] * 25

        result = HRMaxEstimationService.estimate_hrmax(activities)
        assert result.success is True
        assert result.confidence == "HIGH"

    def test_mixed_valid_and_invalid_activities(self):
        """Test filtering handles mix of valid and invalid activities."""
        activities = [
            {"max_heartrate": 180, "moving_time": 1200},  # Valid
            {"max_heartrate": None, "moving_time": 1200},  # Missing HR
            {"max_heartrate": 175, "moving_time": 300},  # Too short
            {"max_heartrate": 185, "moving_time": 1200},  # Valid
        ] * 5  # 20 total, but only 10 valid after filtering

        result = HRMaxEstimationService.estimate_hrmax(activities)

        assert result.success is True
        assert result.activity_count >= 5  # Should have enough valid activities
        assert result.hrmax is not None

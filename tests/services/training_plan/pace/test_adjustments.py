"""
Tests for pace adjustments based on weekly feedback.
"""

import pytest
from src.services.training_plan.pace import (
    PaceSeed,
    adjust_pace_seed,
    WeekLogRun,
    validate_pace_seed,
)


class TestAdjustPaceSeed:
    """Test pace seed adjustments."""

    def setup_method(self):
        """Create a base pace seed for testing."""
        self.base_seed = PaceSeed(
            E_min=570.0,  # Adjusted to overlap with Steady
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

    def test_no_adjustment_empty_week_log(self):
        """Test no adjustment when week_log is empty."""
        adjusted_seed, disable_quality = adjust_pace_seed(self.base_seed, [])
        assert adjusted_seed == self.base_seed
        assert disable_quality is False

    def test_no_adjustment_normal_week(self):
        """Test no adjustment for normal week (good completion, moderate RPE)."""
        week_log = [
            WeekLogRun(run_type="easy", planned_mi=4.0, done_mi=4.0, rpe=3),
            WeekLogRun(run_type="steady", planned_mi=5.0, done_mi=5.0, rpe=4),
        ]
        adjusted_seed, disable_quality = adjust_pace_seed(self.base_seed, week_log)
        assert adjusted_seed == self.base_seed
        assert disable_quality is False

    def test_adjustment_low_completion(self):
        """Test paces slow down when completion < 60%."""
        week_log = [
            WeekLogRun(run_type="easy", planned_mi=4.0, done_mi=2.0, rpe=5),
            WeekLogRun(run_type="steady", planned_mi=5.0, done_mi=2.5, rpe=6),
        ]
        adjusted_seed, disable_quality = adjust_pace_seed(self.base_seed, week_log)

        # All paces should be 15 seconds slower
        assert adjusted_seed.E_min == self.base_seed.E_min + 15
        assert adjusted_seed.E_max == self.base_seed.E_max + 15
        assert adjusted_seed.M == self.base_seed.M + 15
        assert adjusted_seed.T_min == self.base_seed.T_min + 15
        assert disable_quality is True

        # Validate adjusted seed
        is_valid, error_msg = validate_pace_seed(adjusted_seed)
        assert is_valid is True, f"Adjusted seed failed validation: {error_msg}"

    def test_adjustment_high_rpe(self):
        """Test paces slow down when RPE >= 5.0."""
        week_log = [
            WeekLogRun(run_type="easy", planned_mi=4.0, done_mi=4.0, rpe=5),
            WeekLogRun(run_type="steady", planned_mi=5.0, done_mi=5.0, rpe=6),
        ]
        adjusted_seed, disable_quality = adjust_pace_seed(self.base_seed, week_log)

        # All paces should be 10 seconds slower
        assert adjusted_seed.E_min == self.base_seed.E_min + 10
        assert adjusted_seed.E_max == self.base_seed.E_max + 10
        assert adjusted_seed.M == self.base_seed.M + 10
        assert disable_quality is True

    def test_adjustment_excellent_recovery(self):
        """Test paces speed up when RPE <= 2.0 and completion >= 80%."""
        week_log = [
            WeekLogRun(run_type="easy", planned_mi=4.0, done_mi=4.0, rpe=2),
            WeekLogRun(run_type="steady", planned_mi=5.0, done_mi=5.0, rpe=1),
        ]
        adjusted_seed, disable_quality = adjust_pace_seed(self.base_seed, week_log)

        # All paces should be 5 seconds faster
        assert adjusted_seed.E_min == self.base_seed.E_min - 5
        assert adjusted_seed.E_max == self.base_seed.E_max - 5
        assert adjusted_seed.M == self.base_seed.M - 5
        assert disable_quality is False

    def test_adjustment_week1_long_cap_unchanged(self):
        """Test week1_long_cap is not adjusted."""
        week_log = [
            WeekLogRun(run_type="easy", planned_mi=4.0, done_mi=2.0, rpe=5),
        ]
        adjusted_seed, _ = adjust_pace_seed(self.base_seed, week_log)
        assert adjusted_seed.week1_long_cap == self.base_seed.week1_long_cap

    def test_adjustment_invalid_seed_raises_error(self):
        """Test adjustment raises error for invalid seed."""
        invalid_seed = PaceSeed(
            E_min=700.0,  # Invalid: > E_max
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )
        week_log = [
            WeekLogRun(run_type="easy", planned_mi=4.0, done_mi=4.0, rpe=3),
        ]

        with pytest.raises(ValueError, match="Invalid input seed"):
            adjust_pace_seed(invalid_seed, week_log)

    def test_calculate_completion_rate(self):
        """Test completion rate calculation."""
        week_log = [
            WeekLogRun(run_type="easy", planned_mi=4.0, done_mi=2.0, rpe=3),
            WeekLogRun(run_type="steady", planned_mi=5.0, done_mi=2.5, rpe=4),
        ]
        # Total planned: 9.0, Total done: 4.5, Rate: 50%
        adjusted_seed, disable_quality = adjust_pace_seed(self.base_seed, week_log)
        assert disable_quality is True  # 50% < 60%

    def test_calculate_avg_rpe(self):
        """Test average RPE calculation for easy/steady runs."""
        week_log = [
            WeekLogRun(run_type="easy", planned_mi=4.0, done_mi=4.0, rpe=2),
            WeekLogRun(run_type="steady", planned_mi=5.0, done_mi=5.0, rpe=1),
            WeekLogRun(
                run_type="long", planned_mi=10.0, done_mi=10.0, rpe=5
            ),  # Not included
        ]
        # Avg RPE for easy/steady: (2 + 1) / 2 = 1.5
        adjusted_seed, disable_quality = adjust_pace_seed(self.base_seed, week_log)
        # Should speed up (RPE <= 2.0 and completion >= 80%)
        assert adjusted_seed.E_min < self.base_seed.E_min
        assert disable_quality is False

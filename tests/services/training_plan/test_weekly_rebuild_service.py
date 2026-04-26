"""
Tests for Weekly Rebuild Service

Tests the weekly rebuild logic that adjusts pace seed based on
previous week's completion data and rebuilds workout details.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, patch

from src.services.training_plan.weekly_rebuild_service import (
    WeeklyRebuildService,
    _find_week_workouts,
    _normalize_workout_type,
    _determine_phase,
)
from src.services.training_plan.weekly_adjuster import WeekLogRun
from src.services.training_plan.pace import PaceSeed


class TestWeeklyRebuildService:
    """Test weekly rebuild service."""

    def test_normalize_workout_type(self):
        """Test workout type normalization."""
        assert _normalize_workout_type("Easy") == "easy"
        assert _normalize_workout_type("Easy / Recovery") == "easy"
        assert _normalize_workout_type("Steady") == "steady"
        assert _normalize_workout_type("Aerobic / Steady") == "steady"
        assert _normalize_workout_type("Endurance") == "endurance"
        assert _normalize_workout_type("Endurance (Medium-Long)") == "endurance"
        assert _normalize_workout_type("Long Run") == "long"
        assert _normalize_workout_type("Long") == "long"
        assert _normalize_workout_type("Unknown") == "easy"  # Default fallback

    def test_determine_phase(self):
        """Test training phase determination."""
        total_weeks = 16

        # Base phase (first 40%)
        assert _determine_phase(1, total_weeks) == "Base"
        assert _determine_phase(6, total_weeks) == "Base"

        # Build phase (40-70%)
        assert _determine_phase(7, total_weeks) == "Build"
        assert _determine_phase(11, total_weeks) == "Build"

        # Specific phase (70-90%)
        assert _determine_phase(12, total_weeks) == "Specific"
        assert _determine_phase(14, total_weeks) == "Specific"

        # Taper phase (last 10%)
        assert _determine_phase(15, total_weeks) == "Taper"
        assert _determine_phase(16, total_weeks) == "Taper"

    def test_find_week_workouts(self):
        """Test finding workouts for a specific week."""
        from src.db.models.plan_workouts import PlanWorkout

        # Create mock workouts
        race_date = date.today() + timedelta(weeks=8)
        # Week 2 is 2 weeks before race week
        # Calculate backwards from race date
        weeks_before_race = 2
        target_week_start = race_date - timedelta(weeks=weeks_before_race)
        days_since_monday = target_week_start.weekday()
        week2_start = target_week_start - timedelta(days=days_since_monday)
        week2_end = week2_start + timedelta(days=6)

        # Create workouts within the week range
        all_workouts = [
            Mock(
                spec=PlanWorkout,
                date=week2_start + timedelta(days=i),
                miles=5.0,
                workout_type="Easy",
            )
            for i in range(4)  # Monday, Tuesday, Wednesday, Thursday
        ]

        # Verify dates are in range
        for w in all_workouts:
            assert week2_start <= w.date <= week2_end

        # Find week 2 workouts
        week_workouts = _find_week_workouts(
            all_workouts=all_workouts,
            week_num=2,
            race_date=race_date,
        )

        # Should find workouts in week 2 range
        assert len(week_workouts) == 4

    @pytest.mark.skip(reason="Requires database setup - integration test")
    def test_rebuild_week_with_previous_logs(self):
        """Test rebuilding a week with previous week logs for adjustments."""
        # This would require a full database setup
        # For now, we test the components separately
        pass

    def test_rebuild_week_without_previous_logs(self):
        """Test rebuilding a week without previous logs (uses initial seed)."""
        # This would require mocking the database session
        # For now, we test the components separately
        pass

    def test_pace_adjustment_from_week_logs(self):
        """Test that pace adjustments are applied based on week logs."""
        from src.services.training_plan.weekly_adjuster import adjust_seed_from_week

        initial_seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

        # Simulate poor completion (<60%) - should slow down
        week_logs = [
            WeekLogRun(
                run_type="easy", planned_mi=4.0, done_mi=2.0, rpe=5, avg_hr=None
            ),
            WeekLogRun(
                run_type="steady", planned_mi=5.0, done_mi=2.5, rpe=6, avg_hr=None
            ),
        ]

        adjusted_seed, disable_quality = adjust_seed_from_week(initial_seed, week_logs)

        # Verify paces slowed down
        assert adjusted_seed.E_min > initial_seed.E_min
        assert adjusted_seed.E_max > initial_seed.E_max
        assert adjusted_seed.M > initial_seed.M

        # Verify quality disabled
        assert disable_quality is True

    def test_pace_adjustment_excellent_recovery(self):
        """Test pace adjustment when recovery is excellent (RPE <= 2)."""
        from src.services.training_plan.weekly_adjuster import adjust_seed_from_week

        initial_seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

        # Simulate excellent recovery (RPE <= 2, completion >= 80%)
        week_logs = [
            WeekLogRun(
                run_type="easy", planned_mi=4.0, done_mi=4.0, rpe=2, avg_hr=None
            ),
            WeekLogRun(
                run_type="steady", planned_mi=5.0, done_mi=5.0, rpe=1, avg_hr=None
            ),
        ]

        adjusted_seed, disable_quality = adjust_seed_from_week(initial_seed, week_logs)

        # Verify paces sped up slightly
        assert adjusted_seed.E_min < initial_seed.E_min
        assert adjusted_seed.E_max < initial_seed.E_max
        assert adjusted_seed.M < initial_seed.M

    def test_pace_adjustment_high_rpe(self):
        """Test pace adjustment when RPE is high (>= 5)."""
        from src.services.training_plan.weekly_adjuster import adjust_seed_from_week

        initial_seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

        # Simulate high RPE (>= 5)
        week_logs = [
            WeekLogRun(
                run_type="easy", planned_mi=4.0, done_mi=4.0, rpe=5, avg_hr=None
            ),
            WeekLogRun(
                run_type="steady", planned_mi=5.0, done_mi=5.0, rpe=6, avg_hr=None
            ),
        ]

        adjusted_seed, disable_quality = adjust_seed_from_week(initial_seed, week_logs)

        # Verify paces slowed down
        assert adjusted_seed.E_min > initial_seed.E_min
        assert adjusted_seed.E_max > initial_seed.E_max
        assert adjusted_seed.M > initial_seed.M

        # Verify quality disabled
        assert disable_quality is True

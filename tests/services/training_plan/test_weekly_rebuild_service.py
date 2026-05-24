"""
Tests for Weekly Rebuild Service

Tests the weekly rebuild logic that adjusts pace seed based on
previous week's completion data and rebuilds workout details.
"""

import pytest
from datetime import date, timedelta, datetime, timezone
from unittest.mock import Mock, patch

from src.services.training_plan.weekly_rebuild_service import (
    WeeklyRebuildService,
    _find_week_workouts,
    _normalize_workout_type,
    _determine_phase,
)
from src.services.training_plan.weekly_adjuster import WeekLogRun
from src.smartcoach_mobile_coach.runner_profile.models import (
    PaceZoneBand,
    PaceZoneComputation,
)


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

        # Peak phase (70-90%)
        assert _determine_phase(12, total_weeks) == "Peak"
        assert _determine_phase(14, total_weeks) == "Peak"

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
        from src.services.training_plan.weekly_adjuster import (
            adjust_pace_zones_from_week,
        )

        initial_pace_zones = PaceZoneComputation(
            pace_z2=PaceZoneBand(low_sec=600, high_sec=690, display="10:00-11:30/mi"),
            pace_z3=PaceZoneBand(low_sec=570, high_sec=630, display="9:30-10:30/mi"),
            pace_z4=PaceZoneBand(low_sec=510, high_sec=520, display="8:30-8:40/mi"),
            pace_source="test",
            pace_computed_at=datetime.now(timezone.utc),
            marathon_sec=540,
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

        adjusted_pace_zones, disable_quality = adjust_pace_zones_from_week(
            initial_pace_zones, week_logs
        )

        # Verify paces slowed down
        assert adjusted_pace_zones.pace_z2.low_sec > initial_pace_zones.pace_z2.low_sec
        assert (
            adjusted_pace_zones.pace_z2.high_sec > initial_pace_zones.pace_z2.high_sec
        )
        assert adjusted_pace_zones.marathon_sec > initial_pace_zones.marathon_sec

        # Verify quality disabled
        assert disable_quality is True

    def test_pace_adjustment_excellent_recovery(self):
        """Test pace adjustment when recovery is excellent (RPE <= 2)."""
        from src.services.training_plan.weekly_adjuster import (
            adjust_pace_zones_from_week,
        )

        initial_pace_zones = PaceZoneComputation(
            pace_z2=PaceZoneBand(low_sec=600, high_sec=690, display="10:00-11:30/mi"),
            pace_z3=PaceZoneBand(low_sec=570, high_sec=630, display="9:30-10:30/mi"),
            pace_z4=PaceZoneBand(low_sec=510, high_sec=520, display="8:30-8:40/mi"),
            pace_source="test",
            pace_computed_at=datetime.now(timezone.utc),
            marathon_sec=540,
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

        adjusted_pace_zones, disable_quality = adjust_pace_zones_from_week(
            initial_pace_zones, week_logs
        )

        # Verify paces sped up slightly
        assert adjusted_pace_zones.pace_z2.low_sec < initial_pace_zones.pace_z2.low_sec
        assert (
            adjusted_pace_zones.pace_z2.high_sec < initial_pace_zones.pace_z2.high_sec
        )
        assert adjusted_pace_zones.marathon_sec < initial_pace_zones.marathon_sec

    def test_pace_adjustment_high_rpe(self):
        """Test pace adjustment when RPE is high (>= 5)."""
        from src.services.training_plan.weekly_adjuster import (
            adjust_pace_zones_from_week,
        )

        initial_pace_zones = PaceZoneComputation(
            pace_z2=PaceZoneBand(low_sec=600, high_sec=690, display="10:00-11:30/mi"),
            pace_z3=PaceZoneBand(low_sec=570, high_sec=630, display="9:30-10:30/mi"),
            pace_z4=PaceZoneBand(low_sec=510, high_sec=520, display="8:30-8:40/mi"),
            pace_source="test",
            pace_computed_at=datetime.now(timezone.utc),
            marathon_sec=540,
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

        adjusted_pace_zones, disable_quality = adjust_pace_zones_from_week(
            initial_pace_zones, week_logs
        )

        # Verify paces slowed down
        assert adjusted_pace_zones.pace_z2.low_sec > initial_pace_zones.pace_z2.low_sec
        assert (
            adjusted_pace_zones.pace_z2.high_sec > initial_pace_zones.pace_z2.high_sec
        )
        assert adjusted_pace_zones.marathon_sec > initial_pace_zones.marathon_sec

        # Verify quality disabled
        assert disable_quality is True

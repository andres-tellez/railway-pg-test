"""
Tests for Pace Seed Service

Tests the pace seeding logic for both Strava-based and calibration-based paths.
"""

import pytest
from datetime import datetime, timedelta
from src.services.training_plan.pace_seed_service import (
    get_initial_pace_seed,
    median_easy_pace,
    longest_recent_long_run,
    PaceSeed,
)


class TestPaceSeedService:
    """Test pace seed generation with and without Strava data."""

    def test_pace_seed_with_strava_data(self):
        """Test pace seeding from Strava activities (sufficient data)."""
        # Create sample activities with realistic paces
        # 8:00/mi pace = 480 seconds per mile
        activities = [
            {
                "date": (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"),
                "distance": 5.0,
                "moving_time": 2400,
            }
            for i in range(6)
        ]  # 6 runs in last 6 days

        seed = get_initial_pace_seed(
            strava_activities=activities,
            plan_week1_total=20.0,
            plan_week1_long=8.0,
            goal_mp_sec_per_mi=None,
        )

        # Verify seed is created
        assert seed is not None
        assert isinstance(seed, PaceSeed)

        # Verify pace zones are reasonable
        # Easy should be ~480s/mi (8:00/mi) + range
        assert 450 <= seed.E_min <= 550
        assert 500 <= seed.E_max <= 600
        assert seed.S_min < seed.E_min  # Steady faster than easy
        assert seed.S_max < seed.E_max
        assert seed.M < seed.E_min  # Marathon faster than easy
        assert seed.T_min < seed.M  # Threshold faster than marathon
        assert seed.T_max < seed.M

        # Verify week1_long_cap is set
        assert seed.week1_long_cap > 0

    def test_pace_seed_without_strava_data(self):
        """Test calibration-based pace seeding (no Strava data)."""
        # Empty activities list
        activities = []

        seed = get_initial_pace_seed(
            strava_activities=activities,
            plan_week1_total=20.0,
            plan_week1_long=8.0,
            goal_mp_sec_per_mi=None,
        )

        # Verify seed is created (calibration fallback)
        assert seed is not None
        assert isinstance(seed, PaceSeed)

        # Verify conservative defaults are used
        # Default marathon pace = 10:00/mi = 600 sec/mi
        assert seed.M == 600.0
        assert seed.E_min > seed.M  # Easy slower than marathon
        assert seed.E_max > seed.M
        assert seed.S_min > seed.M  # Steady slower than marathon
        assert seed.S_max > seed.M
        assert seed.T_min < seed.M  # Threshold faster than marathon
        assert seed.T_max < seed.M

        # Verify week1_long_cap is conservative
        assert seed.week1_long_cap <= 16.0

    def test_pace_seed_insufficient_strava_data(self):
        """Test calibration fallback when Strava data is insufficient (<6 runs)."""
        # Only 3 runs (not enough)
        activities = [
            {
                "date": (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"),
                "distance": 4.0,
                "moving_time": 1920,
            }
            for i in range(3)
        ]

        seed = get_initial_pace_seed(
            strava_activities=activities,
            plan_week1_total=20.0,
            plan_week1_long=8.0,
            goal_mp_sec_per_mi=None,
        )

        # Should fall back to calibration
        assert seed is not None
        assert seed.M == 600.0  # Default marathon pace

    def test_pace_seed_with_goal_marathon_pace(self):
        """Test pace seeding with provided goal marathon pace."""
        # 9:00/mi goal pace = 540 seconds per mile
        goal_mp = 9 * 60  # 540 sec/mi

        seed = get_initial_pace_seed(
            strava_activities=[],
            plan_week1_total=20.0,
            plan_week1_long=8.0,
            goal_mp_sec_per_mi=goal_mp,
        )

        # Verify goal pace is used
        assert seed.M == goal_mp
        assert seed.E_min > goal_mp  # Easy slower
        assert seed.T_min < goal_mp  # Threshold faster

    def test_median_easy_pace_calculation(self):
        """Test median easy pace calculation from activities."""
        # Activities with varying paces
        activities = [
            {"distance": 5.0, "moving_time": 2400},  # 8:00/mi
            {"distance": 4.0, "moving_time": 2040},  # 8:30/mi
            {"distance": 6.0, "moving_time": 2880},  # 8:00/mi
            {"distance": 5.0, "moving_time": 2550},  # 8:30/mi
            {"distance": 4.0, "moving_time": 1920},  # 8:00/mi
        ]

        median = median_easy_pace(activities)

        # Should return median pace (8:00/mi = 480s/mi)
        assert median is not None
        assert 470 <= median <= 490  # Around 8:00/mi

    def test_median_easy_pace_with_insufficient_data(self):
        """Test median easy pace with insufficient activities."""
        # Activities too short (< 2 miles)
        activities = [
            {"distance": 1.0, "moving_time": 480},  # Too short
            {"distance": 1.5, "moving_time": 720},  # Too short
        ]

        median = median_easy_pace(activities)

        # Should return None or handle gracefully
        # (function filters < 2.0 miles)
        assert median is None or median == 0

    def test_longest_recent_long_run(self):
        """Test finding longest recent long run."""
        activities = [
            {"distance": 5.0},  # Not a long run
            {"distance": 12.0},  # Long run
            {"distance": 8.0},  # Not a long run
            {"distance": 16.0},  # Long run
            {"distance": 10.0},  # Long run
        ]

        longest = longest_recent_long_run(activities)

        # Should return longest (16.0)
        assert longest == 16.0

    def test_longest_recent_long_run_no_long_runs(self):
        """Test longest long run when no runs are 10+ miles."""
        activities = [
            {"distance": 5.0},
            {"distance": 8.0},
            {"distance": 7.0},
        ]

        longest = longest_recent_long_run(activities)

        # Should return 0.0 (no long runs)
        assert longest == 0.0

    def test_pace_seed_with_recent_activities_only(self):
        """Test that only recent activities (≤6 weeks) are used."""
        # Mix of recent and old activities
        recent_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        old_date = (datetime.now() - timedelta(weeks=8)).strftime(
            "%Y-%m-%d"
        )  # 8 weeks ago

        activities = [
            {"date": recent_date, "distance": 5.0, "moving_time": 2400},
            {"date": recent_date, "distance": 4.0, "moving_time": 1920},
            {"date": recent_date, "distance": 6.0, "moving_time": 2880},
            {"date": recent_date, "distance": 5.0, "moving_time": 2400},
            {"date": recent_date, "distance": 4.0, "moving_time": 1920},
            {"date": recent_date, "distance": 5.0, "moving_time": 2400},
            {
                "date": old_date,
                "distance": 3.0,
                "moving_time": 1200,
            },  # Should be ignored
        ]

        seed = get_initial_pace_seed(
            strava_activities=activities,
            plan_week1_total=20.0,
            plan_week1_long=8.0,
            goal_mp_sec_per_mi=None,
        )

        # Should use recent activities (8:00/mi pace)
        assert seed is not None
        assert 450 <= seed.E_min <= 550  # Around 8:00/mi

    def test_pace_seed_week1_long_cap_from_strava(self):
        """Test week1_long_cap is adjusted based on recent longest run."""
        activities = [
            {
                "date": (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"),
                "distance": 5.0,
                "moving_time": 2400,
            }
            for i in range(6)
        ]
        activities.append(
            {
                "date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                "distance": 14.0,
                "moving_time": 6720,
            }
        )  # Long run

        seed = get_initial_pace_seed(
            strava_activities=activities,
            plan_week1_total=20.0,
            plan_week1_long=10.0,
            goal_mp_sec_per_mi=None,
        )

        # week1_long_cap should consider recent longest (14.0)
        assert seed.week1_long_cap <= max(
            10.0, 14.0 + 2.0
        )  # plan_week1_long or longest + 2

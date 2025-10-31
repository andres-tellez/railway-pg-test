"""
Tests for Pass 4: Workout Details Service

Tests the workout detailing logic that uses pace seed to generate
segments, pace guidance, and cues.
"""

import pytest
from src.services.training_plan.pass4_workout_details import (
    Pass4WorkoutDetails,
    _fmt_range,
    _detail_run,
)
from src.services.training_plan.pace_seed_service import PaceSeed
from src.services.training_plan.workout_types import EASY, STEADY, ENDURANCE, LONG


class TestPass4WorkoutDetails:
    """Test workout details generation with pace seed."""

    def test_fmt_range(self):
        """Test pace range formatting."""
        # Single pace value
        assert _fmt_range(600.0, 600.0) == "10:00/mi"

        # Range
        assert _fmt_range(600.0, 630.0) == "10:00–10:30/mi"

        # Another range
        assert _fmt_range(480.0, 510.0) == "8:00–8:30/mi"

    def test_detail_easy_run(self):
        """Test easy run detail generation."""
        seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

        details = _detail_run(
            run_type=EASY,
            distance_mi=4.0,
            phase="Base",
            seed=seed,
            allow_quality=False,
        )

        # Verify segments
        assert "segments" in details
        segments = details["segments"]
        assert len(segments) == 3  # Warm-up, Easy, Cool-down

        # Verify warm-up
        assert segments[0]["name"] == "Warm-up"
        assert segments[0]["mi"] == 0.5

        # Verify easy main
        assert segments[1]["name"] == "Easy"
        assert segments[1]["mi"] == 3.0  # 4.0 - 1.0 (wu + cd)

        # Verify cool-down
        assert segments[2]["name"] == "Cool-down"
        assert segments[2]["mi"] == 0.5

        # Verify cues
        assert "cues" in details
        assert "Conversational effort" in details["cues"]

        # Verify pace labels
        assert "pace_labels" in details
        assert "E" in details["pace_labels"]

    def test_detail_steady_run(self):
        """Test steady run detail generation."""
        seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

        details = _detail_run(
            run_type=STEADY,
            distance_mi=5.0,
            phase="Build",
            seed=seed,
            allow_quality=True,
        )

        # Verify segments
        segments = details["segments"]
        assert len(segments) == 3  # Warm-up, Steady, Cool-down

        # Verify steady main
        assert segments[1]["name"] == "Steady"
        assert segments[1]["mi"] == 3.0  # 5.0 - 2.0 (wu + cd)

        # Verify optional strides in Build/Peak
        assert (
            "strides" in details["cues"].lower() or "stride" in details["cues"].lower()
        )

    def test_detail_endurance_run(self):
        """Test endurance run detail generation."""
        seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

        details = _detail_run(
            run_type=ENDURANCE,
            distance_mi=8.0,
            phase="Peak",
            seed=seed,
            allow_quality=True,
        )

        # Verify segments
        segments = details["segments"]
        assert len(segments) == 3  # Warm-up, Endurance, Cool-down

        # Verify endurance main
        assert segments[1]["name"] == "Endurance"
        assert segments[1]["mi"] == 6.0  # 8.0 - 2.0 (wu + cd)

    def test_detail_long_run_base_phase(self):
        """Test long run detail generation in Base phase."""
        seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

        details = _detail_run(
            run_type=LONG,
            distance_mi=12.0,
            phase="Base",
            seed=seed,
            allow_quality=False,
        )

        # Verify single segment (easy long run)
        segments = details["segments"]
        assert len(segments) == 1
        assert segments[0]["name"] == "Long Easy"
        assert segments[0]["mi"] == 12.0

        # Verify cues include fueling
        assert "fuel" in details["cues"].lower() or "fluids" in details["cues"].lower()

    def test_detail_long_run_peak_phase(self):
        """Test long run detail generation in Peak phase with marathon finish."""
        seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

        details = _detail_run(
            run_type=LONG,
            distance_mi=18.0,
            phase="Peak",
            seed=seed,
            allow_quality=True,
        )

        # Verify marathon finish segment
        segments = details["segments"]
        assert len(segments) == 2  # Easy part + Marathon finish

        # Verify easy part
        assert segments[0]["name"] == "Easy"
        # Finish is ~25% rounded: 18.0 * 0.25 = 4.5, rounded = 5.0 (or 4.0 depending on rounding)
        # Easy part = 18.0 - finish
        assert segments[0]["mi"] >= 13.0  # At least 13.0 (if finish = 5.0)
        assert segments[0]["mi"] <= 14.0  # At most 14.0 (if finish = 4.0)

        # Verify marathon finish
        assert segments[1]["name"] == "Marathon finish"
        assert segments[1]["mi"] >= 4.0  # ~25% of 18.0 (rounded)
        assert segments[1]["mi"] <= 5.0  # Max finish distance
        assert segments[1]["pace"] == "9:00/mi"  # M pace

    def test_add_details_to_plan(self):
        """Test adding details to complete plan."""
        service = Pass4WorkoutDetails()

        seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

        plan = {
            "weeks": [
                {
                    "week_number": 1,
                    "phase": "Base",
                    "workouts": [
                        {"day": "Mon", "type": EASY, "miles": 4.0},
                        {"day": "Wed", "type": STEADY, "miles": 5.0},
                        {"day": "Sat", "type": LONG, "miles": 10.0},
                    ],
                }
            ]
        }

        result = service.add_details_to_plan(
            plan=plan,
            seed=seed,
            mode="prefill",
            week_logs=None,
        )

        # Verify plan structure preserved
        assert "weeks" in result
        assert len(result["weeks"]) == 1

        # Verify workouts have details
        week = result["weeks"][0]
        workouts = week["workouts"]
        assert len(workouts) == 3

        # Verify each workout has segments
        for workout in workouts:
            assert "segments" in workout
            assert "cues" in workout
            assert "pace_labels" in workout

    def test_add_details_to_week(self):
        """Test adding details to a single week."""
        service = Pass4WorkoutDetails()

        seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

        week = {
            "week_number": 1,
            "phase": "Base",
            "workouts": [
                {"day": "Mon", "type": EASY, "distance_miles": 4.0},
                {"day": "Wed", "type": STEADY, "distance_miles": 5.0},
            ],
        }

        result = service.add_details_to_week(
            week=week,
            seed=seed,
            allow_quality=False,
        )

        # Verify week structure preserved
        assert "week_number" in result
        assert "workouts" in result

        # Verify workouts have details
        workouts = result["workouts"]
        assert len(workouts) == 2

        for workout in workouts:
            assert "segments" in workout
            assert "cues" in workout

    def test_quality_disabled_in_base_phase(self):
        """Test that quality work is disabled in Base phase."""
        seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

        details = _detail_run(
            run_type=EASY,
            distance_mi=4.0,
            phase="Base",
            seed=seed,
            allow_quality=False,
        )

        # Verify no quality work cues
        assert "strides" not in details["cues"].lower()

    def test_quality_enabled_in_peak_phase(self):
        """Test that quality work is enabled in Peak phase."""
        seed = PaceSeed(
            E_min=600.0,
            E_max=690.0,
            S_min=570.0,
            S_max=630.0,
            M=540.0,
            T_min=510.0,
            T_max=520.0,
            week1_long_cap=8.0,
        )

        details = _detail_run(
            run_type=EASY,
            distance_mi=4.0,
            phase="Peak",
            seed=seed,
            allow_quality=True,
        )

        # Verify quality work cues
        assert (
            "strides" in details["cues"].lower() or "stride" in details["cues"].lower()
        )

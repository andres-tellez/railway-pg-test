"""
Pytest configuration and fixtures for Coach tests.
"""

import pytest
from pathlib import Path


@pytest.fixture
def test_schemas_dir():
    """Fixture providing path to test schemas directory."""
    return Path(__file__).parent.parent.parent / "schemas"


@pytest.fixture
def sample_runner_state():
    """Fixture providing a sample valid RunnerState."""
    return {
        "version": "1.0.0",
        "runner_state": {
            "phase": "Build",
            "week_of_block": 8,
            "plan_type": "Marathon_4hr",
            "race": {
                "date": "2025-04-15",
                "distance": "Marathon",
                "target_time": "4:00:00",
                "goal_type": "Target Time",
            },
            "zones": {
                "pace": {
                    "easy": "9:45-10:15/mile",
                    "marathon": "9:05-9:15/mile",
                    "threshold": "8:25-8:40/mile",
                },
                "hr": {"z1": "105-120 bpm", "z2": "121-138 bpm", "z3": "139-152 bpm"},
            },
            "weekly_metrics": {
                "week_start": "2025-01-13",
                "mileage": 42.3,
                "volume_score": 86,
                "intensity_score": 78,
                "consistency_score": 92,
                "load_change_pct": 9,
                "fatigue_flags": ["mild_hr_drift"],
            },
            "patterns": {
                "long_runs_too_fast_count": 2,
                "missed_key_workouts_last_4_weeks": 1,
                "trend": "improving",
            },
            "safety": {
                "hr_data_reliable": True,
                "pace_data_reliable": True,
                "reported_injury": False,
            },
        },
    }


@pytest.fixture
def sample_question_context():
    """Fixture providing a sample valid QuestionContext."""
    return {
        "version": "1.0.0",
        "question_context": {
            "intent": "workout_review",
            "workout_review": {
                "workout_type": "long_run",
                "activity": {
                    "date": "2025-01-12",
                    "distance_miles": 18.0,
                    "avg_pace": "8:36/mile",
                    "avg_hr": 146,
                    "zone_distribution": {"z1": "5%", "z2": "53%", "z3": "42%"},
                    "plan_target": {
                        "distance_miles": 18.0,
                        "pace_range": "9:45-10:15/mile",
                        "hr_zone": "Z2",
                    },
                    "deviation": {"pace_faster_pct": 10, "hr_above_zone": True},
                },
            },
        },
    }

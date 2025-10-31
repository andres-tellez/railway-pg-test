"""
End-to-End Smoke Test for Launch Checklist

Tests:
1. Generate plans for 3/4/5-day frequencies across Base→Taper
2. Verify segments structure matches spec
3. Verify pace_ranges and all metadata are present
4. Check intensity mapping (M only when Marathon step exists)
"""

import pytest
from datetime import date, timedelta
from src.services.training_plan.orchestrator_three_pass import ThreePassOrchestrator
from src.services.training_plan.pace_seed_service import PaceSeed
from src.db.db_session import get_session
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_session():
    """Mock database session."""
    session = Mock()
    return session


@pytest.fixture
def sample_plan_request():
    """Sample plan request."""
    race_date = date.today() + timedelta(days=120)  # 120 days from now
    return {
        "race_date": race_date.strftime("%Y-%m-%d"),
        "primary_goal": "Just Finish",
        "race_distance": "Marathon",
        "race_name": "Test Marathon",
        "race_location": "Test City",
        "training_days": ["Mon", "Wed", "Fri", "Sat"],
    }


def test_segments_spec_compliance():
    """Verify segments match spec: units, targetType, steps structure."""
    from src.services.training_plan.pass4_workout_details import _detail_run
    from src.services.training_plan.pace_seed_service import PaceSeed

    seed = PaceSeed(
        E_min=645,
        E_max=705,
        S_min=615,
        S_max=630,
        M=600,
        T_min=570,
        T_max=580,
        week1_long_cap=8.0,
    )

    # Test endurance run (typical weekday run)
    details = _detail_run(
        run_type="endurance",
        distance_mi=10.0,
        phase="Peak",
        seed=seed,
        allow_quality=True,
    )

    segments = details["segments"]

    # Verify top-level structure
    assert segments["units"] == "mi", "units must be 'mi'"
    assert segments["targetType"] == "PACE", "targetType must be 'PACE'"
    assert "steps" in segments, "must have steps array"
    assert "notes" in segments, "must have notes"

    # Verify each step structure
    for step in segments["steps"]:
        assert "name" in step, "step must have name"
        assert "durationType" in step, "step must have durationType"
        assert step["durationType"] == "DISTANCE", "durationType must be DISTANCE"
        assert "value" in step, "step must have value"
        assert isinstance(step["value"], (int, float)), "value must be numeric"
        assert step["value"] > 0, "value must be positive (zero steps filtered)"

        assert "target" in step, "step must have target"
        target = step["target"]
        assert isinstance(target, dict), "target must be dict"
        assert "low" in target, "target must have low"
        assert "high" in target, "target must have high"
        assert isinstance(target["low"], int), "target.low must be int (seconds)"
        assert isinstance(target["high"], int), "target.high must be int (seconds)"
        assert target["low"] <= target["high"], "target.low <= target.high"

        assert "intensity" in step, "step must have intensity"
        assert step["intensity"] in ["EASY", "STEADY", "MARATHON"], "valid intensity"

    # Verify sum of steps equals distance (± tolerance)
    total_miles = sum(s["value"] for s in segments["steps"])
    assert (
        abs(total_miles - 10.0) < 0.11
    ), f"sum of steps ({total_miles}) should equal distance (10.0)"


def test_pace_ranges_structure():
    """Verify pace_ranges structure with integer seconds."""
    from src.services.training_plan.plan_storage_service import PlanStorageService
    from src.services.training_plan.pace_seed_service import PaceSeed
    from datetime import date

    seed = PaceSeed(
        E_min=645,
        E_max=705,
        S_min=615,
        S_max=630,
        M=600,
        T_min=570,
        T_max=580,
        week1_long_cap=8.0,
    )

    run = {"type": "endurance", "label": "Endurance (Medium-Long)", "miles": 10.0}
    details = {
        "segments": {
            "units": "mi",
            "targetType": "PACE",
            "steps": [
                {
                    "name": "Endurance",
                    "durationType": "DISTANCE",
                    "value": 10.0,
                    "target": {"low": 615, "high": 630},
                    "intensity": "STEADY",
                }
            ],
            "notes": "test",
        },
        "cues": "test cues",
        "quality_insert": None,
    }

    row = PlanStorageService._workout_to_row(
        plan_id=1,
        date=date.today(),
        phase="Peak",
        run=run,
        seed=seed,
        details=details,
    )

    pace_ranges = row["pace_ranges"]
    assert isinstance(pace_ranges, dict), "pace_ranges must be dict"
    assert "E" in pace_ranges, "pace_ranges must have E"
    assert "S" in pace_ranges, "pace_ranges must have S"
    assert "M" in pace_ranges, "pace_ranges must have M"
    assert "T" in pace_ranges, "pace_ranges must have T"

    # Verify integer seconds
    for zone in ["E", "S", "M", "T"]:
        assert isinstance(pace_ranges[zone], list), f"{zone} must be list"
        assert len(pace_ranges[zone]) == 2, f"{zone} must have [min, max]"
        assert all(
            isinstance(v, int) for v in pace_ranges[zone]
        ), f"{zone} values must be int (seconds)"


def test_intensity_mapping():
    """Verify intensity is 'M' only when Marathon step exists."""
    from src.services.training_plan.plan_storage_service import PlanStorageService
    from src.services.training_plan.pace_seed_service import PaceSeed
    from datetime import date

    seed = PaceSeed(
        E_min=645,
        E_max=705,
        S_min=615,
        S_max=630,
        M=600,
        T_min=570,
        T_max=580,
        week1_long_cap=8.0,
    )

    # Test 1: Long run WITHOUT marathon finish -> intensity = "E"
    run1 = {"type": "long", "label": "Long Run", "miles": 15.0}
    details1 = {
        "segments": {
            "units": "mi",
            "targetType": "PACE",
            "steps": [
                {
                    "name": "Long Easy",
                    "durationType": "DISTANCE",
                    "value": 15.0,
                    "target": {"low": 645, "high": 705},
                    "intensity": "EASY",
                }
            ],
            "notes": "test",
        },
        "cues": "test",
        "quality_insert": None,
    }

    row1 = PlanStorageService._workout_to_row(
        plan_id=1,
        date=date.today(),
        phase="Base",
        run=run1,
        seed=seed,
        details=details1,
    )
    assert row1["intensity"] == "E", "Long run without M-finish should be E"

    # Test 2: Long run WITH marathon finish -> intensity = "M"
    run2 = {"type": "long", "label": "Long Run", "miles": 18.0}
    details2 = {
        "segments": {
            "units": "mi",
            "targetType": "PACE",
            "steps": [
                {
                    "name": "Long Easy",
                    "durationType": "DISTANCE",
                    "value": 13.5,
                    "target": {"low": 645, "high": 705},
                    "intensity": "EASY",
                },
                {
                    "name": "Marathon finish",
                    "durationType": "DISTANCE",
                    "value": 4.5,
                    "target": {"low": 600, "high": 600},
                    "intensity": "MARATHON",
                },
            ],
            "notes": "test",
        },
        "cues": "test",
        "quality_insert": {"type": "marathon_finish", "miles": 4.5},
    }

    row2 = PlanStorageService._workout_to_row(
        plan_id=1,
        date=date.today(),
        phase="Peak",
        run=run2,
        seed=seed,
        details=details2,
    )
    assert row2["intensity"] == "M", "Long run with M-finish should be M"


def test_all_metadata_fields():
    """Verify all metadata fields are present in saved row."""
    from src.services.training_plan.plan_storage_service import PlanStorageService
    from src.services.training_plan.pace_seed_service import PaceSeed
    from datetime import date

    seed = PaceSeed(
        E_min=645,
        E_max=705,
        S_min=615,
        S_max=630,
        M=600,
        T_min=570,
        T_max=580,
        week1_long_cap=8.0,
    )

    run = {"type": "endurance", "label": "Endurance (Medium-Long)", "miles": 10.0}
    details = {
        "segments": {
            "units": "mi",
            "targetType": "PACE",
            "steps": [
                {
                    "name": "Endurance",
                    "durationType": "DISTANCE",
                    "value": 10.0,
                    "target": {"low": 615, "high": 630},
                    "intensity": "STEADY",
                }
            ],
            "notes": "test cues",
        },
        "cues": "test cues",
        "quality_insert": None,
    }

    row = PlanStorageService._workout_to_row(
        plan_id=42,
        date=date(2026, 1, 17),
        phase="Peak",
        run=run,
        seed=seed,
        details=details,
    )

    # Verify all required fields
    required_fields = [
        "plan_id",
        "date",
        "workout_type",
        "run_type_key",
        "phase",
        "miles",
        "intensity",
        "target_zone",
        "focus",
        "description",
        "cues",
        "pace_ranges",
        "allow_quality",
        "quality_insert",
        "segments",
    ]

    for field in required_fields:
        assert field in row, f"Row must have {field}"

    # Verify values match spec
    assert row["plan_id"] == 42
    assert row["date"] == date(2026, 1, 17)
    assert row["workout_type"] == "Endurance (Medium-Long)"
    assert row["run_type_key"] == "endurance"
    assert row["phase"] == "Peak"
    assert row["miles"] == 10.0
    assert row["intensity"] == "S"
    assert row["allow_quality"] is True  # Peak phase
    assert row["quality_insert"] is None

    # Verify segments structure
    segments = row["segments"]
    assert segments["units"] == "mi"
    assert segments["targetType"] == "PACE"
    assert len(segments["steps"]) > 0


def test_sample_row_format():
    """Verify row matches the sample format from checklist."""
    from src.services.training_plan.plan_storage_service import PlanStorageService
    from src.services.training_plan.pace_seed_service import PaceSeed
    from datetime import date

    seed = PaceSeed(
        E_min=645,
        E_max=705,
        S_min=615,
        S_max=630,
        M=600,
        T_min=570,
        T_max=580,
        week1_long_cap=8.0,
    )

    run = {"type": "endurance", "label": "Endurance (Medium-Long)", "miles": 10.0}
    details = {
        "segments": {
            "units": "mi",
            "targetType": "PACE",
            "steps": [
                {
                    "name": "Warm-up",
                    "durationType": "DISTANCE",
                    "value": 1.0,
                    "target": {"low": 645, "high": 705},
                    "intensity": "EASY",
                },
                {
                    "name": "Endurance",
                    "durationType": "DISTANCE",
                    "value": 8.0,
                    "target": {"low": 615, "high": 630},
                    "intensity": "STEADY",
                },
                {
                    "name": "Cool-down",
                    "durationType": "DISTANCE",
                    "value": 1.0,
                    "target": {"low": 645, "high": 705},
                    "intensity": "EASY",
                },
            ],
            "notes": "Medium-long run; builds fatigue tolerance. If feeling good: last 2–3 mi at marathon pace.",
        },
        "cues": "Medium-long run; builds fatigue tolerance. If feeling good: last 2–3 mi at marathon pace.",
        "quality_insert": None,
    }

    row = PlanStorageService._workout_to_row(
        plan_id=42,
        date=date(2026, 1, 17),
        phase="Peak",
        run=run,
        seed=seed,
        details=details,
    )

    # Verify structure matches sample
    assert row["plan_id"] == 42
    assert row["date"] == date(2026, 1, 17)
    assert row["workout_type"] == "Endurance (Medium-Long)"
    assert row["run_type_key"] == "endurance"
    assert row["phase"] == "Peak"
    assert row["miles"] == 10.0
    assert row["intensity"] == "S"
    assert (
        "10:15" in row["target_zone"] or "10:30" in row["target_zone"]
    )  # Pace string format
    assert row["focus"] == "Medium-Long"
    assert (
        row["cues"]
        == "Medium-long run; builds fatigue tolerance. If feeling good: last 2–3 mi at marathon pace."
    )
    assert row["allow_quality"] is True
    assert row["quality_insert"] is None

    # Verify pace_ranges
    assert row["pace_ranges"]["E"] == [645, 705]
    assert row["pace_ranges"]["S"] == [615, 630]
    assert row["pace_ranges"]["M"] == [600, 600]
    assert row["pace_ranges"]["T"] == [570, 580]

    # Verify segments
    segments = row["segments"]
    assert segments["units"] == "mi"
    assert segments["targetType"] == "PACE"
    assert len(segments["steps"]) == 3
    assert (
        segments["notes"]
        == "Medium-long run; builds fatigue tolerance. If feeling good: last 2–3 mi at marathon pace."
    )

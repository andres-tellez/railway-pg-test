"""Tests for plan_workouts.run_type_key placement-role validation."""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach.runner_profile.plan_placement import (
    infer_placement_role_from_label,
    normalize_persisted_run_type_key,
    placement_focus_tag,
    placement_wu_cd_mi,
    recognize_run_type_key_from_workout_label,
    validate_persisted_run_type_key,
)


@pytest.mark.parametrize("raw", ["easy", "steady", "endurance", "long"])
def test_validate_persisted_run_type_key_accepts_roles(raw):
    assert validate_persisted_run_type_key(raw) == raw


def test_validate_persisted_run_type_key_normalizes_long_run():
    assert validate_persisted_run_type_key("long_run") == "long"
    assert normalize_persisted_run_type_key("long_run") == "long"


@pytest.mark.parametrize("raw", ["tempo", "intervals", "threshold", "Race"])
def test_validate_persisted_run_type_key_rejects_non_roles(raw):
    with pytest.raises(ValueError, match="Invalid run_type_key"):
        validate_persisted_run_type_key(raw)


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Easy", "easy"),
        ("Easy / Recovery", "easy"),
        ("Steady", "steady"),
        ("Aerobic / Steady", "steady"),
        ("Endurance (Medium-Long)", "endurance"),
        ("Long Run", "long"),
        ("Tempo", "endurance"),
        ("Threshold", "endurance"),
        ("Intervals", "endurance"),
        ("Unknown", None),
        ("", None),
    ],
)
def test_recognize_run_type_key_from_workout_label(label, expected):
    assert recognize_run_type_key_from_workout_label(label) == expected


def test_infer_placement_role_from_label_defaults_unknown_to_easy():
    assert infer_placement_role_from_label("Unknown") == "easy"


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("easy", "Recovery"),
        ("steady", "Aerobic"),
        ("endurance", "Medium-Long"),
        ("long", "Long – fueling practice"),
        ("long_run", "Long – fueling practice"),
    ],
)
def test_placement_focus_tag(role, expected):
    assert placement_focus_tag(role) == expected


def test_placement_wu_cd_mi_for_roles():
    assert placement_wu_cd_mi("easy") == {"wu": 0.5, "cd": 0.5}
    assert placement_wu_cd_mi("steady") == {"wu": 1.0, "cd": 1.0}
    assert placement_wu_cd_mi("long_run") == {"wu": 0.0, "cd": 0.0}


def test_placement_wu_cd_mi_unknown_defaults():
    assert placement_wu_cd_mi("tempo") == {"wu": 1.0, "cd": 1.0}

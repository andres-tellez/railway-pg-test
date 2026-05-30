"""Tests for plan_workouts.run_type_key taxonomy-key validation."""

from __future__ import annotations

import pytest

from src.smartcoach_mobile_coach.runner_profile.plan_placement import (
    infer_placement_role_from_label,
    infer_run_type_key_from_workout_label,
    normalize_persisted_run_type_key,
    placement_focus_tag,
    placement_wu_cd_mi,
    recognize_run_type_key_from_workout_label,
    validate_persisted_run_type_key,
)


@pytest.mark.parametrize(
    "raw",
    ["easy", "tempo", "threshold", "long_run", "intervals", "hills", "race"],
)
def test_validate_persisted_run_type_key_accepts_taxonomy_keys(raw):
    assert validate_persisted_run_type_key(raw) == raw


def test_validate_persisted_run_type_key_normalizes_long_alias():
    assert validate_persisted_run_type_key("long") == "long_run"
    assert normalize_persisted_run_type_key("long") == "long_run"


def test_validate_persisted_run_type_key_normalizes_legacy_steady():
    assert validate_persisted_run_type_key("steady") == "easy"


def test_validate_persisted_run_type_key_normalizes_legacy_endurance_from_label():
    assert validate_persisted_run_type_key("endurance", workout_type="Tempo") == "tempo"
    assert validate_persisted_run_type_key("endurance", workout_type="Long Run") == (
        "long_run"
    )


@pytest.mark.parametrize("raw", ["unknown", "vo2", "steady_state"])
def test_validate_persisted_run_type_key_rejects_unknown(raw):
    with pytest.raises(ValueError, match="Invalid run_type_key"):
        validate_persisted_run_type_key(raw)


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Easy", "easy"),
        ("Easy / Recovery", "easy"),
        ("Long Run", "long_run"),
        ("Tempo", "tempo"),
        ("Threshold", "threshold"),
        ("Intervals", "intervals"),
        ("Race Day", "race"),
        ("Unknown", None),
        ("", None),
    ],
)
def test_recognize_run_type_key_from_workout_label(label, expected):
    assert recognize_run_type_key_from_workout_label(label) == expected


def test_infer_run_type_key_from_label_defaults_unknown_to_easy():
    assert infer_run_type_key_from_workout_label("Unknown") == "easy"
    assert infer_placement_role_from_label("Unknown") == "easy"


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("easy", "Recovery"),
        ("tempo", "Tempo"),
        ("threshold", "Threshold"),
        ("long_run", "Long – fueling practice"),
        ("race", "Race Day"),
    ],
)
def test_placement_focus_tag(role, expected):
    assert placement_focus_tag(role) == expected


def test_placement_wu_cd_mi_for_taxonomy_keys():
    assert placement_wu_cd_mi("easy") == {"wu": 0.5, "cd": 0.5}
    assert placement_wu_cd_mi("tempo") == {"wu": 1.0, "cd": 1.0}
    assert placement_wu_cd_mi("long_run") == {"wu": 0.0, "cd": 0.0}
    assert placement_wu_cd_mi("race") == {"wu": 0.0, "cd": 0.0}

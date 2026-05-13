"""Tests for silent validation repair allowlist."""

from __future__ import annotations

from src.services.training_plan.v2.race_configs.marathon_config import MarathonConfig
from src.services.training_plan.v2.plan_validation_silent_repair import (
    attempt_silent_repair_then_revalidate,
    violations_are_silent_repairable,
)


def test_violations_allowlist_positive_and_negative():
    assert violations_are_silent_repairable(
        [{"rule": "missing_taper", "severity": "error"}]
    )
    assert violations_are_silent_repairable(
        [
            {"rule": "missing_taper"},
            {"rule": "incorrect_taper_weeks"},
            {"rule": "unsafe_long_run_progression"},
        ]
    )
    assert not violations_are_silent_repairable(
        [
            {"rule": "missing_taper"},
            {"rule": "10_percent_rule_violation"},
        ]
    )
    assert not violations_are_silent_repairable([])


def test_silent_repair_caps_unsafe_long_run_progression(monkeypatch):
    plan = {
        "weeks": [
            {
                "week_number": 1,
                "weekly_mileage": 30.0,
                "workouts": [
                    {"day": "Sat", "workout_type": "Long Run", "distance_miles": 12.0},
                    {"day": "Tue", "workout_type": "Easy Run", "distance_miles": 6.0},
                ],
            },
            {
                "week_number": 2,
                "weekly_mileage": 36.0,
                "workouts": [
                    {"day": "Sat", "workout_type": "Long Run", "distance_miles": 16.0},
                    {"day": "Tue", "workout_type": "Easy Run", "distance_miles": 6.0},
                ],
            },
        ]
    }
    violations = [
        {
            "rule": "unsafe_long_run_progression",
            "severity": "error",
            "location": "week 2",
            "suggestion": "Reduce long run distance in week 2 to at most 14.0",
        }
    ]

    observed = {}

    def _fake_validate(_self, candidate_plan, unit_system):
        observed["plan"] = candidate_plan
        return {
            "valid": True,
            "validated_plan": candidate_plan,
            "violations": [],
        }

    monkeypatch.setattr(
        "src.services.training_plan.v2.plan_validation_silent_repair."
        "PlanValidationServiceV2.validate_plan",
        _fake_validate,
    )
    out = attempt_silent_repair_then_revalidate(
        plan,
        violations,
        config=MarathonConfig(),
        unit_system="imperial",
    )

    assert isinstance(out, dict)
    weeks = (observed.get("plan") or {}).get("weeks") or []
    week2 = next((w for w in weeks if w.get("week_number") == 2), None)
    assert isinstance(week2, dict)
    workouts = week2.get("workouts") or []
    long_run = next(
        (
            w
            for w in workouts
            if str(w.get("workout_type") or "").strip().lower() == "long run"
        ),
        None,
    )
    assert isinstance(long_run, dict)
    assert float(long_run.get("distance_miles") or 0) <= 14.0

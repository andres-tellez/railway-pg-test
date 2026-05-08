"""Tests for silent validation repair allowlist."""

from __future__ import annotations

from src.services.training_plan.v2.plan_validation_silent_repair import (
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
        ]
    )
    assert not violations_are_silent_repairable(
        [
            {"rule": "missing_taper"},
            {"rule": "10_percent_rule_violation"},
        ]
    )
    assert not violations_are_silent_repairable([])

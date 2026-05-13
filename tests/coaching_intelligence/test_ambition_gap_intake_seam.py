"""
Integration-style seam tests for ambition-gap evaluator.

Uses realistic *shapes* of intake + fitness data a caller might assemble (e.g. after
reading plan_request and MV metrics) without importing plan generation or the planner.

No HTTP, no blueprints, no planner modules — architectural isolation only.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pytest

from src.coaching_intelligence.ambition_gap import evaluate_ambition_gap


def _evaluate_from_plan_and_fitness_snapshot(
    *,
    plan_request: Dict[str, Any],
    weekly_mileage: float,
    longest_run_miles: Optional[float] = None,
) -> Dict[str, Any]:
    """Test-only seam: map snapshot fields to evaluator inputs (not production code)."""
    return evaluate_ambition_gap(
        weekly_mileage=weekly_mileage,
        primary_goal=plan_request.get("primary_goal"),
        target_time=plan_request.get("target_time"),
        longest_run_miles=longest_run_miles,
    )


def test_seam_typical_just_finish_marathon_intake_with_moderate_baseline() -> None:
    plan_request = {
        "race_distance": "Marathon",
        "primary_goal": "Just Finish",
        "target_time": None,
        "training_days": ["Mon", "Wed", "Fri", "Sat"],
    }
    # weekly_mileage / longest_run as MV might supply for plan gen
    out = _evaluate_from_plan_and_fitness_snapshot(
        plan_request=plan_request,
        weekly_mileage=27.5,
        longest_run_miles=12.0,
    )
    assert out["stance"] == "COHERENT"
    assert out["baseline_band"] == "MODERATE"
    assert out["goal_demand"] == "FINISH"
    assert "STANCE_COHERENT_FINISH_INTENT" in out["attributions"]


def test_seam_target_time_with_thin_baseline_high_tension() -> None:
    plan_request = {
        "primary_goal": "Target Time",
        "target_time": "2:55:00",
    }
    out = _evaluate_from_plan_and_fitness_snapshot(
        plan_request=plan_request,
        weekly_mileage=12.0,
        longest_run_miles=8.0,
    )
    assert out["stance"] == "HIGH_TENSION"
    assert out["goal_demand"] == "TIME_TARGET"
    assert "STANCE_HIGH_TENSION_TIME_VS_THIN_BASELINE" in out["attributions"]


def test_seam_target_time_established_baseline_coherent_via_attribution() -> None:
    plan_request = {
        "primary_goal": "Target Time",
        "target_time": "3:30:00",
    }
    out = _evaluate_from_plan_and_fitness_snapshot(
        plan_request=plan_request,
        weekly_mileage=48.0,
        longest_run_miles=18.0,
    )
    assert out["stance"] == "COHERENT"
    assert out["baseline_band"] == "ESTABLISHED"
    assert "STANCE_COHERENT_TIME_VS_ESTABLISHED_BASELINE" in out["attributions"]


def test_seam_partial_intake_missing_goal_key() -> None:
    plan_request: Dict[str, Any] = {"training_days": ["Tue", "Thu", "Sat"]}
    out = _evaluate_from_plan_and_fitness_snapshot(
        plan_request=plan_request,
        weekly_mileage=20.0,
    )
    assert out["stance"] == "INSUFFICIENT_GOAL_CONTEXT"
    assert out["goal_demand"] == "UNSPECIFIED"


def test_seam_longest_run_zero_adds_attribution_only_does_not_change_stance_path() -> (
    None
):
    """v1: LR<=0 flag is observational; stance still driven by mpw + goal."""
    plan_request = {"primary_goal": "Just Finish"}
    out = _evaluate_from_plan_and_fitness_snapshot(
        plan_request=plan_request,
        weekly_mileage=22.0,
        longest_run_miles=0.0,
    )
    assert out["stance"] == "COHERENT"
    assert "RULE_LONGEST_RUN_MISSING_OR_ZERO" in out["attributions"]


@pytest.mark.parametrize(
    "primary_goal",
    ["Just Finish", "just finish", "I just want to finish"],
)
def test_seam_goal_string_variants_finish_intent(primary_goal: str) -> None:
    out = _evaluate_from_plan_and_fitness_snapshot(
        plan_request={"primary_goal": primary_goal},
        weekly_mileage=25.0,
    )
    assert out["goal_demand"] == "FINISH"
    assert out["stance"] == "COHERENT"

"""Tests for observational ambition-gap evaluator (Phase 3 prototype)."""

from typing import Optional

import pytest

from src.coaching_intelligence.ambition_gap import evaluate_ambition_gap


@pytest.mark.parametrize(
    "mpw,goal,tt,expected_stance,expected_baseline",
    [
        (25.0, "Just Finish", None, "COHERENT", "MODERATE"),
        (10.0, "Just Finish", None, "COHERENT", "THIN"),
        (40.0, "Target Time", "3:15:00", "COHERENT", "ESTABLISHED"),
        (20.0, "Target Time", "3:15:00", "MANAGEABLE_TENSION", "MODERATE"),
        (12.0, "Target Time", "3:15:00", "HIGH_TENSION", "THIN"),
    ],
)
def test_ambition_gap_stances(
    mpw: float,
    goal: str,
    tt: Optional[str],
    expected_stance: str,
    expected_baseline: str,
) -> None:
    out = evaluate_ambition_gap(
        weekly_mileage=mpw,
        primary_goal=goal,
        target_time=tt,
    )
    assert out["stance"] == expected_stance
    assert out["baseline_band"] == expected_baseline
    assert out["thin_baseline_data"] is False
    assert isinstance(out["attributions"], list)
    assert len(out["attributions"]) >= 1
    assert (
        out["attributions"]
        == evaluate_ambition_gap(
            weekly_mileage=mpw,
            primary_goal=goal,
            target_time=tt,
        )["attributions"]
    )


def test_unspecified_goal() -> None:
    out = evaluate_ambition_gap(
        weekly_mileage=25.0, primary_goal=None, target_time=None
    )
    assert out["stance"] == "INSUFFICIENT_GOAL_CONTEXT"
    assert out["goal_demand"] == "UNSPECIFIED"
    assert "RULE_GOAL_DEMAND_UNSPECIFIED" in out["attributions"]


def test_thin_baseline_flag() -> None:
    out = evaluate_ambition_gap(
        weekly_mileage=0.0,
        primary_goal="Just Finish",
        target_time=None,
    )
    assert out["thin_baseline_data"] is True
    assert "RULE_BASELINE_MILEAGE_MISSING_OR_ZERO" in out["attributions"]


def test_target_time_goal_without_time_string() -> None:
    out = evaluate_ambition_gap(
        weekly_mileage=30.0,
        primary_goal="Target Time",
        target_time=None,
    )
    assert out["goal_demand"] == "TIME_TARGET"
    assert "RULE_GOAL_TIME_STRING_ABSENT" in out["attributions"]

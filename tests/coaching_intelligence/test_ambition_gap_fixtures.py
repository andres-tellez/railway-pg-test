"""Lock ``synthetic_ambition_attributions`` to ``evaluate_ambition_gap`` (no drift)."""

from __future__ import annotations

from src.coaching_intelligence.ambition_gap import evaluate_ambition_gap

from tests.coaching_intelligence.ambition_gap_fixtures import (
    synthetic_ambition_attributions,
)


def test_synthetic_matches_evaluator_for_time_target_bands():
    for mpw, goal, tt in (
        (10.0, "Target Time", "3:30:00"),
        (20.0, "Target Time", "3:30:00"),
        (35.0, "Target Time", "3:30:00"),
    ):
        ev = evaluate_ambition_gap(
            weekly_mileage=mpw,
            primary_goal=goal,
            target_time=tt,
            longest_run_miles=8.0,
        )
        band = str(ev["baseline_band"])
        syn = synthetic_ambition_attributions(
            baseline_band=band,
            goal_demand="TIME_TARGET",
            thin_baseline_data=mpw <= 0,
            longest_run_miles=8.0,
            target_time_present=bool(tt.strip()),
        )
        assert syn == ev["attributions"]


def test_synthetic_matches_evaluator_just_finish():
    mpw = 32.0
    ev = evaluate_ambition_gap(
        weekly_mileage=mpw,
        primary_goal="Just Finish",
        target_time="",
        longest_run_miles=10.0,
    )
    syn = synthetic_ambition_attributions(
        baseline_band=str(ev["baseline_band"]),
        goal_demand="FINISH",
        thin_baseline_data=mpw <= 0,
        longest_run_miles=10.0,
    )
    assert syn == ev["attributions"]

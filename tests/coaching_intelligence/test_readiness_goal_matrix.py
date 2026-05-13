"""Wave 4 — demand score monotonicity and 3:30 cliff regression."""

from __future__ import annotations

from src.coaching_intelligence.plan_generation_readiness import (
    evaluate_plan_generation_readiness,
)
from src.coaching_intelligence.policy.demand import compute_demand_score
from src.coaching_intelligence.policy.policy_table import marathon_distance_mi
from tests.coaching_intelligence.ambition_gap_fixtures import (
    synthetic_ambition_attributions,
)


def _assessment_base():
    return {
        "schema_version": "pre_generation_runner_assessment.v1",
        "activity_summary": {
            "avg_miles_per_week_approx": 40.0,
            "longest_run_miles": 16.0,
            "activities_found": 16,
            "lookback_weeks": 6,
            "completed_calendar_weeks_count": 4,
            "pace_reliability": "high",
            "typical_easy_pace_sec_per_mi": 480.0,
            "best_sustained_endurance_pace_sec_per_mi": 430.0,
            "long_runs_ge_10_mi_count": 4,
            "weeks_with_long_run_10plus": 3,
        },
        "ambition_gap": {
            "stance": "COHERENT",
            "baseline_band": "ESTABLISHED",
            "goal_demand": "TIME_TARGET",
            "thin_baseline_data": False,
            "attributions": synthetic_ambition_attributions(
                baseline_band="ESTABLISHED",
                goal_demand="TIME_TARGET",
                thin_baseline_data=False,
                longest_run_miles=16.0,
            ),
        },
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
    }


def _plan_with_time(target_time: str):
    return {
        "race_distance": "Marathon",
        "race_date": "2099-12-01",
        "primary_goal": "Target Time",
        "target_time": target_time,
        "training_days": ["Mon", "Tue", "Thu", "Sat", "Sun"],
    }


def test_compute_demand_score_decreases_with_slower_marathon_times():
    times = [
        "2:50:00",
        "3:00:00",
        "3:15:00",
        "3:30:00",
        "3:40:00",
        "4:00:00",
        "4:30:00",
        "5:00:00",
        "5:30:00",
    ]
    prev = None
    from src.coaching_intelligence.plan_generation_readiness import (
        _parse_clock_seconds,
    )

    for clock in times:
        secs = _parse_clock_seconds(clock)
        assert secs is not None
        pace = float(secs) / marathon_distance_mi
        d = compute_demand_score(pace, "Marathon")
        if prev is not None:
            assert d <= prev + 1e-9, (clock, d, prev)
        prev = d


def test_no_cliff_marathon_33000_vs_33001_readiness():
    a = _assessment_base()
    out_a = evaluate_plan_generation_readiness(
        plan_request=_plan_with_time("3:30:00"),
        assessment_api=a,
    )
    out_b = evaluate_plan_generation_readiness(
        plan_request=_plan_with_time("3:30:01"),
        assessment_api=a,
    )
    assert out_a["decision"] == out_b["decision"]
    assert out_a["readiness_level"] == out_b["readiness_level"]
    assert set(out_a["reason_codes"]) == set(out_b["reason_codes"])

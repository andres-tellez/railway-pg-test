"""Wave 4 — demand score monotonicity, 3:30 cliff regression, generalized matrix."""

from __future__ import annotations

import itertools
from datetime import date, timedelta

import pytest

from src.coaching_intelligence.plan_generation_readiness import (
    DECISION_ALLOW,
    DECISION_BLOCK,
    DECISION_DEFER,
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
    from src.coaching_intelligence.time_clock import parse_clock_seconds

    for clock in times:
        secs = parse_clock_seconds(clock)
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


TIMES_ORDERED = [
    "Finish",
    "5:30:00",
    "5:00:00",
    "4:30:00",
    "4:00:00",
    "3:40:00",
    "3:30:00",
    "3:15:00",
    "3:00:00",
    "2:50:00",
]
DAY_COUNTS = [3, 4, 5, 6]
MPWS = [10, 20, 30, 45]
WEEKS_TO_RACE = [6, 12, 18, 24]


def _decision_rank(decision: str) -> int:
    if decision == DECISION_ALLOW:
        return 0
    if decision == DECISION_DEFER:
        return 1
    if decision == DECISION_BLOCK:
        return 2
    raise AssertionError(f"unknown decision {decision!r}")


def _band_from_mpw(mpw: float) -> str:
    if mpw <= 15:
        return "THIN"
    if mpw <= 30:
        return "MODERATE"
    return "ESTABLISHED"


def _matrix_plan(time_spec: str, n_days: int, weeks: int) -> dict:
    pool = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    days = pool[:n_days]
    race = (date.today() + timedelta(weeks=weeks)).isoformat()
    if time_spec == "Finish":
        return {
            "race_distance": "Marathon",
            "race_date": race,
            "primary_goal": "Finish Strong",
            "target_time": "",
            "training_days": days,
        }
    return {
        "race_distance": "Marathon",
        "race_date": race,
        "primary_goal": "Target Time",
        "target_time": time_spec,
        "training_days": days,
    }


def _matrix_assessment(mpw: float, time_spec: str) -> dict:
    band = _band_from_mpw(mpw)
    thin = mpw <= 0
    longest = min(max(mpw * 0.35, 5.0), 22.0)
    if time_spec == "Finish":
        gd = "FINISH"
        tt_present = False
    else:
        gd = "TIME_TARGET"
        tt_present = True
    return {
        "schema_version": "pre_generation_runner_assessment.v1",
        "activity_summary": {
            "avg_miles_per_week_approx": mpw,
            "longest_run_miles": longest,
            "activities_found": max(8, int(mpw) + 4),
            "lookback_weeks": 8,
            "completed_calendar_weeks_count": 5,
            "pace_reliability": "high",
            "typical_easy_pace_sec_per_mi": 480.0 + max(0.0, (40.0 - mpw) * 2.5),
            "best_sustained_endurance_pace_sec_per_mi": 440.0,
            "long_runs_ge_10_mi_count": 3,
            "weeks_with_long_run_10plus": 3,
        },
        "ambition_gap": {
            "stance": "COHERENT",
            "baseline_band": band,
            "goal_demand": gd,
            "thin_baseline_data": thin,
            "attributions": synthetic_ambition_attributions(
                baseline_band=band,
                goal_demand=gd,
                thin_baseline_data=thin,
                longest_run_miles=longest,
                target_time_present=tt_present,
            ),
        },
        "intake_alignment_state": {
            "generation_ready": True,
            "unresolved_flags": [],
        },
    }


_MATRIX_PRODUCT = list(
    itertools.product(TIMES_ORDERED, DAY_COUNTS, MPWS, WEEKS_TO_RACE)
)
# ~640 combinations; sample every 5th → ~128 cases
_MATRIX_SMOKE_CASES = _MATRIX_PRODUCT[::5]


@pytest.mark.parametrize(
    "time_spec,n_days,mpw,weeks",
    _MATRIX_SMOKE_CASES,
)
def test_readiness_matrix_smoke_decision_domain(
    time_spec: str, n_days: int, mpw: int, weeks: int
):
    plan = _matrix_plan(time_spec, n_days, weeks)
    assess = _matrix_assessment(float(mpw), time_spec)
    out = evaluate_plan_generation_readiness(plan_request=plan, assessment_api=assess)
    assert out["decision"] in (DECISION_ALLOW, DECISION_DEFER, DECISION_BLOCK)


def test_decision_non_decreasing_as_marathon_time_goal_hardens():
    """Time-only goals: stricter (faster) targets do not improve decision vs slower targets."""
    time_only = [t for t in TIMES_ORDERED if t != "Finish"]
    n_days, mpw, weeks = 4, 25, 20
    prev_rank: int | None = None
    for t in time_only:
        plan = _matrix_plan(t, n_days, weeks)
        assess = _matrix_assessment(float(mpw), t)
        out = evaluate_plan_generation_readiness(
            plan_request=plan, assessment_api=assess
        )
        r = _decision_rank(out["decision"])
        if prev_rank is not None:
            assert r >= prev_rank, (t, out["decision"], prev_rank, r)
        prev_rank = r


def test_decision_non_increasing_as_weekly_volume_rises():
    """Holding goal and schedule fixed, more mpw does not yield a worse decision ordinal."""
    t = "4:00:00"
    n_days, weeks = 4, 20
    prev_rank: int | None = None
    for mpw in MPWS:
        plan = _matrix_plan(t, n_days, weeks)
        assess = _matrix_assessment(float(mpw), t)
        out = evaluate_plan_generation_readiness(
            plan_request=plan, assessment_api=assess
        )
        r = _decision_rank(out["decision"])
        if prev_rank is not None:
            assert r <= prev_rank, (mpw, out["decision"], prev_rank, r)
        prev_rank = r

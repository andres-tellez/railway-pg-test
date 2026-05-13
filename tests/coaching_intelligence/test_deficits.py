"""Phase 4.3 — axis deficits are zero when evidence meets targets, positive otherwise."""

from __future__ import annotations

import pytest

from src.coaching_intelligence.policy.deficits import compute_deficits
from src.coaching_intelligence.policy.demand import compute_demand_score
from src.coaching_intelligence.policy.policy_table import marathon_distance_mi
from src.coaching_intelligence.time_clock import parse_clock_seconds


def _plan_marathon_tt(**overrides):
    base = {
        "race_distance": "Marathon",
        "race_date": "2099-12-01",
        "primary_goal": "Target Time",
        "target_time": "4:00:00",
        "training_days": ["Mon", "Tue", "Wed", "Thu", "Sat"],
    }
    base.update(overrides)
    return base


def _demand_for_clock(clock: str) -> float:
    secs = parse_clock_seconds(clock)
    assert secs is not None
    pace = float(secs) / marathon_distance_mi
    return compute_demand_score(pace, "Marathon")


@pytest.mark.parametrize(
    "mpw,expect_positive",
    [(55.0, False), (10.0, True)],
)
def test_volume_deficit_when_mpw_below_or_above_peak_target(
    mpw: float, expect_positive: bool
):
    act = {
        "avg_miles_per_week_approx": mpw,
        "longest_run_miles": 18.0,
        "pace_reliability": "high",
        "typical_easy_pace_sec_per_mi": 400.0,
    }
    plan = _plan_marathon_tt()
    goal_pace_secs = parse_clock_seconds(plan["target_time"])
    assert goal_pace_secs is not None
    gp = float(goal_pace_secs) / marathon_distance_mi
    ds = _demand_for_clock("4:00:00")
    d = compute_deficits(act, plan, demand_score=ds, goal_marathon_pace_sec_per_mi=gp)
    if expect_positive:
        assert d.volume_deficit_mpw is not None and d.volume_deficit_mpw > 0
    else:
        assert d.volume_deficit_mpw is None


@pytest.mark.parametrize(
    "lr_mi,expect_positive",
    [(22.0, False), (4.0, True)],
)
def test_long_run_deficit_scales_with_target_long_run(
    lr_mi: float, expect_positive: bool
):
    act = {
        "avg_miles_per_week_approx": 55.0,
        "longest_run_miles": lr_mi,
        "pace_reliability": "high",
        "typical_easy_pace_sec_per_mi": 400.0,
    }
    plan = _plan_marathon_tt()
    goal_pace_secs = parse_clock_seconds(plan["target_time"])
    assert goal_pace_secs is not None
    gp = float(goal_pace_secs) / marathon_distance_mi
    ds = _demand_for_clock("4:00:00")
    d = compute_deficits(act, plan, demand_score=ds, goal_marathon_pace_sec_per_mi=gp)
    if expect_positive:
        assert d.long_run_deficit_mi is not None and d.long_run_deficit_mi > 0
    else:
        assert d.long_run_deficit_mi is None


def test_pace_deficit_zero_when_easy_pace_near_goal():
    act = {
        "avg_miles_per_week_approx": 45.0,
        "longest_run_miles": 18.0,
        "pace_reliability": "high",
        "typical_easy_pace_sec_per_mi": 620.0,
    }
    plan = _plan_marathon_tt(target_time="5:00:00")
    gp = parse_clock_seconds("5:00:00")
    assert gp is not None
    gp_mi = float(gp) / marathon_distance_mi
    ds = _demand_for_clock("5:00:00")
    d = compute_deficits(
        act, plan, demand_score=ds, goal_marathon_pace_sec_per_mi=gp_mi
    )
    assert d.pace_deficit_sec_per_mi is None


def test_pace_deficit_positive_when_easy_pace_far_from_goal():
    act = {
        "avg_miles_per_week_approx": 45.0,
        "longest_run_miles": 18.0,
        "pace_reliability": "high",
        "typical_easy_pace_sec_per_mi": 720.0,
    }
    plan = _plan_marathon_tt(target_time="4:00:00")
    gp = parse_clock_seconds("4:00:00")
    assert gp is not None
    gp_mi = float(gp) / marathon_distance_mi
    ds = _demand_for_clock("4:00:00")
    d = compute_deficits(
        act, plan, demand_score=ds, goal_marathon_pace_sec_per_mi=gp_mi
    )
    assert d.pace_deficit_sec_per_mi is not None
    assert d.pace_deficit_sec_per_mi > 10.0


def test_frequency_deficit_when_under_day_target():
    act = {
        "avg_miles_per_week_approx": 45.0,
        "longest_run_miles": 18.0,
        "pace_reliability": "high",
        "typical_easy_pace_sec_per_mi": 600.0,
    }
    plan = _plan_marathon_tt(
        training_days=["Mon", "Wed"],
        target_time="3:00:00",
    )
    gp = parse_clock_seconds("3:00:00")
    assert gp is not None
    gp_mi = float(gp) / marathon_distance_mi
    ds = _demand_for_clock("3:00:00")
    d = compute_deficits(
        act, plan, demand_score=ds, goal_marathon_pace_sec_per_mi=gp_mi
    )
    assert d.frequency_deficit_days is not None
    assert d.frequency_deficit_days >= 1.0


def test_time_deficit_when_weeks_to_race_short_for_demand():
    act = {
        "avg_miles_per_week_approx": 40.0,
        "longest_run_miles": 16.0,
        "pace_reliability": "high",
        "typical_easy_pace_sec_per_mi": 500.0,
    }
    plan = _plan_marathon_tt(target_time="3:30:00")
    gp = parse_clock_seconds("3:30:00")
    assert gp is not None
    gp_mi = float(gp) / marathon_distance_mi
    ds = _demand_for_clock("3:30:00")
    d = compute_deficits(
        act,
        plan,
        demand_score=ds,
        goal_marathon_pace_sec_per_mi=gp_mi,
        weeks_to_race=4.0,
    )
    assert d.time_deficit_weeks is not None
    assert d.time_deficit_weeks > 0


def test_time_deficit_none_when_plenty_of_weeks():
    act = {
        "avg_miles_per_week_approx": 40.0,
        "longest_run_miles": 16.0,
        "pace_reliability": "high",
        "typical_easy_pace_sec_per_mi": 500.0,
    }
    plan = _plan_marathon_tt(target_time="3:30:00")
    gp = parse_clock_seconds("3:30:00")
    assert gp is not None
    gp_mi = float(gp) / marathon_distance_mi
    ds = _demand_for_clock("3:30:00")
    d = compute_deficits(
        act,
        plan,
        demand_score=ds,
        goal_marathon_pace_sec_per_mi=gp_mi,
        weeks_to_race=30.0,
    )
    assert d.time_deficit_weeks is None

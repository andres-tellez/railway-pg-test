"""Unit tests for long-run selection (Insights systems.long v1)."""

from __future__ import annotations

from src.smartcoach_mobile_coach.long_run_insights_selection import (
    LONG_RUN_MIN_MOVING_TIME_SEC,
    LongRunCandidate,
    infer_long_run_candidate,
    qualifies_planned_long_run,
    select_long_run_for_week,
)


def _candidate(
    *,
    activity_id: int,
    moving_time: int,
    insights_system: str = "easy",
    matched_run_type_key: str | None = None,
    date_plan_run_type_key: str | None = None,
    planned_type: str | None = None,
    executed_type: str | None = None,
) -> LongRunCandidate:
    return LongRunCandidate(
        activity_id=activity_id,
        moving_time=moving_time,
        insights_system=insights_system,
        matched_run_type_key=matched_run_type_key,
        date_plan_run_type_key=date_plan_run_type_key,
        planned_type=planned_type,
        executed_type=executed_type,
        hr_drift_pct=2.0,
        avg_pace_min_per_mi=10.0,
        avg_hr_bpm=140.0,
    )


def test_short_week_three_and_five_mile_easy_runs_produce_no_long_run():
    """3 mi + 5 mi easy week stays Easy-only; no inferred Long run."""
    week = [
        _candidate(activity_id=1, moving_time=24 * 60),
        _candidate(activity_id=2, moving_time=40 * 60),
    ]
    assert select_long_run_for_week(week) is None
    assert infer_long_run_candidate(week) is None


def test_planned_long_run_requires_seventy_five_minutes():
    planned_short = _candidate(
        activity_id=1,
        moving_time=60 * 60,
        matched_run_type_key="long_run",
    )
    assert qualifies_planned_long_run(planned_short) is False

    planned_ok = _candidate(
        activity_id=2,
        moving_time=LONG_RUN_MIN_MOVING_TIME_SEC,
        matched_run_type_key="long_run",
    )
    assert qualifies_planned_long_run(planned_ok) is True
    assert select_long_run_for_week([planned_ok]) == planned_ok


def test_planned_long_run_excludes_race_workout():
    race = _candidate(
        activity_id=1,
        moving_time=90 * 60,
        matched_run_type_key="race",
    )
    assert qualifies_planned_long_run(race) is False


def test_planned_long_run_prefers_longest_when_multiple_qualify():
    shorter = _candidate(
        activity_id=1,
        moving_time=80 * 60,
        date_plan_run_type_key="long_run",
    )
    longer = _candidate(
        activity_id=2,
        moving_time=95 * 60,
        date_plan_run_type_key="long_run",
    )
    assert select_long_run_for_week([shorter, longer]) == longer


def test_infer_long_run_requires_seventy_five_minutes_and_clear_gap():
    easy_a = _candidate(activity_id=1, moving_time=65 * 60)
    easy_b = _candidate(activity_id=2, moving_time=65 * 60)
    long_enough_but_not_distinct = _candidate(activity_id=3, moving_time=80 * 60)
    week = [easy_a, easy_b, long_enough_but_not_distinct]
    assert infer_long_run_candidate(week) is None

    distinct_long = _candidate(activity_id=4, moving_time=95 * 60)
    week_with_gap = [easy_a, easy_b, distinct_long]
    assert infer_long_run_candidate(week_with_gap) == distinct_long


def test_infer_long_run_accepts_median_plus_twenty_minutes():
    others = [
        _candidate(activity_id=1, moving_time=40 * 60),
        _candidate(activity_id=2, moving_time=44 * 60),
    ]
    longest = _candidate(activity_id=3, moving_time=65 * 60)
    assert infer_long_run_candidate([*others, longest]) is None

    long_by_padding = _candidate(activity_id=4, moving_time=76 * 60)
    assert infer_long_run_candidate([*others, long_by_padding]) == long_by_padding


def test_rule_one_wins_over_inference():
    planned = _candidate(
        activity_id=1,
        moving_time=80 * 60,
        matched_run_type_key="long_run",
    )
    longer_easy = _candidate(activity_id=2, moving_time=120 * 60)
    assert select_long_run_for_week([planned, longer_easy]) == planned


def test_tempo_runs_are_not_inferred_as_long():
    tempo = _candidate(activity_id=1, moving_time=90 * 60, insights_system="tempo")
    assert infer_long_run_candidate([tempo]) is None

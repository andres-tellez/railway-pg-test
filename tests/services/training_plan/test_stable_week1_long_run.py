"""Stable Week-1 long run from recent weekly longest-run anchors."""

import pytest

from src.services.training_plan.v2.shared_v2.long_run_signals import (
    build_week1_long_run_explanation,
    compute_stable_week1_long_run_start,
)


def test_outlier_single_global_max_uses_median_not_max_plus_one():
    # One week at 13, otherwise lower — should not jump to 15 (13+2 style outlier)
    miles, meta = compute_stable_week1_long_run_start(
        [13.0, 12.0, 11.0, 10.0, 12.0, 10.0],
        long_run_increment=1.0,
        min_long_run_mi=5.0,
    )
    assert meta["ties_at_global_max"] == 1
    assert meta["median_long_run"] == pytest.approx(11.5)
    assert meta["most_recent_long_run"] == 13.0
    assert meta["raw_candidate"] == pytest.approx(13.0)  # max(median, most recent)
    assert miles <= meta["cap_ceiling_miles"] + 0.01
    # Capped at 1.1× median (12.65), half-mile round → 12.5
    assert miles == 12.5


def test_repeated_global_max_allows_increment_then_median_cap():
    miles, meta = compute_stable_week1_long_run_start(
        [13.0, 12.0, 13.0, 11.0, 10.0, 12.0],
        long_run_increment=1.0,
        min_long_run_mi=5.0,
    )
    assert meta["ties_at_global_max"] >= 2
    assert meta["rule"] == "max_plus_increment_repeated_peak_anchor"
    assert meta["raw_candidate"] == pytest.approx(14.0)
    # median = 12, +10% cap = 13.2
    assert miles == 13.0


def test_ten_percent_cap_limits_boost_when_median_low():
    miles, meta = compute_stable_week1_long_run_start(
        [20.0, 10.0, 10.0, 10.0],
        long_run_increment=1.0,
        min_long_run_mi=5.0,
    )
    assert meta["ties_at_global_max"] == 1
    assert meta["median_long_run"] == pytest.approx(10.0)
    assert meta["cap_ceiling_miles"] == pytest.approx(11.0)
    assert miles <= 11.0


def test_outlier_when_most_recent_below_median_candidate_is_median():
    miles, meta = compute_stable_week1_long_run_start(
        [10.0, 12.0, 12.0, 13.0],
        long_run_increment=1.0,
        min_long_run_mi=5.0,
    )
    assert meta["most_recent_long_run"] == 10.0
    assert meta["median_long_run"] == pytest.approx(12.0)
    assert meta["raw_candidate"] == pytest.approx(12.0)
    assert miles == 12.0


def test_empty_series_raises():
    with pytest.raises(ValueError):
        compute_stable_week1_long_run_start([])


def test_distant_high_weeks_suppressed_by_recent_three_week_cap():
    miles, meta = compute_stable_week1_long_run_start(
        [12.0, 11.0, 10.0, 18.0, 17.0, 16.0],
        long_run_increment=1.0,
        min_long_run_mi=5.0,
    )
    assert meta["recent_weighting_applied"] is True
    assert meta["explanation_reason_key"] == "recent_median_cap"
    assert miles == 12.0


def test_build_week1_long_run_explanation_coach_copy():
    series = [13.0, 12.0, 11.0, 10.0, 12.0, 10.0]
    miles, meta = compute_stable_week1_long_run_start(series)
    text = build_week1_long_run_explanation(
        weekly_series=series,
        start_lr_miles=miles,
        start_meta=meta,
        start_rule="median_single_peak_week_anchor",
    )
    assert "10-13" in text or "10–13" in text
    assert "Week 1 long run:" in text
    assert str(int(miles)) in text or str(miles) in text


def test_build_week1_long_run_explanation_recovery_branch():
    text = build_week1_long_run_explanation(
        weekly_series=[16.0, 15.0, 14.0],
        start_lr_miles=11.0,
        start_meta={"longest_recent": 16.0},
        start_rule="recovery_week_after_consecutive_runs",
    )
    assert "recovery" in text.lower()
    assert "11.0" in text

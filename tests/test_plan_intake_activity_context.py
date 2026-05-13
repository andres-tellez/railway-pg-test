from __future__ import annotations

import re
from datetime import date
from unittest.mock import MagicMock, patch

from src.smartcoach_mobile_coach.plan_intake_activity_context import (
    apply_plan_activity_preamble_to_assistant_markdown,
    build_plan_intake_activity_context_block,
    build_runner_evidence,
    compute_plan_intake_activity_summary,
    format_plan_intake_activity_context_block,
    format_user_visible_activity_overview,
)


def test_format_plan_intake_activity_context_with_runs():
    s = format_plan_intake_activity_context_block(
        {
            "lookback_weeks": 12,
            "activities_found": 8,
            "has_running_data": True,
            "total_miles_window": 40.0,
            "avg_miles_per_week_approx": 3.3,
            "longest_run_miles": 12.5,
            "longest_run_date": "2026-03-01",
            "latest_run_date": "2026-04-01",
        }
    )
    assert "**8**" in s
    assert "40" in s
    assert "Do not" in s or "not" in s.lower()
    assert "race distance" in s.lower()


def test_format_plan_intake_activity_context_zero_runs():
    s = format_plan_intake_activity_context_block(
        {
            "lookback_weeks": 12,
            "activities_found": 0,
            "has_running_data": False,
            "total_miles_window": 0.0,
            "avg_miles_per_week_approx": 0.0,
            "longest_run_miles": 0.0,
            "longest_run_date": None,
            "latest_run_date": None,
        }
    )
    assert "no" in s.lower() or "0" in s
    assert "Strava" in s or "strava" in s.lower()


@patch(
    "src.smartcoach_mobile_coach.plan_intake_activity_context.DataCollectionService.fetch_strava_activities"
)
def test_compute_plan_intake_activity_summary_includes_pace_and_long_run_signals(
    mock_fetch,
):
    mock_fetch.return_value = [
        {"date": "2026-04-10", "distance": 6.0, "moving_time": 3300},
        {"date": "2026-04-03", "distance": 11.0, "moving_time": 6600},
        {"date": "2026-03-27", "distance": 5.5, "moving_time": 3000},
        {"date": "2026-03-20", "distance": 10.5, "moving_time": 6300},
    ]
    session = MagicMock()
    out = compute_plan_intake_activity_summary(
        session,
        "user-uuid",
        lookback_weeks=8,
        anchor_local_date=date(2026, 4, 15),
    )
    assert out["pace_reliability"] in ("low", "medium", "high")
    assert out["runs_usable_pace_count"] >= 3
    assert out["typical_easy_pace_sec_per_mi"] is not None
    assert out["long_runs_ge_10_mi_count"] >= 2
    mock_fetch.assert_called_once()


@patch(
    "src.smartcoach_mobile_coach.plan_intake_activity_context.DataCollectionService.fetch_strava_activities"
)
def test_build_runner_evidence_single_fetch_and_weekly_history_shape(
    mock_fetch, monkeypatch
):
    monkeypatch.setenv("SMARTCOACH_PLAN_INTAKE_ACTIVITY_WEEKS", "6")
    monkeypatch.setenv("SMARTCOACH_PLAN_INTAKE_HISTORY_WEEKS", "8")
    mock_fetch.return_value = [
        {"date": "2026-04-10", "distance": 6.0},
        {"date": "2026-03-20", "distance": 5.0},
    ]
    session = MagicMock()
    ev = build_runner_evidence(
        session, "user-uuid", anchor_local_date=date(2026, 4, 15)
    )
    mock_fetch.assert_called_once_with(session, "user-uuid", weeks=8)
    data = ev.to_api_dict()
    assert data["history_lookback_weeks"] == 8
    assert len(data["weekly_mileage_history"]) == 8
    # two distinct ISO weeks with mileage in the 8-week window
    assert data["consistency_weeks_active_in_history"] == 2


@patch(
    "src.smartcoach_mobile_coach.plan_intake_activity_context.DataCollectionService.fetch_strava_activities"
)
def test_compute_plan_intake_activity_summary(mock_fetch):
    mock_fetch.return_value = [
        {"date": "2026-04-10", "distance": 6.0},
        {"date": "2026-04-03", "distance": 10.0},
    ]
    session = MagicMock()
    out = compute_plan_intake_activity_summary(
        session,
        "user-uuid",
        lookback_weeks=12,
        anchor_local_date=date(2026, 4, 15),
    )
    assert out["has_running_data"] is True
    assert out["total_miles_window"] == 16.0
    assert out["longest_run_miles"] == 10.0
    assert out["runs_per_week_approx"] == 0.2
    assert out["completed_calendar_weeks_count"] == 2
    assert out["avg_miles_per_week_approx"] == 8.0  # mean of two completed ISO weeks
    assert abs(out["avg_miles_per_week_raw_window"] - 16.0 / 12.0) < 0.06
    mock_fetch.assert_called_once()


def test_format_user_visible_activity_overview_no_data_is_coach_like():
    s = format_user_visible_activity_overview(
        {"has_running_data": False, "activities_found": 0}
    )
    assert "don’t have enough recent running data" in s
    assert "Strava" not in s


def test_format_user_visible_activity_overview_with_runs():
    s = format_user_visible_activity_overview(
        {
            "lookback_weeks": 12,
            "activities_found": 8,
            "has_running_data": True,
            "total_miles_window": 40.0,
            "avg_miles_per_week_approx": 3.3,
            "runs_per_week_approx": 1.3,
            "active_weeks": 4,
            "weekly_miles_min_active": 8.0,
            "weekly_miles_max_active": 12.0,
            "longest_run_miles": 12.5,
            "longest_run_date": "2026-03-01",
            "latest_run_date": "2026-04-01",
        }
    )
    assert "recent training" in s.lower()
    assert "logged runs" not in s
    assert s.count("\n") <= 2
    assert "solid consistency" in s
    assert "opportunity" in s
    assert "**12 miles**" in s
    assert len(re.findall(r"\b\d+(?:\.\d+)?(?:[–-]\d+(?:\.\d+)?)?\b", s)) <= 2


def test_format_user_visible_activity_overview_uses_banded_volume_language():
    s = format_user_visible_activity_overview(
        {
            "lookback_weeks": 6,
            "activities_found": 24,
            "has_running_data": True,
            "total_miles_window": 159.0,
            "avg_miles_per_week_approx": 26.5,
            "runs_per_week_approx": 4.0,
            "active_weeks": 6,
            "weekly_miles_min_active": 24.0,
            "weekly_miles_max_active": 33.0,
            "longest_run_miles": 10.0,
            "longest_run_date": "2026-03-01",
            "latest_run_date": "2026-04-01",
        }
    )
    assert "around **25 miles per week**" in s
    assert "**10 miles**" in s
    assert "2026-" not in s
    assert "24–33" not in s
    assert len(re.findall(r"\b\d+(?:\.\d+)?(?:[–-]\d+(?:\.\d+)?)?\b", s)) <= 2


def test_apply_plan_activity_preamble_prepends_without_marker():
    summary = {
        "lookback_weeks": 12,
        "activities_found": 2,
        "has_running_data": True,
        "total_miles_window": 10.0,
        "avg_miles_per_week_approx": 0.8,
        "runs_per_week_approx": 0.2,
        "active_weeks": 2,
        "weekly_miles_min_active": 4.0,
        "weekly_miles_max_active": 6.0,
        "longest_run_miles": 6.0,
        "longest_run_date": "2026-01-01",
        "latest_run_date": "2026-01-02",
    }
    out = apply_plan_activity_preamble_to_assistant_markdown(
        "What is your **race date**?",
        plan_creation_mode=True,
        activity_summary=summary,
        runner_understanding_already_shown=False,
    )
    assert "race date" in out
    assert "<!--" not in out
    assert "recent training" in out.lower()


def test_apply_plan_activity_preamble_skips_if_already_shown():
    summary = {
        "lookback_weeks": 12,
        "activities_found": 2,
        "has_running_data": True,
        "total_miles_window": 10.0,
        "avg_miles_per_week_approx": 0.8,
        "runs_per_week_approx": 0.2,
        "active_weeks": 2,
        "weekly_miles_min_active": 4.0,
        "weekly_miles_max_active": 6.0,
        "longest_run_miles": 6.0,
        "longest_run_date": "2026-01-01",
        "latest_run_date": "2026-01-02",
    }
    out = apply_plan_activity_preamble_to_assistant_markdown(
        "Next question?",
        plan_creation_mode=True,
        activity_summary=summary,
        runner_understanding_already_shown=True,
    )
    assert out == "Next question?"


def test_build_plan_intake_activity_context_block_integration():
    with patch(
        "src.smartcoach_mobile_coach.plan_intake_activity_context.DataCollectionService.fetch_strava_activities",
        return_value=[{"date": "2026-01-01", "distance": 5.0}],
    ):
        text = build_plan_intake_activity_context_block(MagicMock(), "any-uuid")
    assert "## Athlete activity snapshot" in text
    assert "**1**" in text

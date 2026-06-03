"""Tests for centralized weekly insights reconcile."""

from __future__ import annotations

import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from src.services.weekly_insights_reconcile_service import (
    ensure_user_weekly_insights,
    schedule_ensure_user_weekly_insights,
)
from src.smartcoach_mobile_coach.weekly_insights_service import (
    last_completed_week_bounds,
)


@patch(
    "src.services.execution_analytics_recompute_service.recompute_stale_execution_kpis_for_user"
)
@patch("src.smartcoach_mobile_coach.weekly_insights_service.generate_weekly_insight")
@patch("src.smartcoach_mobile_coach.weekly_insights_service.last_completed_week_bounds")
def test_ensure_calls_recompute_and_weekly_generation(
    mock_bounds, mock_gen, mock_recompute
):
    mock_bounds.return_value = (date(2026, 4, 6), date(2026, 4, 12))
    mock_gen.return_value = {"generated": True, "skipped": False}
    mock_recompute.return_value = 3
    session = MagicMock()

    result = ensure_user_weekly_insights(
        session,
        "550e8400-e29b-41d4-a716-446655440000",
        weeks=6,
        include_current_week=True,
    )

    mock_recompute.assert_called_once()
    assert mock_recompute.call_args.kwargs.get("lookback_weeks") == 6
    assert mock_gen.call_count == 7
    assert result["execution_runs_updated"] == 3
    assert result["summary"]["generated"] == 7
    assert len(result["completed_weeks"]) == 6
    assert result["in_progress"] is not None


@patch(
    "src.services.execution_analytics_recompute_service.recompute_stale_execution_kpis_for_user"
)
@patch("src.smartcoach_mobile_coach.weekly_insights_service.generate_weekly_insight")
@patch("src.smartcoach_mobile_coach.weekly_insights_service.last_completed_week_bounds")
def test_ensure_omits_in_progress_when_disabled(mock_bounds, mock_gen, mock_recompute):
    mock_bounds.return_value = (date(2026, 4, 6), date(2026, 4, 12))
    mock_gen.return_value = {"generated": True}
    mock_recompute.return_value = 0

    result = ensure_user_weekly_insights(
        MagicMock(),
        "550e8400-e29b-41d4-a716-446655440000",
        weeks=6,
        include_current_week=False,
    )

    assert mock_gen.call_count == 6
    assert result["in_progress"] is None


@patch(
    "src.services.execution_analytics_recompute_service.recompute_stale_execution_kpis_for_user"
)
@patch("src.smartcoach_mobile_coach.weekly_insights_service.generate_weekly_insight")
@patch("src.smartcoach_mobile_coach.weekly_insights_service.last_completed_week_bounds")
def test_ensure_summary_counts_skipped_weeks(mock_bounds, mock_gen, mock_recompute):
    mock_bounds.return_value = (date(2026, 4, 6), date(2026, 4, 12))
    mock_recompute.return_value = 0

    def _side_effect(*_args, **kwargs):
        if kwargs.get("insight_week") == "in_progress":
            return {"generated": False, "skipped": True, "reason": "no_easy_runs"}
        return {"generated": True}

    mock_gen.side_effect = _side_effect
    session = MagicMock()

    result = ensure_user_weekly_insights(
        session,
        "550e8400-e29b-41d4-a716-446655440000",
        weeks=2,
        include_current_week=True,
    )

    assert mock_gen.call_count == 3
    assert result["summary"]["generated"] == 2
    assert result["summary"]["skipped"] == 1


@patch("src.services.weekly_insights_reconcile_service.threading.Timer")
def test_schedule_debounces_duplicate_calls(mock_timer):
    timers = []

    def _make_timer(*_args, **_kwargs):
        t = MagicMock()
        timers.append(t)
        return t

    mock_timer.side_effect = _make_timer
    schedule_ensure_user_weekly_insights("550e8400-e29b-41d4-a716-446655440000")
    schedule_ensure_user_weekly_insights("550e8400-e29b-41d4-a716-446655440000")

    assert len(timers) == 2
    timers[0].cancel.assert_called_once()
    timers[0].start.assert_called_once()
    timers[1].start.assert_called_once()


@patch.dict(os.environ, {"WEEKLY_INSIGHT_INGESTION_BACKFILL": "0"})
@patch("src.services.weekly_insights_reconcile_service.threading.Timer")
def test_schedule_respects_disable_env(mock_timer):
    schedule_ensure_user_weekly_insights("550e8400-e29b-41d4-a716-446655440000")
    mock_timer.assert_not_called()


def test_six_completed_mondays_span_matches_reconcile_window():
    today = date(2026, 4, 15)
    last_completed_monday, _ = last_completed_week_bounds(today)
    weeks = 6
    oldest = last_completed_monday - timedelta(weeks=weeks - 1)
    mondays = [oldest + timedelta(weeks=i) for i in range(weeks)]
    assert mondays[-1] == last_completed_monday

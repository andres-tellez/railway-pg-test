"""Tests for post-ingestion weekly insight backfill scheduling."""

from __future__ import annotations

import os
from datetime import date, timedelta
from unittest.mock import patch

from src.smartcoach_mobile_coach.weekly_insights_service import (
    last_completed_week_bounds,
)
from src.services.weekly_insight_post_ingestion_backfill import (
    _run_backfill,
    schedule_weekly_insights_after_strava_ingestion,
)


def test_six_completed_mondays_span_five_weeks_before_last_completed():
    today = date(2026, 4, 15)  # Wednesday
    last_completed_monday, _ = last_completed_week_bounds(today)
    assert last_completed_monday == date(2026, 4, 6)
    oldest = last_completed_monday - timedelta(weeks=5)
    assert oldest == date(2026, 3, 2)
    mondays = [oldest + timedelta(weeks=i) for i in range(6)]
    assert mondays[0] == date(2026, 3, 2)
    assert mondays[-1] == date(2026, 4, 6)


@patch("src.services.weekly_insight_post_ingestion_backfill.threading.Thread")
def test_schedule_starts_daemon_thread_on_inserts(mock_thread):
    schedule_weekly_insights_after_strava_ingestion(
        "550e8400-e29b-41d4-a716-446655440000",
        force_full_sync=False,
        inserted_count=2,
    )
    mock_thread.assert_called_once()
    _, kwargs = mock_thread.call_args
    assert kwargs.get("daemon") is True
    assert kwargs["args"] == ("550e8400-e29b-41d4-a716-446655440000",)


@patch("src.services.weekly_insight_post_ingestion_backfill.threading.Thread")
def test_schedule_starts_on_force_full_even_if_zero_inserts(mock_thread):
    schedule_weekly_insights_after_strava_ingestion(
        "550e8400-e29b-41d4-a716-446655440000",
        force_full_sync=True,
        inserted_count=0,
    )
    mock_thread.assert_called_once()


@patch("src.services.weekly_insight_post_ingestion_backfill.threading.Thread")
def test_schedule_skips_without_user(mock_thread):
    schedule_weekly_insights_after_strava_ingestion(
        "",
        force_full_sync=True,
        inserted_count=5,
    )
    mock_thread.assert_not_called()


@patch("src.services.weekly_insight_post_ingestion_backfill.threading.Thread")
def test_schedule_skips_when_no_inserts_and_not_force_full(mock_thread):
    schedule_weekly_insights_after_strava_ingestion(
        "550e8400-e29b-41d4-a716-446655440000",
        force_full_sync=False,
        inserted_count=0,
    )
    mock_thread.assert_not_called()


@patch.dict(os.environ, {"WEEKLY_INSIGHT_INGESTION_BACKFILL": "0"})
@patch("src.services.weekly_insight_post_ingestion_backfill.threading.Thread")
def test_schedule_respects_disable_env(mock_thread):
    schedule_weekly_insights_after_strava_ingestion(
        "550e8400-e29b-41d4-a716-446655440000",
        force_full_sync=True,
        inserted_count=1,
    )
    mock_thread.assert_not_called()


@patch(
    "src.services.execution_analytics_recompute_service.recompute_stale_execution_kpis_for_user"
)
@patch("src.db.db_session.get_session")
@patch("src.smartcoach_mobile_coach.weekly_insights_service.generate_weekly_insight")
@patch("src.smartcoach_mobile_coach.weekly_insights_service.last_completed_week_bounds")
def test_run_backfill_calls_completed_then_in_progress(
    mock_bounds, mock_gen, mock_get_session, mock_recompute
):
    mock_session = mock_get_session.return_value
    mock_bounds.return_value = (date(2026, 4, 6), date(2026, 4, 12))
    mock_gen.return_value = {"generated": True, "skipped": False}
    mock_recompute.return_value = 5

    _run_backfill("550e8400-e29b-41d4-a716-446655440000")

    mock_recompute.assert_called_once_with(
        mock_session, "550e8400-e29b-41d4-a716-446655440000"
    )

    assert mock_gen.call_count == 7
    oldest = date(2026, 4, 6) - timedelta(weeks=5)
    for i, c in enumerate(mock_gen.call_args_list[:6]):
        ref_date = c.kwargs["ref_date"]
        week_mon = oldest + timedelta(weeks=i)
        assert ref_date == week_mon + timedelta(days=7)
        assert c.kwargs["insight_week"] == "completed"

    last = mock_gen.call_args_list[6]
    assert last.kwargs["insight_week"] == "in_progress"
    assert last.kwargs["ref_date"] == date.today()
    mock_session.close.assert_called_once()

"""Unit tests for admin weekly insights batch."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from src.services.admin_weekly_insights_batch_service import (
    _process_users,
    run_weekly_insights_admin_batch,
)


@patch("src.smartcoach_mobile_coach.weekly_insights_service.generate_weekly_insight")
def test_process_users_counts(mock_gen):
    mock_gen.side_effect = [
        {"generated": True},
        {"generated": False, "reason": "no_easy_runs"},
        {"generated": True},
    ]
    session = MagicMock()
    stats = _process_users(
        session,
        ["u1", "u2", "u3"],
        ref_date=date(2026, 4, 13),
        insight_week="completed",
        label="test",
    )
    assert stats == {"generated": 2, "skipped": 1, "errors": 0}
    assert mock_gen.call_count == 3


@patch("src.smartcoach_mobile_coach.weekly_insights_service.generate_weekly_insight")
def test_process_users_counts_errors(mock_gen):
    mock_gen.side_effect = [RuntimeError("db"), {"generated": True}]
    session = MagicMock()
    stats = _process_users(
        session,
        ["u1", "u2"],
        ref_date=date(2026, 4, 13),
        insight_week="in_progress",
        label="test",
    )
    assert stats["errors"] == 1
    assert stats["generated"] == 1
    assert stats["skipped"] == 0


@patch("src.services.admin_weekly_insights_batch_service._process_users")
@patch("src.smartcoach_mobile_coach.weekly_insights_service.get_users_with_easy_runs")
def test_run_admin_batch_invokes_six_completed_plus_in_progress(
    mock_get_users, mock_process
):
    mock_get_users.return_value = []
    mock_process.return_value = {"generated": 0, "skipped": 0, "errors": 0}
    session = MagicMock()
    fixed = date(2026, 4, 15)
    with patch("src.services.admin_weekly_insights_batch_service.date") as mock_date:
        mock_date.today = lambda: fixed
        out = run_weekly_insights_admin_batch(session)

    assert mock_get_users.call_count == 7
    assert mock_process.call_count == 7
    completed = [
        c
        for c in mock_process.call_args_list
        if c.kwargs["insight_week"] == "completed"
    ]
    in_prog = [
        c
        for c in mock_process.call_args_list
        if c.kwargs["insight_week"] == "in_progress"
    ]
    assert len(completed) == 6
    assert len(in_prog) == 1
    assert out["six_completed_weeks"]["totals"]["errors"] == 0
    assert "weeks" in out["six_completed_weeks"]
    assert len(out["six_completed_weeks"]["weeks"]) == 6

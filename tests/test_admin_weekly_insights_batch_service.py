"""Unit tests for admin weekly insights batch."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from src.services.admin_weekly_insights_batch_service import _process_users


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

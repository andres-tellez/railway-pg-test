"""Tests for execution analytics recompute scheduling and window helpers."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from src.services.execution_analytics_recompute_service import (
    recompute_execution_kpis_for_window,
    recompute_recent_execution_kpis,
    schedule_post_activity_execution_recompute,
    schedule_profile_refresh_execution_recompute,
)


@patch(
    "src.services.execution_analytics_recompute_service.refresh_activity_execution_kpis",
    return_value=2,
)
@patch("src.services.execution_analytics_recompute_service._activity_ids_in_window")
def test_recompute_window_delegates_to_producer(mock_ids, mock_refresh):
    session = MagicMock()
    mock_ids.return_value = [101, 102]

    count = recompute_execution_kpis_for_window(
        session,
        user_id="user-1",
        athlete_id=42,
        after_ts=1000,
        before_ts=2000,
        limit=50,
    )

    mock_ids.assert_called_once()
    mock_refresh.assert_called_once_with(
        session,
        "user-1",
        activity_ids=[101, 102],
        commit=True,
    )
    assert count == 2


@patch(
    "src.services.execution_analytics_recompute_service.refresh_activity_execution_kpis",
    return_value=0,
)
def test_recompute_window_no_runs(mock_refresh):
    session = MagicMock()
    session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
        []
    )

    with patch(
        "src.services.execution_analytics_recompute_service._activity_ids_in_window",
        return_value=[],
    ):
        count = recompute_execution_kpis_for_window(session, user_id="user-1")

    mock_refresh.assert_not_called()
    assert count == 0


@patch(
    "src.services.execution_analytics_recompute_service.refresh_activity_execution_kpis",
    return_value=3,
)
def test_recompute_recent_no_runs_returns_zero(mock_refresh):
    session = MagicMock()
    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
        []
    )

    count = recompute_recent_execution_kpis(session, "user-1")

    mock_refresh.assert_not_called()
    assert count == 0


@patch.dict(os.environ, {"EXECUTION_RECOMPUTE_ON_ACTIVITY": "0"})
@patch("threading.Timer")
def test_schedule_post_activity_respects_disable(mock_timer):
    schedule_post_activity_execution_recompute("user-1")
    mock_timer.assert_not_called()


@patch.dict(os.environ, {"EXECUTION_RECOMPUTE_ON_PROFILE_REFRESH": "0"})
@patch("threading.Timer")
def test_schedule_profile_refresh_respects_disable(mock_timer):
    schedule_profile_refresh_execution_recompute("user-1")
    mock_timer.assert_not_called()

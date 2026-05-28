"""Shared fixtures for smartcoach_mobile_coach tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _default_no_latest_weekly_insight_row(monkeypatch, request):
    """Most history tests mock chart SQL only; avoid MagicMock latest-week rows."""
    if request.node.get_closest_marker("latest_week_row"):
        return
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.weekly_insights_service._fetch_latest_weekly_insight_row",
        lambda _session, _user_id: None,
    )

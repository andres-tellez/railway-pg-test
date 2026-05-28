"""``latest_week`` on /weekly-history matches /weekly scoreboard core fields."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.smartcoach_mobile_coach.weekly_insights_service import (
    _LATEST_WEEK_NO_INSIGHT_MESSAGE,
    _build_latest_week_scoreboard,
    get_latest_weekly_insight,
    get_weekly_insight_history,
)

USER_ID = "00000000-0000-0000-0000-000000000001"

_SCOREBOARD_PARITY_KEYS = (
    "has_insight",
    "week_start",
    "week_end",
    "overall_band",
    "kpis",
    "easy_run_count",
    "total_run_count",
    "summary_text",
    "action_text",
    "generated_at",
    "systems",
)


def _sample_insight_row() -> SimpleNamespace:
    return SimpleNamespace(
        week_start=date(2026, 4, 7),
        week_end=date(2026, 4, 13),
        overall_band="green",
        hr_drift_pct=2.5,
        z2_pace_min_per_mi=9.5,
        efficiency=1.2,
        hr_drift_band="green",
        z2_pace_band="green",
        efficiency_band="green",
        hr_drift_delta=-0.5,
        z2_pace_delta=-0.01,
        easy_avg_hr=142.0,
        efficiency_delta=0.1,
        easy_avg_hr_band="green",
        easy_avg_hr_delta=-1.5,
        easy_run_count=3,
        total_run_count=5,
        summary_text="Easy volume looked controlled.",
        action_text="Keep the next long run aerobic.",
        generated_at=datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc),
        kpi_snapshot=None,
    )


@pytest.mark.latest_week_row
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service._fetch_latest_weekly_insight_row",
)
def test_latest_week_scoreboard_matches_weekly_core_fields(mock_fetch_row):
    row = _sample_insight_row()
    mock_fetch_row.return_value = row
    session = MagicMock()

    weekly = get_latest_weekly_insight(session, USER_ID, slim=False)
    latest_week = _build_latest_week_scoreboard(session, USER_ID)

    for key in _SCOREBOARD_PARITY_KEYS:
        assert latest_week[key] == weekly[key]
    assert "insight_detail_level" not in latest_week
    assert "hr_drift_band_zones" not in latest_week


@pytest.mark.latest_week_row
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service._fetch_latest_weekly_insight_row",
    return_value=None,
)
def test_latest_week_no_row_message(mock_fetch_row):
    session = MagicMock()
    latest_week = _build_latest_week_scoreboard(session, USER_ID)
    assert latest_week == {
        "has_insight": False,
        "message": _LATEST_WEEK_NO_INSIGHT_MESSAGE,
    }


@pytest.mark.latest_week_row
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service._fetch_tempo_week_rollups_batch",
    return_value={},
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service.get_primary_athlete_id",
    return_value=None,
)
@patch(
    "src.smartcoach_mobile_coach.weekly_insights_service._fetch_latest_weekly_insight_row",
)
def test_weekly_history_always_includes_latest_week(
    mock_fetch_row,
    _mock_athlete,
    _mock_tempo_batch,
):
    row = _sample_insight_row()
    mock_fetch_row.return_value = row
    session = MagicMock()

    out = get_weekly_insight_history(session, USER_ID, weeks=1)

    assert "latest_week" in out
    assert out["latest_week"]["has_insight"] is True
    assert out["latest_week"]["week_start"] == "2026-04-07"
    assert len(out["latest_week"]["kpis"]) == 4

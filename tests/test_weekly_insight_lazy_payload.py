"""Lazy (orientation) vs full payloads for get_latest_weekly_insight / coach tool."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.smartcoach_mobile_coach.agent_tools import execute_tool
from src.smartcoach_mobile_coach.weekly_insights_service import (
    WEEKLY_INSIGHT_ORIENTATION_NOTE,
    get_latest_weekly_insight,
    weekly_insight_tool_slim_default_from_env,
)


def test_get_latest_weekly_insight_slim_no_row():
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = None
    out = get_latest_weekly_insight(
        session, "00000000-0000-0000-0000-000000000001", slim=True
    )
    assert out["has_insight"] is False
    assert out["insight_detail_level"] == "orientation"
    assert out["orientation_note"] == WEEKLY_INSIGHT_ORIENTATION_NOTE
    assert "hr_drift_band_zones" not in out
    assert "systems" not in out


def test_get_latest_weekly_insight_slim_with_row():
    row = SimpleNamespace(
        week_start=date(2026, 4, 7),
        week_end=date(2026, 4, 13),
        overall_band="green",
    )
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = row
    out = get_latest_weekly_insight(
        session, "00000000-0000-0000-0000-000000000001", slim=True
    )
    assert out["has_insight"] is True
    assert out["insight_detail_level"] == "orientation"
    assert out["week_start"] == "2026-04-07"
    assert out["week_end"] == "2026-04-13"
    assert out["overall_band"] == "green"
    assert "kpis" not in out
    assert out["orientation_note"] == WEEKLY_INSIGHT_ORIENTATION_NOTE


def test_get_latest_weekly_insight_full_includes_kpis():
    row = SimpleNamespace(
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
        summary_text=None,
        action_text=None,
        generated_at=datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc),
        kpi_snapshot=None,
    )
    session = MagicMock()
    session.execute.return_value.fetchone.return_value = row
    out = get_latest_weekly_insight(
        session, "00000000-0000-0000-0000-000000000001", slim=False
    )
    assert out["has_insight"] is True
    assert out["insight_detail_level"] == "full"
    assert len(out["kpis"]) == 4
    assert "hr_drift_band_zones" in out


@pytest.mark.parametrize(
    "env_val,expected",
    [
        (None, True),
        ("1", True),
        ("0", False),
        ("false", False),
    ],
)
def test_weekly_insight_tool_slim_env(monkeypatch, env_val, expected):
    if env_val is None:
        monkeypatch.delenv("SMARTCOACH_WEEKLY_INSIGHT_TOOL_SLIM", raising=False)
    else:
        monkeypatch.setenv("SMARTCOACH_WEEKLY_INSIGHT_TOOL_SLIM", env_val)
    assert weekly_insight_tool_slim_default_from_env() is expected


def test_execute_tool_weekly_insight_respects_include_kpi_detail(monkeypatch):
    calls: list[bool] = []

    def fake_get(session, uid, *, slim=False):
        calls.append(slim)
        return {"ok": True, "slim": slim}

    monkeypatch.setenv("SMARTCOACH_WEEKLY_INSIGHT_TOOL_SLIM", "1")
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.agent_tools._increment_tool_call_count",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "src.smartcoach_mobile_coach.agent_tools.get_latest_weekly_insight",
        fake_get,
    )
    session = MagicMock()
    execute_tool(
        session,
        "00000000-0000-0000-0000-000000000001",
        "get_weekly_training_insight",
        "{}",
    )
    assert calls == [True]

    execute_tool(
        session,
        "00000000-0000-0000-0000-000000000001",
        "get_weekly_training_insight",
        '{"include_kpi_detail": true}',
    )
    assert calls == [True, False]

"""Tests for ISO week volume context on run recap fastpath."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from src.smartcoach_mobile_coach.run_recap_fastpath import (
    _compact_run_context_for_llm,
    system_appendix_for_prefetch,
)
from src.smartcoach_mobile_coach.run_recap_week_volume_bundle import (
    build_week_volume_context_for_llm,
    run_recap_week_volume_bundle_enabled,
)


def test_build_week_volume_maps_this_and_last_week(monkeypatch):
    from src.smartcoach_mobile_coach import agent_tools

    def fake_agg(session, uid, *, start_date_from, start_date_to, **kwargs):
        assert start_date_from == date(2026, 4, 6)
        assert start_date_to == date(2026, 4, 19)
        return {
            "run_count": 4,
            "total_mi_display": "20.00 mi",
            "weekly_summaries": [
                {
                    "iso_week": "2026-15",
                    "week_monday": "2026-04-13",
                    "week_label": "Week of 4/13",
                    "run_count": 2,
                    "total_mi_display": "10.50 mi",
                },
                {
                    "iso_week": "2026-14",
                    "week_monday": "2026-04-06",
                    "week_label": "Week of 4/6",
                    "run_count": 1,
                    "total_mi_display": "5.00 mi",
                },
            ],
        }

    monkeypatch.setattr(agent_tools, "tool_aggregate_runs_in_range", fake_agg)

    out = build_week_volume_context_for_llm(MagicMock(), "user-id", "2026-04-16")
    assert out is not None
    assert out["this_week"]["week_monday"] == "2026-04-13"
    assert out["this_week"]["run_count"] == 2
    assert out["this_week"]["total_mi_display"] == "10.50 mi"
    assert out["last_week"]["week_monday"] == "2026-04-06"
    assert out["last_week"]["run_count"] == 1
    assert out["last_week"]["total_mi_display"] == "5.00 mi"


def test_build_week_volume_zeros_when_weeks_missing(monkeypatch):
    from src.smartcoach_mobile_coach import agent_tools

    def fake_agg(session, uid, *, start_date_from, start_date_to, **kwargs):
        return {"run_count": 0, "total_mi_display": "0.00 mi", "weekly_summaries": []}

    monkeypatch.setattr(agent_tools, "tool_aggregate_runs_in_range", fake_agg)

    out = build_week_volume_context_for_llm(MagicMock(), "u", "2026-04-16")
    assert out is not None
    assert out["this_week"]["run_count"] == 0
    assert out["this_week"]["total_mi_display"] == "0.00 mi"
    assert out["last_week"]["run_count"] == 0


def test_build_week_volume_returns_none_on_tool_error(monkeypatch):
    from src.smartcoach_mobile_coach import agent_tools

    monkeypatch.setattr(
        agent_tools,
        "tool_aggregate_runs_in_range",
        lambda *a, **k: {"error": "no_athlete", "message": "x"},
    )
    assert build_week_volume_context_for_llm(MagicMock(), "u", "2026-04-16") is None


def test_compact_includes_week_volume_context():
    prefetch = {
        "activity_id": 1,
        "get_run_summary": {"facts": {"title": "Today"}},
        "comparison_for_llm": [],
        "week_volume_for_llm": {
            "scope": "test scope",
            "anchor_local_date": "2026-04-16",
            "this_week": {
                "week_monday": "2026-04-13",
                "week_label": "W1",
                "run_count": 2,
                "total_mi_display": "10 mi",
            },
            "last_week": {
                "week_monday": "2026-04-06",
                "week_label": "W0",
                "run_count": 1,
                "total_mi_display": "5 mi",
            },
        },
    }
    compact = _compact_run_context_for_llm(prefetch, "2026-04-16")
    assert compact["week_volume_context"]["this_week"]["run_count"] == 2


def test_appendix_mentions_week_volume_when_present():
    prefetch = {
        "activity_id": 1,
        "get_run_summary": {"facts": {"title": "Today"}},
        "comparison_for_llm": [],
        "week_volume_for_llm": {
            "scope": "s",
            "anchor_local_date": "2026-04-16",
            "this_week": {
                "week_monday": "2026-04-13",
                "week_label": "W1",
                "run_count": 2,
                "total_mi_display": "10.00 mi",
            },
            "last_week": {
                "week_monday": "2026-04-06",
                "week_label": "W0",
                "run_count": 1,
                "total_mi_display": "5.00 mi",
            },
        },
    }
    out = system_appendix_for_prefetch(prefetch, "2026-04-16")
    assert "Week volume (`week_volume_context`)" in out


def test_week_volume_bundle_env_off(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_RUN_RECAP_WEEK_VOLUME_BUNDLE", "0")
    assert not run_recap_week_volume_bundle_enabled()

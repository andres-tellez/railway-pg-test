"""Tests for KPI-free comparison bundle on run recap fastpath."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.smartcoach_mobile_coach.run_recap_comparison_bundle import (
    build_comparison_sessions_facts_only,
    run_recap_comparison_bundle_enabled,
)
from src.smartcoach_mobile_coach.run_recap_fastpath import (
    _compact_run_context_for_llm,
)


def test_build_comparison_respects_order_and_kpis_off(monkeypatch):
    from src.smartcoach_mobile_coach import agent_tools

    def fake_find(session, uid, ld):
        if ld == "2026-04-17":
            return {"activity_id": 201}
        if ld == "2026-04-16":
            return {"activity_id": 202}
        return {"no_runs": True}

    def fake_get(
        session,
        uid,
        aid,
        anchor_local_date=None,
        *,
        include_peer_comparison=True,
        include_execution_kpis=True,
        include_hr_profile=True,
    ):
        assert include_peer_comparison is False
        assert include_execution_kpis is False
        assert include_hr_profile is False
        return {
            "facts": {
                "title": f"Run {aid}",
                "local_date": anchor_local_date,
                "distance_display": "5.0 mi",
                "avg_pace_display": "9:00/mi",
                "avg_heart_rate_display": "140 bpm",
            }
        }

    monkeypatch.setattr(agent_tools, "tool_find_runs_by_date", fake_find)
    monkeypatch.setattr(agent_tools, "tool_get_run_summary", fake_get)

    out = build_comparison_sessions_facts_only(
        MagicMock(),
        "user",
        "2026-04-18",
        exclude_activity_id=200,
    )
    assert len(out) == 2
    assert out[0]["calendar_local_date"] == "2026-04-17"
    assert out[0]["activity_id"] == 201
    assert out[1]["calendar_local_date"] == "2026-04-16"
    assert "training_kpis" not in out[0]["facts"]


def test_build_comparison_skips_disambiguation(monkeypatch):
    from src.smartcoach_mobile_coach import agent_tools

    def fake_find(session, uid, ld):
        if ld == "2026-04-17":
            return {"disambiguation_needed": True, "options": []}
        if ld == "2026-04-16":
            return {"activity_id": 302}
        return {"no_runs": True}

    def fake_get(session, uid, aid, anchor_local_date=None, **kwargs):
        return {"facts": {"title": "Solo", "local_date": anchor_local_date}}

    monkeypatch.setattr(agent_tools, "tool_find_runs_by_date", fake_find)
    monkeypatch.setattr(agent_tools, "tool_get_run_summary", fake_get)

    out = build_comparison_sessions_facts_only(
        MagicMock(), "user", "2026-04-18", exclude_activity_id=300
    )
    assert len(out) == 1
    assert out[0]["activity_id"] == 302


def test_build_comparison_excludes_anchor_activity(monkeypatch):
    from src.smartcoach_mobile_coach import agent_tools

    def fake_find(session, uid, ld):
        if ld == "2026-04-17":
            return {"activity_id": 400}
        return {"no_runs": True}

    def fake_get(session, uid, aid, anchor_local_date=None, **kwargs):
        return {"facts": {"title": "X", "local_date": anchor_local_date}}

    monkeypatch.setattr(agent_tools, "tool_find_runs_by_date", fake_find)
    monkeypatch.setattr(agent_tools, "tool_get_run_summary", fake_get)

    out = build_comparison_sessions_facts_only(
        MagicMock(), "user", "2026-04-18", exclude_activity_id=400
    )
    assert out == []


def test_compact_includes_comparison_sessions():
    prefetch = {
        "activity_id": 1,
        "get_run_summary": {"facts": {"title": "Today"}},
        "comparison_for_llm": [
            {
                "calendar_local_date": "2026-04-15",
                "activity_id": 2,
                "facts": {"title": "Prior", "distance_display": "5 mi"},
            }
        ],
    }
    compact = _compact_run_context_for_llm(prefetch, "2026-04-16")
    assert len(compact["comparison_sessions"]) == 1
    assert compact["comparison_sessions"][0]["activity_id"] == 2


def test_comparison_bundle_env_off(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_RUN_RECAP_COMPARISON_BUNDLE", "0")
    assert not run_recap_comparison_bundle_enabled()

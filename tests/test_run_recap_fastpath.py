"""Tests for opening run-recap fast path eligibility."""

from __future__ import annotations

from src.smartcoach_mobile_coach.run_recap_fastpath import (
    _compact_run_context_for_llm,
    wants_run_recap_fastpath,
)
from src.smartcoach_mobile_coach.run_recap_policy import decide_run_recap_fastpath


def test_wants_fastpath_how_was_my_run_opening():
    assert wants_run_recap_fastpath("How was my run?", [])


def test_wants_fastpath_how_did_today_go():
    assert wants_run_recap_fastpath("How did today go?", [])


def test_rejects_last_run():
    assert not wants_run_recap_fastpath("How was my last run?", [])


def test_rejects_when_prior_user_turn_exists():
    hist = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hey — how can I help?"},
    ]
    assert not wants_run_recap_fastpath("How was my run?", hist)
    d = decide_run_recap_fastpath("How was my run?", hist)
    assert d.reason_code == "not_first_user_turn"


def test_allows_assistant_only_preamble_then_first_user_recap():
    """Welcome / coach preamble without a prior user message does not block fastpath."""
    hist = [
        {"role": "assistant", "content": "Hey — I'm here to help with your training."}
    ]
    assert wants_run_recap_fastpath("How was my run?", hist)
    d = decide_run_recap_fastpath("How was my run?", hist)
    assert d.eligible and d.reason_code == "eligible"


def test_contraction_hows_my_run():
    assert wants_run_recap_fastpath("How's my run?", [])


def test_compact_run_context_default_slim_omits_kpis(monkeypatch):
    monkeypatch.delenv("SMARTCOACH_RUN_RECAP_PREFETCH_SLIM", raising=False)
    prefetch = {
        "activity_id": 42,
        "get_run_summary": {
            "facts": {"title": "Morning run", "distance_display": "5.0 mi"},
            "training_kpis": {"hr_drift_pct": 3.2, "hr_drift_band": "green"},
            "is_easy_run": True,
            "zone_bounds": {"z2_low": 120, "z2_high": 140},
            "hr_drift_band_zones": [{"band": "green", "min": 0, "max": 2.5}],
            "comparison": {"peer_runs": [{"x": 1}]},
        },
    }
    compact = _compact_run_context_for_llm(prefetch, "2026-04-14")
    assert compact["activity_id"] == 42
    assert compact["facts"]["title"] == "Morning run"
    assert "training_kpis" not in compact
    assert "comparison" not in compact
    assert "zone_bounds" not in compact
    assert "hr_drift_band_zones" not in compact


def test_compact_run_context_legacy_includes_kpis(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_RUN_RECAP_PREFETCH_SLIM", "0")
    prefetch = {
        "activity_id": 42,
        "get_run_summary": {
            "facts": {"title": "Morning run", "distance_display": "5.0 mi"},
            "training_kpis": {"hr_drift_pct": 3.2, "hr_drift_band": "green"},
            "is_easy_run": True,
            "zone_bounds": {"z2_low": 120, "z2_high": 140},
            "hr_drift_band_zones": [{"band": "green", "min": 0, "max": 2.5}],
            "comparison": {"peer_runs": [{"x": 1}]},
        },
    }
    compact = _compact_run_context_for_llm(prefetch, "2026-04-14")
    assert compact["training_kpis"]["hr_drift_band"] == "green"
    assert "comparison" not in compact


def test_rejects_when_user_asks_drift():
    assert not wants_run_recap_fastpath("How was my run and what was my HR drift?", [])


def test_yesterday_recap_eligible_with_device_anchor():
    """'Yesterday' must not force the slow tool loop when anchor resolves the run day."""
    msg = "How was my run yesterday?"
    anchor = "2026-04-19"
    assert wants_run_recap_fastpath(msg, [], anchor)
    d = decide_run_recap_fastpath(msg, [], anchor)
    assert d.eligible and d.reason_code == "eligible_yesterday"
    assert d.prefetch_local_date == "2026-04-18"


def test_yesterday_without_anchor_not_eligible():
    msg = "How was my run yesterday?"
    assert not wants_run_recap_fastpath(msg, [])
    d = decide_run_recap_fastpath(msg, [])
    assert not d.eligible and d.reason_code == "invalid_anchor_for_yesterday"


def test_disabled_env(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_RUN_RECAP_FASTPATH", "0")
    try:
        assert not wants_run_recap_fastpath("How was my run?", [])
    finally:
        monkeypatch.delenv("SMARTCOACH_RUN_RECAP_FASTPATH", raising=False)

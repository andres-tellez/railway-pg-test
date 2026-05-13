"""Slim fastpath: coach_prose_signals in compact LLM context."""

# pylint: disable=missing-function-docstring

from src.smartcoach_mobile_coach.run_recap_fastpath import (
    _coach_prose_signals_from_summary,
    _compact_run_context_for_llm,
)


def test_coach_prose_signals_from_summary() -> None:
    summary = {
        "is_easy_run": True,
        "training_kpis": {
            "hr_drift_band": "green",
            "z2_band_pct_display": "72% in Z2 band",
            "easy_pct_display": "85% easy",
        },
    }
    sig = _coach_prose_signals_from_summary(summary)
    assert sig["is_easy_run"] is True
    assert sig["hr_drift_band"] == "green"
    assert sig["z2_band_pct_display"] == "72% in Z2 band"
    assert sig["easy_pct_display"] == "85% easy"


def test_compact_includes_signals_when_slim(monkeypatch) -> None:
    monkeypatch.setenv("SMARTCOACH_RUN_RECAP_PREFETCH_SLIM", "1")
    prefetch = {
        "activity_id": 99,
        "get_run_summary": {
            "facts": {"distance_miles": 5.0},
            "is_easy_run": False,
            "training_kpis": {
                "hr_drift_band": "yellow",
                "z2_band_pct_display": "65%",
            },
        },
    }
    compact = _compact_run_context_for_llm(prefetch, "2026-05-06")
    assert compact["coach_prose_signals"]["hr_drift_band"] == "yellow"
    assert compact["coach_prose_signals"]["z2_band_pct_display"] == "65%"
    assert compact["coach_prose_signals"]["is_easy_run"] is False
    assert "facts" in compact


def test_compact_no_coach_signals_when_non_slim(monkeypatch) -> None:
    monkeypatch.setenv("SMARTCOACH_RUN_RECAP_PREFETCH_SLIM", "0")
    prefetch = {
        "activity_id": 1,
        "get_run_summary": {
            "facts": {},
            "training_kpis": {"hr_drift_band": "green"},
            "is_easy_run": True,
        },
    }
    compact = _compact_run_context_for_llm(prefetch, "2026-05-06")
    assert "coach_prose_signals" not in compact
    assert "training_kpis" in compact

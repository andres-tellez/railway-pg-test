"""Run Review envelope: ``run_summary_layout`` survives section enrichment."""

from __future__ import annotations

from src.smartcoach_mobile_coach.run_summary_sections import (
    enrich_run_summary_payload_with_sections,
)


def test_enrich_preserves_run_summary_layout_inline(monkeypatch) -> None:
    monkeypatch.setenv("SMARTCOACH_RUN_SUMMARY_SECTIONS_ENABLED", "1")
    payload = {
        "type": "run_summary",
        "content": "First paragraph.\n\nSecond paragraph.",
        "data": {"facts": {"activity_id": 123}, "training_kpis": {}},
        "run_summary_layout": "inline",
    }
    out, attached = enrich_run_summary_payload_with_sections(payload)
    assert attached is True
    assert out.get("run_summary_layout") == "inline"
    assert out["type"] == "run_summary"


def test_enrich_passes_through_inline_when_sections_disabled(monkeypatch) -> None:
    monkeypatch.setenv("SMARTCOACH_RUN_SUMMARY_SECTIONS_ENABLED", "0")
    payload = {
        "type": "run_summary",
        "content": "Only block.",
        "data": {"facts": {}},
        "run_summary_layout": "inline",
    }
    out, attached = enrich_run_summary_payload_with_sections(payload)
    assert attached is False
    assert out.get("run_summary_layout") == "inline"

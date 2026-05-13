"""Unit tests for ``run_summary_sections`` (Phase 1 payload enrichment)."""

# pylint: disable=missing-function-docstring

from src.smartcoach_mobile_coach.run_summary_sections import (
    enrich_run_summary_payload_with_sections,
    render_coach_turn_sections_to_content,
    split_insight_markdown_into_sections,
)


def test_split_single_paragraph():
    s = split_insight_markdown_into_sections("One block only.")
    assert s is not None
    assert s["interpretation"] == "One block only."
    assert s["grounding"] == []
    assert s["close"] is None


def test_split_interpretation_grounding():
    t = "First thought.\n\nSecond fact line.\n\nThird fact."
    s = split_insight_markdown_into_sections(t)
    assert s["interpretation"] == "First thought."
    assert s["grounding"] == ["Second fact line.", "Third fact."]
    assert s["close"] is None


def test_split_with_close_question():
    t = "Read on the run.\n\nWhat felt hardest today?"
    s = split_insight_markdown_into_sections(t)
    assert s["interpretation"] == "Read on the run."
    assert s["grounding"] == []
    assert s["close"] == "What felt hardest today?"


def test_render_order_matches_join():
    sections = {
        "interpretation": "A",
        "grounding": ["B", "C"],
        "nudge": "D",
        "close": "E?",
    }
    out = render_coach_turn_sections_to_content(sections)
    assert out == "A\n\nB\n\nC\n\nD\n\nE?"


def test_enrich_adds_sections(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_RUN_SUMMARY_SECTIONS_ENABLED", "1")
    payload, ok = enrich_run_summary_payload_with_sections(
        {
            "type": "run_summary",
            "content": "I\n\nII",
            "data": {"x": 1},
        }
    )
    assert ok is True
    assert "sections" in payload
    assert payload["content"] == "I\n\nII"
    assert payload["data"] == {"x": 1}


def test_enrich_respects_disable(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_RUN_SUMMARY_SECTIONS_ENABLED", "0")
    p0 = {"type": "run_summary", "content": "A\n\nB", "data": {}}
    payload, ok = enrich_run_summary_payload_with_sections(p0)
    assert ok is False
    assert "sections" not in payload


def test_enrich_skips_non_run_summary():
    out, ok = enrich_run_summary_payload_with_sections(
        {"type": "text", "content": "hi"}
    )
    assert ok is False
    assert out["type"] == "text"

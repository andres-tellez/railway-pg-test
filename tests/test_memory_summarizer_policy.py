"""Tests for Memory v2 summarizer policy helpers."""

from __future__ import annotations

import json

from src.smartcoach_mobile_coach.memory.policies.summarizer import (
    SummaryDraft,
    collect_tool_names_from_agent_meta,
    sanitize_summary_payload,
    worth_persisting_extracted_plan_memory,
)


def test_sanitize_summary_payload_happy_path() -> None:
    raw = json.dumps(
        {
            "summary_text": " User improved pacing confidence and committed to easier recoveries. ",
            "thread_tags": ["pacing", "confidence"],
            "plan_memories": [
                "I can only run 4 days per week due to work schedule.",
                "Please keep my long run on Saturday mornings.",
            ],
        }
    )
    out = sanitize_summary_payload(raw)
    assert isinstance(out, SummaryDraft)
    assert out.summary_text.startswith("User improved pacing confidence")
    assert out.thread_tags == ("pacing", "confidence")
    assert len(out.plan_memories) == 2


def test_sanitize_summary_payload_rejects_invalid_json() -> None:
    assert sanitize_summary_payload("{not-json") is None


def test_sanitize_summary_payload_clamps_fields() -> None:
    raw = json.dumps(
        {
            "summary_text": "x" * 2600,
            "thread_tags": ["a" * 80, "ok"],
            "plan_memories": [
                "I can only run 3 days per week because of schedule constraints."
            ],
        }
    )
    out = sanitize_summary_payload(raw)
    assert out is not None
    assert len(out.summary_text) <= 2000
    assert out.thread_tags[0].endswith("...")
    assert out.thread_tags[1] == "ok"


def test_worth_persisting_filters_generic_chaff() -> None:
    assert worth_persisting_extracted_plan_memory("thanks for the help") is False
    assert (
        worth_persisting_extracted_plan_memory(
            "I can only run four days per week because of work travel."
        )
        is True
    )


def test_collect_tool_names_unique_ordered() -> None:
    meta = {
        "timings_ms": {
            "agent_loop_rounds": [
                {"tools": [{"name": "get_run_summary"}, {"name": "search_runs"}]},
                {"tools": [{"name": "get_run_summary"}, {"name": "get_user_context"}]},
            ]
        }
    }
    assert collect_tool_names_from_agent_meta(meta) == [
        "get_run_summary",
        "search_runs",
        "get_user_context",
    ]

from __future__ import annotations

import json

from src.smartcoach_mobile_coach.thread_derived_context import (
    derive_thread_coach_context,
)


def test_thread_context_keeps_run_summary_behavior():
    history = [
        {
            "role": "assistant",
            "content": json.dumps(
                {
                    "type": "run_summary",
                    "content": "Nice run.",
                    "data": {"activity_id": 123, "facts": {"title": "Run"}},
                }
            ),
        }
    ]
    out = derive_thread_coach_context(history)
    assert out.prior_run_summary_in_thread is True
    assert out.last_assistant_was_run_summary is True
    assert out.last_structured_run_activity_id == 123


def test_thread_context_extracts_plan_intake_state():
    history = [
        {
            "role": "assistant",
            "content": json.dumps(
                {
                    "type": "text",
                    "content": "Got it.",
                    "data": {
                        "plan_intake_state": {
                            "status": "collecting",
                            "missing_required": ["race_date"],
                        }
                    },
                }
            ),
        }
    ]
    out = derive_thread_coach_context(history)
    assert out.latest_plan_intake_state is not None
    assert out.latest_plan_intake_state["status"] == "collecting"


def test_thread_context_plain_llm_history_drops_plan_intake():
    """
    History passed to the model strips structured assistant JSON to inner ``content`` only.
    Re-deriving thread context from that stripped history must not recover plan_intake_state
    (or the orchestrator would never see prior intake).
    """
    inner = "Please confirm your race details."
    history = [
        {
            "role": "assistant",
            "content": inner,
        }
    ]
    out = derive_thread_coach_context(history)
    assert out.latest_plan_intake_state is None


def test_thread_context_extracts_plan_generation_payload():
    history = [
        {
            "role": "assistant",
            "content": json.dumps(
                {
                    "type": "text",
                    "content": "Plan created.",
                    "data": {"plan_generation": {"plan_id": 77}},
                }
            ),
        }
    ]
    out = derive_thread_coach_context(history)
    assert out.latest_plan_generation_result is not None
    assert out.latest_plan_generation_result["plan_id"] == 77

"""
Minimal plan-creation system prompt must reflect tool-returned intake state.

The agent loop builds the initial system message from thread_ctx, then runs
tools; alignment pause is often computed only in tool output. Refreshing
``messages[0]`` after intake tools keeps ``alignment_pause_coaching_facts_*``
in sync. This module tests the shared builder used for that refresh.
"""

from __future__ import annotations

from src.smartcoach_mobile_coach.dialogue_manager import (
    INTENT_PLAN_CREATION,
    MODE_CLEAR_COACHING,
    TURN_FOLLOW_UP,
    ResponseDirective,
)
from src.smartcoach_mobile_coach.orchestrator import (
    _plan_creation_minimal_system_content,
)
from src.smartcoach_mobile_coach.thread_derived_context import DerivedThreadCoachContext


def _minimal_directive() -> ResponseDirective:
    return ResponseDirective(
        turn_type=TURN_FOLLOW_UP,
        intent=INTENT_PLAN_CREATION,
        target_length="short",
        tone_hint="coach-like",
        focus="plan intake",
        avoid_repeating_metrics=[],
        allow_full_recap=True,
        narration_mode="natural",
        tool_strategy="default",
        natural_style_notes="",
        coaching_depth_requested=False,
        investigate_first=False,
        interaction_mode=MODE_CLEAR_COACHING,
    )


def test_minimal_plan_creation_system_includes_alignment_pause_facts(monkeypatch):
    intake = {
        "status": "collecting",
        "missing_required": [],
        "ready_to_generate": False,
        "draft": {
            "primary_goal": "Target Time",
            "target_time": "3:00:00",
            "training_days": ["Mon", "Tue", "Sun"],
        },
        "alignment": {
            "ambition_stance": "HIGH_TENSION",
            "baseline_band": "THIN",
            "goal_demand": "TIME_TARGET",
            "state": {
                "pause_required": True,
                "generation_ready": False,
                "allowed_question_categories": ["frequency_flexibility"],
            },
        },
    }
    thread_ctx = DerivedThreadCoachContext(
        prior_run_summary_in_thread=False,
        last_assistant_was_run_summary=False,
        last_structured_run_activity_id=None,
        latest_plan_intake_state=intake,
        latest_plan_generation_result=None,
    )
    text = _plan_creation_minimal_system_content(
        plan_intake_ctx=intake,
        anchor_local_date="2026-05-08",
        client_timezone="America/New_York",
        activity_ctx_block="",
        response_directive=_minimal_directive(),
        user_message="ok",
        thread_ctx=thread_ctx,
    )
    assert "## Intake alignment — coach-facing facts" in text
    assert "HIGH_TENSION" in text
    assert "frequency_flexibility" in text

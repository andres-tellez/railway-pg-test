"""Plan-setup intent clarification (accent / ASCII mismatch) before LLM."""

from __future__ import annotations

import json

import pytest

from src.smartcoach_mobile_coach.dialogue_manager import (
    MODE_CLEAR_COACHING,
    ResponseDirective,
    TURN_OPENING,
)
from src.smartcoach_mobile_coach.orchestrator import (
    _fold_approx_ascii_for_intent,
    _is_plan_creation_turn,
    _should_offer_plan_creation_clarification,
)
from src.smartcoach_mobile_coach.thread_derived_context import (
    DerivedThreadCoachContext,
    derive_thread_coach_context,
)


def _directive_general_chat() -> ResponseDirective:
    return ResponseDirective(
        turn_type=TURN_OPENING,
        intent="general_chat",
        target_length="short",
        tone_hint="coach-like",
        focus="chat",
        avoid_repeating_metrics=[],
        allow_full_recap=True,
        narration_mode="natural",
        tool_strategy="default",
        natural_style_notes=[],
        coaching_depth_requested=False,
        investigate_first=False,
        interaction_mode=MODE_CLEAR_COACHING,
    )


def test_fold_approx_ascii_strips_accent_from_create():
    assert _fold_approx_ascii_for_intent("créate").lower() == "create"


def test_should_offer_when_accented_create_misses_strict_classifier(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_INTENT_CLARIFICATION", "1")
    ctx = DerivedThreadCoachContext(
        prior_run_summary_in_thread=False,
        last_assistant_was_run_summary=False,
        last_structured_run_activity_id=None,
        latest_plan_intake_state=None,
        latest_plan_generation_result=None,
    )
    assert _should_offer_plan_creation_clarification(
        user_message="créate a plan",
        thread_ctx=ctx,
        response_directive=_directive_general_chat(),
        has_active_plan=False,
    )


def test_should_not_offer_when_strict_plan_creation_already(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_INTENT_CLARIFICATION", "1")
    ctx = DerivedThreadCoachContext(
        prior_run_summary_in_thread=False,
        last_assistant_was_run_summary=False,
        last_structured_run_activity_id=None,
        latest_plan_intake_state=None,
        latest_plan_generation_result=None,
    )
    rd = ResponseDirective(
        turn_type=TURN_OPENING,
        intent="plan_creation",
        target_length="short",
        tone_hint="coach-like",
        focus="plan intake",
        avoid_repeating_metrics=[],
        allow_full_recap=True,
        narration_mode="natural",
        tool_strategy="default",
        natural_style_notes=[],
        coaching_depth_requested=False,
        investigate_first=False,
        interaction_mode=MODE_CLEAR_COACHING,
    )
    assert not _should_offer_plan_creation_clarification(
        user_message="créate a plan",
        thread_ctx=ctx,
        response_directive=rd,
        has_active_plan=False,
    )


def test_should_not_offer_when_active_plan(monkeypatch):
    monkeypatch.setenv("SMARTCOACH_PLAN_CREATION_INTENT_CLARIFICATION", "1")
    ctx = DerivedThreadCoachContext(
        prior_run_summary_in_thread=False,
        last_assistant_was_run_summary=False,
        last_structured_run_activity_id=None,
        latest_plan_intake_state=None,
        latest_plan_generation_result=None,
    )
    assert not _should_offer_plan_creation_clarification(
        user_message="créate a plan",
        thread_ctx=ctx,
        response_directive=_directive_general_chat(),
        has_active_plan=True,
    )


def test_derive_thread_sets_plan_creation_clarification_pending():
    payload = {
        "type": "text",
        "content": "clarify",
        "data": {"plan_creation_clarification_pending": True},
    }
    history = [{"role": "assistant", "content": json.dumps(payload)}]
    ctx = derive_thread_coach_context(history)
    assert ctx.plan_creation_clarification_pending is True


def test_force_after_clarification_enters_plan_mode_without_message_regex():
    from types import SimpleNamespace

    ctx = SimpleNamespace(
        latest_plan_intake_state=None,
        latest_plan_generation_result=None,
        plan_creation_clarification_pending=False,
    )
    assert _is_plan_creation_turn(
        intent="general_chat",
        user_message="ok",
        thread_ctx=ctx,
        has_active_plan=False,
        force_after_clarification=True,
    )


def test_force_after_clarification_blocked_when_active_plan():
    from types import SimpleNamespace

    ctx = SimpleNamespace(
        latest_plan_intake_state=None,
        latest_plan_generation_result=None,
        plan_creation_clarification_pending=False,
    )
    assert not _is_plan_creation_turn(
        intent="general_chat",
        user_message="yes",
        thread_ctx=ctx,
        has_active_plan=True,
        force_after_clarification=True,
    )

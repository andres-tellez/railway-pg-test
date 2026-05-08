"""
V1.6 hotfix regression tests for plan-creation turn detection.

Background: the previous implementation used substring hints like
``"training plan"`` and ``"plan for"``. Ordinary analysis questions
such as "How was today's run compared to the training plan?" tripped
those hints and forced the user into the intake script ("what race
distance are you aiming for?") even though an active plan already
existed.

The rewritten detector:

* matches broad structured-training intent (explicit plan requests,
  train-for-race statements, race/date/goal shorthand, and "get better"
  training intent),
* short-circuits to False whenever the user already has an active
  plan (unless the thread is *mid-intake* via ``latest_plan_intake_state``),
* keeps honoring ``INTENT_PLAN_CREATION`` from the classifier, but only
  for users who do **not** already have an active plan.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.smartcoach_mobile_coach.orchestrator import (
    _enforce_plan_creation_response_guardrails,
    _is_plan_creation_turn,
    _user_has_active_plan,
    _user_message_matches_plan_creation_regex,
)


# ---------------------------------------------------------------------------
# Regex detector — message-only signal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "msg",
    [
        # The exact bug we shipped for: analysis question that mentions
        # "training plan" without any creation verb.
        "How was today's run compared to the training plan?",
        "Did I hit the training plan this week?",
        "Is the training plan going well?",
        "What's my plan for today?",
        "What's my plan for this week?",
        "What's the plan for tomorrow?",
        "Tell me about my plan",
        "Explain my training plan",
        "Show me the plan overview",
        "What does the training plan say I should do?",
        "I followed the plan yesterday",
        "Yesterday's plan went well",
        "",
        "   ",
    ],
)
def test_regex_detector_does_not_flag_analysis_questions(msg: str) -> None:
    assert (
        _user_message_matches_plan_creation_regex(msg) is False
    ), f"regex false-positive on analysis message: {msg!r}"


@pytest.mark.parametrize(
    "msg",
    [
        "Create a plan for my marathon",
        "Can you build a training plan for me?",
        "Please make a plan for the fall half",
        "Generate a training schedule",
        "Design a plan for a sub-4 marathon",
        "I want to start a plan",
        "Set up a training program for me",
        "Put together a plan for the half",
        "Help me train for a 10k",
        "I want a new training plan",
        "I want a plan",
        "I want a marathon plan",
        "I want a half marathon plan",
        "I want to train for a marathon",
        "I'm training for Chicago Marathon",
        "I'm training for the Boston Marathon",
        "Train for my race in October",
        "Prep for my marathon",
        "Prepare for the Chicago marathon",
        "Draft a plan for me",
        "I need a plan",
        "Chicago Oct 11, 3:30 goal, 5 days per week",
        "Boston Marathon April 20 target 3:30 weekdays",
        "I want to get better",
        "I want to improve",
        "I want to get faster",
        "I want to build consistency",
        "I want to train for Chicago",
    ],
)
def test_regex_detector_matches_explicit_creation_requests(msg: str) -> None:
    assert (
        _user_message_matches_plan_creation_regex(msg) is True
    ), f"regex missed a genuine creation request: {msg!r}"


# ---------------------------------------------------------------------------
# _user_has_active_plan — existence check
# ---------------------------------------------------------------------------


def test_user_has_active_plan_returns_true_when_row_exists() -> None:
    session = MagicMock()
    row = MagicMock()
    session.execute.return_value.first.return_value = row
    assert _user_has_active_plan(session, "user-1") is True


def test_user_has_active_plan_returns_false_when_no_row() -> None:
    session = MagicMock()
    session.execute.return_value.first.return_value = None
    assert _user_has_active_plan(session, "user-1") is False


def test_user_has_active_plan_returns_false_for_empty_user_id() -> None:
    session = MagicMock()
    assert _user_has_active_plan(session, "") is False
    session.execute.assert_not_called()


def test_user_has_active_plan_returns_false_and_rolls_back_on_db_error() -> None:
    session = MagicMock()
    session.execute.side_effect = RuntimeError("relation plans does not exist")
    assert _user_has_active_plan(session, "user-1") is False
    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# _is_plan_creation_turn — integration of regex + active-plan + intent
# ---------------------------------------------------------------------------


def _ctx(latest_plan_intake_state=None):
    return SimpleNamespace(
        prior_run_summary_in_thread=False,
        last_assistant_was_run_summary=False,
        last_structured_run_activity_id=None,
        latest_plan_intake_state=latest_plan_intake_state,
        latest_plan_generation_result=None,
    )


def test_analysis_question_with_active_plan_never_routes_to_intake() -> None:
    """The exact bug we shipped — must no longer happen."""
    result = _is_plan_creation_turn(
        intent="plan_analysis",
        user_message="How was today's run compared to the training plan?",
        thread_ctx=_ctx(),
        has_active_plan=True,
    )
    assert result is False


def test_analysis_question_without_active_plan_also_not_intake() -> None:
    """Regex-only gate must still reject analysis phrasing."""
    result = _is_plan_creation_turn(
        intent="plan_analysis",
        user_message="What's my plan for this week?",
        thread_ctx=_ctx(),
        has_active_plan=False,
    )
    assert result is False


def test_creation_request_with_no_active_plan_routes_to_intake() -> None:
    result = _is_plan_creation_turn(
        intent="plan_analysis",
        user_message="I want a marathon plan",
        thread_ctx=_ctx(),
        has_active_plan=False,
    )
    assert result is True


@pytest.mark.parametrize(
    "msg",
    [
        "I want a marathon plan",
        "I'm training for X race",
        "Chicago Oct 11, 3:30 goal, 5 days per week",
        "I run sometimes and want to get better",
    ],
)
def test_realistic_plan_creation_inputs_route_to_intake(msg: str) -> None:
    result = _is_plan_creation_turn(
        intent="general_chat",
        user_message=msg,
        thread_ctx=_ctx(),
        has_active_plan=False,
    )
    assert result is True


def test_creation_request_with_active_plan_does_not_force_intake() -> None:
    """User already has a live plan — we route through normal coach
    so the LLM can ask "replace your current plan?" instead of
    dropping straight into the intake script.
    """
    result = _is_plan_creation_turn(
        intent="plan_analysis",
        user_message="Build me a new training plan",
        thread_ctx=_ctx(),
        has_active_plan=True,
    )
    assert result is False


def test_classifier_intent_plan_creation_honored_for_no_plan_user() -> None:
    from src.smartcoach_mobile_coach.dialogue_manager import INTENT_PLAN_CREATION

    result = _is_plan_creation_turn(
        intent=INTENT_PLAN_CREATION,
        user_message="sure, let's do it",
        thread_ctx=_ctx(),
        has_active_plan=False,
    )
    assert result is True


def test_analysis_question_vetoes_overeager_classifier_intent() -> None:
    from src.smartcoach_mobile_coach.dialogue_manager import INTENT_PLAN_CREATION

    result = _is_plan_creation_turn(
        intent=INTENT_PLAN_CREATION,
        user_message="How was today's run compared to the training plan?",
        thread_ctx=_ctx(),
        has_active_plan=False,
    )
    assert result is False


def test_classifier_intent_plan_creation_ignored_for_user_with_active_plan() -> None:
    from src.smartcoach_mobile_coach.dialogue_manager import INTENT_PLAN_CREATION

    result = _is_plan_creation_turn(
        intent=INTENT_PLAN_CREATION,
        user_message="how was my run?",
        thread_ctx=_ctx(),
        has_active_plan=True,
    )
    assert result is False


def test_mid_intake_thread_always_wins_even_with_active_plan() -> None:
    """Rule 1 — a thread that already emitted plan_intake_state stays
    in intake so the ongoing flow finishes, even if the user's active
    plan would normally short-circuit detection.
    """
    result = _is_plan_creation_turn(
        intent="plan_analysis",
        user_message="5 days a week",
        thread_ctx=_ctx(latest_plan_intake_state={"training_days": None}),
        has_active_plan=True,
    )
    assert result is True


def test_empty_and_whitespace_messages_do_not_route_to_intake() -> None:
    for msg in ("", "   ", "\n\t"):
        assert (
            _is_plan_creation_turn(
                intent="small_talk",
                user_message=msg,
                thread_ctx=_ctx(),
                has_active_plan=False,
            )
            is False
        )


def test_plan_creation_response_guardrail_strips_filler_and_extra_question() -> None:
    text = (
        "Here’s what I’m seeing from your recent training: you’ve been running around **35 miles per week** with solid consistency. "
        "Your long run is around **13 miles**, which gives us a useful base to build from. "
        "The opportunity is adding structure so that consistency turns into race-specific progress. "
        "Great! I’m here to help you with that. What are you training for? Do you have a specific race in mind?"
    )
    out = _enforce_plan_creation_response_guardrails(text)
    assert "Great" not in out
    assert "here to help" not in out
    assert out.count("?") == 1
    assert "Do you have a specific race in mind" not in out
    assert len([s for s in re.split(r"(?<=[.!?])\s+", out) if s.strip()]) <= 4


def test_plan_creation_response_guardrail_keeps_first_question_only() -> None:
    out = _enforce_plan_creation_response_guardrails(
        "I can help with that. What are you training for? Do you have a race date?"
    )
    assert out == "What are you training for?"


def test_plan_creation_guardrail_replaces_premature_generate_confirm_while_collecting() -> (
    None
):
    """COLLECTING: model must not ask full-plan yes / generate — replace with next question."""
    intake = {
        "ready_to_generate": False,
        "missing_required": ["training_days"],
        "ux": {"training_days_count": 6},
        "draft": {},
    }
    text = "You’re in a solid groove. Does that all look right so we can generate your plan?"
    out = _enforce_plan_creation_response_guardrails(text, plan_intake_state=intake)
    assert "generate" not in out.lower()
    assert "look right" not in out.lower()
    assert "week" in out.lower()


def test_plan_creation_guardrail_does_not_replace_when_ready_to_confirm() -> None:
    intake = {
        "ready_to_generate": True,
        "missing_required": [],
        "confirmation_summary": "Marathon on 2026-10-11",
        "draft": {},
    }
    text = "Here’s the recap. Does that look right?"
    out = _enforce_plan_creation_response_guardrails(text, plan_intake_state=intake)
    assert "look right" in out.lower() or "recap" in out.lower()


def test_plan_creation_guardrail_alignment_pause_keeps_fifth_sentence() -> None:
    """Alignment pause copy may need five sentences (interpret → tension → rationale → question)."""
    intake = {
        "ready_to_generate": False,
        "alignment": {"state": {"pause_required": True, "generation_ready": False}},
        "draft": {},
    }
    text = (
        "Your goal is ambitious versus recent volume. "
        "Three days leaves little cushion. "
        "Adding a day improves durability. "
        "That matters for staying healthy. "
        "Would you be open to adding one run day?"
    )
    out = _enforce_plan_creation_response_guardrails(text, plan_intake_state=intake)
    assert "Would you be open" in out
    assert "cushion" in out.lower()


def test_plan_creation_guardrail_collecting_caps_at_four_sentences() -> None:
    intake = {
        "ready_to_generate": False,
        "missing_required": ["training_days"],
        "draft": {},
    }
    text = "First. Second. Third. Fourth. Fifth."
    out = _enforce_plan_creation_response_guardrails(text, plan_intake_state=intake)
    assert "Fifth" not in out
    assert len([s for s in out.split("\n") if s.strip()]) == 4


def test_plan_creation_guardrail_strips_numbered_list_artifacts() -> None:
    out = _enforce_plan_creation_response_guardrails(
        "1. Would you be open to adding one run day?\n2. These will help me align the plan."
    )
    assert "1." not in out
    assert "2." not in out
    assert "Would you be open to adding one run day?" in out

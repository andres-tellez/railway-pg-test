"""
V1.6 hotfix regression tests for plan-creation turn detection.

Background: the previous implementation used substring hints like
``"training plan"`` and ``"plan for"``. Ordinary analysis questions
such as "How was today's run compared to the training plan?" tripped
those hints and forced the user into the intake script ("what race
distance are you aiming for?") even though an active plan already
existed.

The rewritten detector:

* matches only verb-anchored creation phrases (create / build / make /
  generate / design / start / set up / draft / help me train /
  train for …),
* short-circuits to False whenever the user already has an active
  plan (unless the thread is *mid-intake* via ``latest_plan_intake_state``),
* keeps honoring ``INTENT_PLAN_CREATION`` from the classifier, but only
  for users who do **not** already have an active plan.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.smartcoach_mobile_coach.orchestrator import (
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
        "I want to train for a marathon",
        "Train for my race in October",
        "Prep for my marathon",
        "Prepare for the Chicago marathon",
        "Draft a plan for me",
        "I need a plan",
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
        user_message="Build me a training plan for the half",
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

"""
V1.6 Phase B 3B.13 — orchestrator opening-turn ``get_user_context`` nudge.

The nudge is a **prompt hint**, not a hard rule: we verify the section is
emitted when ``turn_type == "opening"`` outside plan-creation mode, and
suppressed in every other scenario. End-to-end prompt composition is
covered lightly — we don't round-trip through OpenAI here; the V1.6
contract is that the section lands in the system prompt when expected.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.smartcoach_mobile_coach.dialogue_manager import (
    MODE_CLEAR_COACHING,
    TURN_ACKNOWLEDGMENT,
    TURN_DRILL_DOWN,
    TURN_FOLLOW_UP,
    TURN_OPENING,
    ResponseDirective,
)
from src.smartcoach_mobile_coach.orchestrator import (
    _user_context_opening_nudge_section,
)


def _directive(turn_type: str, intent: str = "run_analysis") -> ResponseDirective:
    """Build a minimal ResponseDirective — only ``turn_type`` is exercised by the nudge."""
    return ResponseDirective(
        turn_type=turn_type,
        intent=intent,
        target_length="short",
        tone_hint="coach-like",
        focus="ground in user context",
        avoid_repeating_metrics=[],
        allow_full_recap=True,
        narration_mode="natural",
        tool_strategy="default",
        natural_style_notes="",
        coaching_depth_requested=False,
        investigate_first=False,
        interaction_mode=MODE_CLEAR_COACHING,
    )


# ---------------------------------------------------------------------------
# Emit / suppress
# ---------------------------------------------------------------------------


def test_nudge_is_emitted_on_opening_turn_outside_plan_creation():
    out = _user_context_opening_nudge_section(
        _directive(TURN_OPENING), plan_creation_mode=False
    )
    assert out, "opening turn must emit the nudge section"
    assert "get_user_context" in out
    assert "turn_type = opening" in out


def test_nudge_is_empty_on_non_opening_turns():
    for turn in (TURN_FOLLOW_UP, TURN_DRILL_DOWN, TURN_ACKNOWLEDGMENT):
        out = _user_context_opening_nudge_section(
            _directive(turn), plan_creation_mode=False
        )
        assert out == "", f"turn_type={turn} must not emit the nudge"


def test_nudge_is_suppressed_in_plan_creation_mode():
    out = _user_context_opening_nudge_section(
        _directive(TURN_OPENING), plan_creation_mode=True
    )
    assert out == "", "plan-creation mode has its own stub; nudge must not fire"


# ---------------------------------------------------------------------------
# Content contract (spec wording we rely on downstream)
# ---------------------------------------------------------------------------


def test_nudge_mentions_small_payload_and_caching():
    """Tells the model the call is cheap — so it actually takes the hint."""
    out = _user_context_opening_nudge_section(
        _directive(TURN_OPENING), plan_creation_mode=False
    )
    assert "<2 KB" in out
    assert "cached" in out.lower()


def test_nudge_carves_out_fact_lookup_openings():
    """The nudge must NOT read as 'always call' — narrow fact asks should skip."""
    out = _user_context_opening_nudge_section(
        _directive(TURN_OPENING), plan_creation_mode=False
    )
    assert "Skip it" in out or "skip" in out.lower()
    assert "get_run_summary" in out


def test_nudge_forbids_redundant_followup_calls():
    out = _user_context_opening_nudge_section(
        _directive(TURN_OPENING), plan_creation_mode=False
    )
    # Explicit "don't re-call on follow-up/drill-down" guidance.
    assert "re-call" in out.lower() or "follow-up" in out.lower()


# ---------------------------------------------------------------------------
# Integration: nudge lands in the composed system prompt on opening turns
# ---------------------------------------------------------------------------


def test_nudge_ordering_relative_to_intent_priority_override():
    """
    When both sections fire (opening turn + race_projection intent) both
    are joined into the final system prompt. We don't dictate the order
    beyond "they coexist" — this test just locks that neither eats the
    other.
    """
    from src.smartcoach_mobile_coach.orchestrator import (
        _intent_priority_override_section,
        _join_nonempty_system_sections,
    )

    intent_section = _intent_priority_override_section("race_projection")
    nudge_section = _user_context_opening_nudge_section(
        _directive(TURN_OPENING, intent="race_projection"),
        plan_creation_mode=False,
    )
    composed = _join_nonempty_system_sections(intent_section, nudge_section)
    assert "race_projection" in composed
    assert "get_user_context" in composed

"""
V1.6 Phase D 3D.4 — deterministic coaching-hint resolver tests.

Locks :func:`src.services.plan.phase_coach_hints.resolve_coaching_hint`
against its contract so the trigger for
``coaching_hint = propose_goal`` vs ``merge_retrospective_and_propose``
vs ``None`` never drifts:

* No hint when an active goal exists (coach does not auto-refine).
* No hint for empty / future phases (nothing to coach toward yet).
* ``merge_retrospective_and_propose`` when the phase is *current*,
  has zero completed weeks, and has no active goal.
* ``propose_goal`` for every other past/current + no-goal combination.
* Graceful ``None`` on malformed payload shapes.

These tests are pure-function tests — no DB, no fixtures. Integration
with :func:`build_phase_analysis_payload` is covered separately in
``test_get_phase_analysis_tool.py`` (payload field presence + per-phase
correctness).
"""

from __future__ import annotations

import pytest

from src.services.plan.phase_coach_hints import (
    CoachingHint,
    resolve_coaching_hint,
)


# ---------------------------------------------------------------------------
# Enum stability
# ---------------------------------------------------------------------------


def test_enum_values_are_stable_wire_strings() -> None:
    # The LLM matches on the literal string, so any rename is a wire
    # break. Assert the two canonical values explicitly.
    assert CoachingHint.PROPOSE_GOAL.value == "propose_goal"
    assert (
        CoachingHint.MERGE_RETROSPECTIVE_AND_PROPOSE.value
        == "merge_retrospective_and_propose"
    )


def test_enum_is_str_subclass_for_direct_json_emission() -> None:
    # str-subclass Enum is required so json.dumps emits the literal
    # value rather than a repr — that way payload shape stays flat for
    # the LLM. ``==`` on the value should match the raw wire string.
    assert isinstance(CoachingHint.PROPOSE_GOAL, str)
    assert CoachingHint.PROPOSE_GOAL == "propose_goal"
    assert CoachingHint.MERGE_RETROSPECTIVE_AND_PROPOSE == (
        "merge_retrospective_and_propose"
    )


# ---------------------------------------------------------------------------
# Already-goaled phases → no hint
# ---------------------------------------------------------------------------


def test_active_goal_present_suppresses_any_hint() -> None:
    goal = {"goal_text": "Stay mostly in Zone 2 on long runs."}
    pw = {"phase_temporality": "current", "completed": 0}
    assert resolve_coaching_hint(goal, pw) is None


def test_goal_present_even_on_past_phase_suppresses_hint() -> None:
    goal = {"goal_text": "Lock in Tempo execution."}
    pw = {"phase_temporality": "past", "completed": 4}
    assert resolve_coaching_hint(goal, pw) is None


def test_empty_goal_text_is_treated_as_no_goal() -> None:
    # Corrupt row — goal dict is present but goal_text is empty.
    # Resolver fails open toward proposing rather than silencing.
    goal = {"goal_text": ""}
    pw = {"phase_temporality": "current", "completed": 2}
    assert resolve_coaching_hint(goal, pw) == "propose_goal"


# ---------------------------------------------------------------------------
# Empty / future phases → no hint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("temporality", ["empty", "future"])
def test_empty_or_future_phase_returns_none(temporality: str) -> None:
    pw = {"phase_temporality": temporality, "completed": 0}
    assert resolve_coaching_hint(None, pw) is None


def test_missing_temporality_returns_none() -> None:
    assert resolve_coaching_hint(None, {"completed": 0}) is None


# ---------------------------------------------------------------------------
# merge_retrospective_and_propose — the "just transitioned" signal
# ---------------------------------------------------------------------------


def test_current_phase_with_zero_completed_and_no_goal_merges() -> None:
    pw = {"phase_temporality": "current", "completed": 0}
    assert resolve_coaching_hint(None, pw) == "merge_retrospective_and_propose"


def test_current_phase_with_one_completed_week_drops_to_propose_goal() -> None:
    # As soon as the first week of a new phase is past its Sunday, the
    # merge-retrospective window closes (user-locked single-shot rule).
    pw = {"phase_temporality": "current", "completed": 1}
    assert resolve_coaching_hint(None, pw) == "propose_goal"


# ---------------------------------------------------------------------------
# propose_goal — mid-phase / catch-up without a goal
# ---------------------------------------------------------------------------


def test_past_phase_no_goal_returns_propose_goal() -> None:
    # A fully-past phase without a goal is unusual but should still
    # prompt the coach to capture a (late) Focus — useful for
    # retrospective summaries that reference what the athlete was
    # working on.
    pw = {"phase_temporality": "past", "completed": 6}
    assert resolve_coaching_hint(None, pw) == "propose_goal"


def test_current_phase_mid_flight_no_goal_returns_propose_goal() -> None:
    pw = {"phase_temporality": "current", "completed": 3}
    assert resolve_coaching_hint(None, pw) == "propose_goal"


# ---------------------------------------------------------------------------
# Malformed payload shapes → graceful None
# ---------------------------------------------------------------------------


def test_phase_weeks_not_a_dict_returns_none() -> None:
    assert resolve_coaching_hint(None, None) is None
    assert resolve_coaching_hint(None, "current") is None
    assert resolve_coaching_hint(None, []) is None


def test_completed_not_an_int_returns_none() -> None:
    # "completed": None (deliberate missing signal) or a string should
    # never accidentally emit a hint.
    pw_none = {"phase_temporality": "current", "completed": None}
    pw_str = {"phase_temporality": "current", "completed": "0"}
    assert resolve_coaching_hint(None, pw_none) is None
    assert resolve_coaching_hint(None, pw_str) is None


def test_unknown_temporality_string_returns_none() -> None:
    # Defensive: an unknown value should never spuriously trigger a
    # hint.
    pw = {"phase_temporality": "transitioning", "completed": 0}
    assert resolve_coaching_hint(None, pw) is None


# ---------------------------------------------------------------------------
# Goal shape tolerance
# ---------------------------------------------------------------------------


def test_goal_as_non_dict_is_treated_as_no_goal() -> None:
    # The payload serializer always emits dict-or-None for `goal`, but
    # a stray non-dict should not silently block the hint.
    pw = {"phase_temporality": "current", "completed": 0}
    assert (
        resolve_coaching_hint("not-a-dict", pw)  # type: ignore[arg-type]
        == "merge_retrospective_and_propose"
    )
    assert (
        resolve_coaching_hint(["something"], pw)  # type: ignore[arg-type]
        == "merge_retrospective_and_propose"
    )

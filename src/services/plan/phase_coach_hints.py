"""
Deterministic coaching-hint producer for the Phase UX flow
(V1.6 Phase D 3D.4).

Single source of truth
----------------------
PHASE_3_IMPLEMENTATION_CHECKLIST §X.5 — this module is the ONLY place
that decides *whether the coach should auto-propose a phase goal* and
*whether to merge a retrospective* on the current turn. Both
:mod:`src.services.plan.phase_analysis` (payload field ``coaching_hint``)
and future conversation-level hooks MUST call the resolver here; they
must not re-derive the rule from ``goal`` + ``phase_weeks`` on their own.

Why a deterministic hint?
-------------------------
The 3D.8 prompt contract already tells the coach *what* to do when
``goal is null`` (propose one) and *what* to do at a phase transition
(merge the retrospective with the new-goal proposal). What it does NOT
do is pin the trigger to specific deterministic inputs — left to its
own pattern-matching, an LLM will sometimes propose a goal mid-phase
for a user who already has one, or split retrospective + proposal
across two turns. Keying the trigger off a single ``coaching_hint``
field forces the coach to read one value and match it to one rule,
which is the same discipline §19.9 enforces for
``deviation_direction`` / ``plan_status`` / ``phase_kpi_priority``.

Hint values (wire-stable enum, see :class:`CoachingHint`)
---------------------------------------------------------
* ``None`` — no action implied. The coach stays inside the normal
  Purpose → Focus → Progress → Action template (3D.8) without a
  writer step.
* ``"propose_goal"`` — the active phase has started (or is fully past)
  and has no active goal. The coach proposes one in this turn and
  saves it via :func:`save_phase_goal`. No retrospective required —
  this is the mid-phase / first-plan-turn auto-proposal path.
* ``"merge_retrospective_and_propose"`` — the active phase is *current*
  and has **zero** completed weeks (i.e. it has just begun) and has
  no active goal. The coach MUST merge a short retrospective of the
  prior phase into the same turn and follow it with a new-phase goal
  proposal (single coach response, user-locked 2026-04-21). The
  retrospective is read from a separate ``get_phase_analysis`` call
  for the prior phase — the hint does not carry the prior phase's
  data; it only signals that the merged response shape applies.

Field coverage guarantee (§X.5 composition rule)
------------------------------------------------
The resolver reads ONLY the fields that
:func:`src.services.plan.phase_analysis.build_phase_analysis_payload`
already emits:

* ``goal`` — ``None`` when no active goal exists (3D.3).
* ``phase_weeks.phase_temporality`` — ``"empty" | "future" | "current"
  | "past"`` (3B.6).
* ``phase_weeks.completed`` — integer count of phase-weeks whose
  Sunday has passed (3B.6).
* ``phase_weeks.total`` — integer count of phase-weeks overall
  (3B.6).

So the resolver is a pure function of the phase-analysis payload — it
never re-queries the DB and never re-derives adherence / priority KPIs
/ weekly status. That keeps it safe to call from HTTP, tool, and
background paths without worrying about transaction scope.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


class CoachingHint(str, Enum):
    """Wire-stable enum for the ``coaching_hint`` payload field.

    String-backed so the LLM sees a plain JSON string and can match on
    the literal value without any enum awareness. ``.value`` is the
    canonical form emitted on the wire.
    """

    PROPOSE_GOAL = "propose_goal"
    MERGE_RETROSPECTIVE_AND_PROPOSE = "merge_retrospective_and_propose"


# Canonical temporality values — mirror
# :func:`src.services.plan.phase_analysis._classify_phase_temporality`.
# Pulled out as constants so typos in either caller or consumer are
# caught by tests, not at runtime on a live coach turn.
_TEMPORALITY_EMPTY = "empty"
_TEMPORALITY_FUTURE = "future"
_TEMPORALITY_CURRENT = "current"
_TEMPORALITY_PAST = "past"


def resolve_coaching_hint(
    goal: Optional[Dict[str, Any]],
    phase_weeks: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Return the canonical ``coaching_hint`` string (or ``None``).

    Args:
        goal: The ``goal`` sub-payload from
            :func:`build_phase_analysis_payload` — either a dict with
            ``goal_text`` / ``status`` / … keys, or ``None`` when no
            active goal exists for ``(user, plan, phase)``.
        phase_weeks: The ``phase_weeks`` sub-payload. Required keys:
            ``phase_temporality`` (str) and ``completed`` (int). Any
            other shape returns ``None`` — the resolver fails safe so
            a partial payload never triggers an unwanted auto-proposal.

    Returns:
        * ``"merge_retrospective_and_propose"`` when the active phase
          is *current*, has zero completed weeks, and has no active
          goal. This is the phase-transition signal.
        * ``"propose_goal"`` when the active phase is *current* (with
          at least one completed week) or fully *past*, and has no
          active goal. This is the mid-phase / catch-up auto-proposal
          signal.
        * ``None`` otherwise — including when a goal is already set,
          when the phase is empty / all future, or when the payload
          shape is unreadable.

    Design contract
    ---------------
    * The resolver never emits a hint for an *already-goaled* phase.
      Refinement of an existing goal is a user-initiated path
      (``save_phase_goal`` with a new ``goal_text``); the coach does
      not auto-propose a replacement.
    * The resolver never emits a hint for an ``"empty"`` or
      ``"future"`` phase. There is nothing to coach toward yet; the
      Purpose step of 3D.8 carries the narrative instead.
    * The ``merge_retrospective_and_propose`` branch is deliberately
      strict on ``completed == 0``. As soon as the first week of a
      phase is past its Sunday, the opportunity to frame the turn as
      a transition is gone — subsequent proposals are ``propose_goal``
      instead. This matches the user-locked "first plan/phase/progress
      turn" rule (2026-04-21) and keeps the signal single-shot per
      phase.
    """
    # Already-goaled → no hint. We only check presence + truthiness of
    # ``goal_text``; a serialized row missing a text is treated as
    # "no goal" so a corrupt row does not silently suppress the
    # proposal (fail-open on the safer side).
    if isinstance(goal, dict) and goal.get("goal_text"):
        return None

    if not isinstance(phase_weeks, dict):
        return None

    temporality = phase_weeks.get("phase_temporality")
    completed = phase_weeks.get("completed")

    if temporality in (_TEMPORALITY_EMPTY, _TEMPORALITY_FUTURE, None):
        return None

    if not isinstance(completed, int):
        return None

    if temporality == _TEMPORALITY_CURRENT and completed == 0:
        return CoachingHint.MERGE_RETROSPECTIVE_AND_PROPOSE.value

    if temporality in (_TEMPORALITY_CURRENT, _TEMPORALITY_PAST):
        return CoachingHint.PROPOSE_GOAL.value

    return None


__all__ = [
    "CoachingHint",
    "resolve_coaching_hint",
]

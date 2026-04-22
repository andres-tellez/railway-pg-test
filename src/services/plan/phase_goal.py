"""
Canonical writer + reader for V1.6 Phase D user_phase_goals rows.

PHASE_3_IMPLEMENTATION_CHECKLIST 3D.2 single-source-of-truth: this
module is the ONLY place in the codebase that mutates the
``user_phase_goals`` table (and one of two read surfaces — the
``get_phase_analysis`` payload extension being the other, in 3D.3/3D.7).
All coach tools, HTTP routes, and future Phase E adaptation hooks MUST
call the helpers below — never hand-roll INSERT/UPDATE against the
table, never re-derive the supersede-then-insert pattern, and never
mirror the active-goal selection rule on mobile.

Soft-semantics contract (user-locked 2026-04-21)
------------------------------------------------
Phase D goals live under an explicit **no hard consent gate** rule
(see :mod:`src.db.models.user_phase_goals` module docstring). The
writer therefore:

* **Never blocks on a missing explicit confirmation.** ``confirmed_at``
  stays ``None`` unless the caller passes an explicit timestamp (e.g.
  when the user says "yes keep that as my focus"). The coach can set
  a goal on a soft agreement ("that sounds right") without a two-step
  dialog.
* **Always does a supersede-then-insert.** Updating an existing goal
  for the same (user, plan, phase) leaves the old row in place with
  ``status='superseded'`` and inserts a fresh ``active`` row. No
  destructive edit, no row count churn, no partial-index requirement
  for cross-DB portability.
* **Caps text length defensively.** 280 chars — behavior-and-outcome
  goals are sentences, not paragraphs. Violations return
  ``invalid_goal_text`` so the tool layer can render a nudge.

The reader side exposes ``get_active_phase_goal`` + ``get_all_goals_for_plan``
so :mod:`phase_analysis` (3D.3/3D.7) and the coach prompt contract
(3D.8) can compose payloads without poking at the ORM directly.

Error envelope convention
-------------------------
Every write path returns a ``(status, payload)`` tuple:

    status  ∈ { "ok", "invalid_phase", "invalid_goal_text",
               "invalid_source", "no_plan", "no_active_plan" }
    payload is a dict with "goal" (the new ``active`` row serialized)
            on ``"ok"``, or ``{"error": status, "message": ...}``
            otherwise.

This keeps the tool layer free of phase/text validation and lets
future non-tool callers (e.g. a future mobile endpoint) reuse the
same validation without re-implementing it.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.db.models.plans import Plan
from src.db.models.user_phase_goals import (
    GOAL_SOURCE_AUTO_PROPOSED,
    GOAL_SOURCE_VALUES,
    GOAL_STATUS_ACTIVE,
    GOAL_STATUS_SUPERSEDED,
    UserPhaseGoal,
)
from src.services.phase.phase_priority import Phase


logger = logging.getLogger(__name__)


# Behavior-and-outcome goals are short sentences. 280 chars covers the
# longest fluent phrasing we've seen in design review ("Stay in control
# of your easy days so the quality sessions still feel strong" ≈ 70
# chars) with a comfortable ceiling for Spanish / Portuguese / German
# expansion without risking unbounded LLM outputs.
MAX_GOAL_TEXT_LENGTH: int = 280


# --------------------------------------------------------------------- #
# Validators
# --------------------------------------------------------------------- #


def _normalize_phase(raw: Any) -> Optional[Phase]:
    """Case-insensitive normalization to the canonical ``Phase`` enum.

    Returns ``None`` on unknown / non-string input so callers can emit
    a consistent ``invalid_phase`` envelope with the allowed list.
    """
    if not isinstance(raw, str):
        return None
    candidate = raw.strip().capitalize()
    try:
        return Phase(candidate)
    except ValueError:
        return None


def _normalize_source(raw: Any) -> Optional[str]:
    """Accept only the three locked provenance strings.

    Defaults (callers pass ``None``) are applied at the call site, not
    here — the validator's job is to reject explicit bad values.
    """
    if raw is None:
        return None
    if isinstance(raw, str) and raw in GOAL_SOURCE_VALUES:
        return raw
    return ""


def _validate_goal_text(raw: Any) -> Optional[str]:
    """Return the trimmed goal text, or ``None`` if invalid / empty."""
    if not isinstance(raw, str):
        return None
    stripped = raw.strip()
    if not stripped:
        return None
    if len(stripped) > MAX_GOAL_TEXT_LENGTH:
        return None
    return stripped


# --------------------------------------------------------------------- #
# Plan lookup
# --------------------------------------------------------------------- #


def _load_active_plan(session: Session, user_id: UUID) -> Optional[Plan]:
    """Return the user's active ``Plan`` or ``None``.

    Parity with other plan-aware services (``weekly_plan``,
    ``phase_analysis``) — one active plan per user is the V1.6
    invariant. Callers that need "most recent" semantics should use
    the existing helpers in those services; the writer here only
    speaks to the **currently active** plan.
    """
    return (
        session.query(Plan)
        .filter(Plan.user_id == user_id, Plan.is_active.is_(True))
        .order_by(desc(Plan.created_at))
        .first()
    )


# --------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------- #


def _serialize_goal(goal: UserPhaseGoal) -> Dict[str, Any]:
    """Wire-shape for a single goal row.

    Kept explicit (not ``__dict__``) so future column additions do not
    leak into the LLM payload without review, and so timezone handling
    for ``created_at`` / ``confirmed_at`` is uniform across reader and
    writer return shapes.
    """
    return {
        "id": goal.id,
        "plan_id": goal.plan_id,
        "phase": goal.phase,
        "goal_text": goal.goal_text,
        "status": goal.status,
        "source": goal.source,
        "confirmed_at": goal.confirmed_at.isoformat() if goal.confirmed_at else None,
        "created_at": goal.created_at.isoformat() if goal.created_at else None,
    }


# --------------------------------------------------------------------- #
# Readers
# --------------------------------------------------------------------- #


def get_active_phase_goal(
    session: Session,
    user_id: UUID,
    plan_id: int,
    phase: Phase,
) -> Optional[UserPhaseGoal]:
    """Return the single ``active`` goal for (user, plan, phase), if any.

    The lookup respects the supersede-then-insert invariant — in a
    consistent database there is at most one ``active`` row per
    (user, plan, phase). If two are ever present (writer bug) the
    most-recently-created wins, matching "intent-of-most-recent-edit".
    """
    return (
        session.query(UserPhaseGoal)
        .filter(
            UserPhaseGoal.user_id == user_id,
            UserPhaseGoal.plan_id == plan_id,
            UserPhaseGoal.phase == phase.value,
            UserPhaseGoal.status == GOAL_STATUS_ACTIVE,
        )
        .order_by(desc(UserPhaseGoal.created_at))
        .first()
    )


def get_all_goals_for_plan(
    session: Session,
    user_id: UUID,
    plan_id: int,
) -> List[UserPhaseGoal]:
    """Return every goal row for a (user, plan), newest first.

    Useful for the 3D.3/3D.7 phase-analysis payload extension — the
    caller can fold by ``phase`` to surface "current focus" + recent
    supersede history without a second query.
    """
    return (
        session.query(UserPhaseGoal)
        .filter(
            UserPhaseGoal.user_id == user_id,
            UserPhaseGoal.plan_id == plan_id,
        )
        .order_by(desc(UserPhaseGoal.created_at))
        .all()
    )


# --------------------------------------------------------------------- #
# Writer — supersede-then-insert
# --------------------------------------------------------------------- #


def save_phase_goal(
    session: Session,
    user_id: UUID,
    phase_raw: Any,
    goal_text_raw: Any,
    *,
    source_raw: Any = None,
    confirmed: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    """Canonical writer — validate, supersede prior, insert new row.

    Args:
        session: Active SQLAlchemy session. The writer does NOT commit
            — commit semantics are owned by the tool layer (so batched
            tool calls share one transaction) or by the test fixture.
        user_id: Internal UUID. Callers that have only a string should
            convert upstream; exposing the UUID type here prevents
            silent cross-user writes on a typoed cast.
        phase_raw: Raw user-facing phase string (validated via
            :func:`_normalize_phase`). Case-insensitive.
        goal_text_raw: Raw user-facing goal text (trimmed, validated
            for length 1–280).
        source_raw: Optional provenance string. Defaults to
            :data:`GOAL_SOURCE_AUTO_PROPOSED` when ``None``. Explicit
            bad values return ``invalid_source``.
        confirmed: When ``True``, stamps ``confirmed_at = now``. When
            ``False`` (the default — soft-semantics path), leaves
            ``confirmed_at`` ``None``. The coach usually passes
            ``False`` for auto-proposed goals and ``True`` once the
            user has explicitly agreed.

    Returns:
        ``("ok", {"goal": <serialized>, "superseded_goal_id": <id|None>})``
        on success, or a standard error envelope tuple.
    """
    phase = _normalize_phase(phase_raw)
    if phase is None:
        return (
            "invalid_phase",
            {
                "error": "invalid_phase",
                "message": (
                    f"phase must be one of {[p.value for p in Phase]} "
                    "(case-insensitive)."
                ),
            },
        )

    goal_text = _validate_goal_text(goal_text_raw)
    if goal_text is None:
        return (
            "invalid_goal_text",
            {
                "error": "invalid_goal_text",
                "message": (
                    f"goal_text is required and must be 1–{MAX_GOAL_TEXT_LENGTH} "
                    "characters after trimming."
                ),
            },
        )

    normalized_source = _normalize_source(source_raw)
    if normalized_source == "":
        # Distinguish "bad string" from "omitted" (returns None above).
        return (
            "invalid_source",
            {
                "error": "invalid_source",
                "message": (
                    f"source must be one of {list(GOAL_SOURCE_VALUES)} "
                    "or omitted (defaults to auto_proposed)."
                ),
            },
        )
    final_source = normalized_source or GOAL_SOURCE_AUTO_PROPOSED

    plan = _load_active_plan(session, user_id)
    if plan is None:
        return (
            "no_active_plan",
            {
                "error": "no_active_plan",
                "message": (
                    "No active plan on file for this user. Generate a plan "
                    "before setting a phase focus."
                ),
            },
        )

    # Supersede the current active goal (if any) for this phase.
    existing = get_active_phase_goal(session, user_id, plan.id, phase)
    superseded_id: Optional[int] = None
    if existing is not None:
        existing.status = GOAL_STATUS_SUPERSEDED
        superseded_id = existing.id

    confirmed_at = None
    if confirmed:
        # Imported lazily so tests can monkey-patch ``datetime.utcnow``
        # only when they need to — the writer otherwise carries no
        # module-level clock dependency.
        from datetime import datetime

        confirmed_at = datetime.utcnow()

    new_goal = UserPhaseGoal(
        user_id=user_id,
        plan_id=plan.id,
        phase=phase.value,
        goal_text=goal_text,
        status=GOAL_STATUS_ACTIVE,
        source=final_source,
        confirmed_at=confirmed_at,
    )
    session.add(new_goal)
    session.flush()  # populate id + server-default timestamps

    logger.info(
        "[phase_goal] saved user=%s plan=%s phase=%s source=%s superseded=%s",
        user_id,
        plan.id,
        phase.value,
        final_source,
        superseded_id,
    )

    return (
        "ok",
        {
            "goal": _serialize_goal(new_goal),
            "superseded_goal_id": superseded_id,
        },
    )


__all__ = [
    "MAX_GOAL_TEXT_LENGTH",
    "get_active_phase_goal",
    "get_all_goals_for_plan",
    "save_phase_goal",
]

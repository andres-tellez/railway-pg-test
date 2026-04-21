"""
Canonical producer for V1.6 §6 ``plan_status`` enum.

PHASE_3_IMPLEMENTATION_CHECKLIST §X.5 single-source-of-truth: this
module is the ONLY place in the codebase that derives ``plan_status``.
All coach payloads, tools, and routes that need the value MUST call
``plan_status_for_activity(...)`` or ``plan_status_for_day(...)`` —
never reimplement the derivation, never mirror it on mobile, never
let the LLM derive it (V1.6 §19: LLM must not override or contradict
``plan_status``).

Spec reference
--------------
SMARTCOACH_SYSTEM_SPEC_V1.md §6 "plan_status Enum":

    planned_only  — Workout is planned; day is in the future.
    in_progress   — Workout is planned; day is today; no activity yet.
    executed      — Workout planned AND a matching activity was
                    recorded (via ``matched_plan_workout_id``).
    missed        — Workout planned, the day has passed, no matching
                    activity exists.
    unplanned     — An activity exists on a day with no planned workout
                    (e.g. rest day or gap day).

Storage/derivation policy
-------------------------
``plan_status`` is **derived on read**, not persisted. It is trivially
computable from ``activity.matched_plan_workout_id`` and the
``(day_date, today)`` tuple, so a persisted column would introduce
invalidation complexity (today moves every day; the status of every
planned-only / in-progress / missed day flips without any write).
Future revisits to this decision (e.g. if a historical "was this
status X on date Y?" query arises) should be tracked as a separate
spec change.

Pairing semantics
-----------------
The spec phrases ``plan_status`` as a per-pairing value: one planned
workout + zero-or-one activity. This module exposes two specialized
entry points because in practice callers either hold an ``Activity``
row (per-activity view; LLM ``get_run_summary``) or a planned-workout
row (per-day view; ``GET /api/plan/current-week``) but rarely both:

    plan_status_for_activity(matched_plan_workout_id)
        — Binary: EXECUTED when linked, UNPLANNED otherwise.
          Suitable for per-activity surfaces; the activity's date/
          today context is not required.

    plan_status_for_day(*, has_planned_workout, has_matching_activity,
                         day_date, today)
        — Full five-value derivation. ``None`` when the day has
          neither a planned workout nor an activity (empty rest /
          gap day; the spec does not enumerate a status for that
          case).

Note on ``unplanned`` from the day perspective
----------------------------------------------
When a planned workout exists on day X AND an activity exists on
day X but the activity's ``matched_plan_workout_id`` points to a
different workout (or is ``None``), the plan-side pairing is
``missed`` (or ``planned_only`` / ``in_progress``), and the activity-
side pairing is ``unplanned``. Callers computing the day view pass
``has_matching_activity=False`` in that case and the day surfaces as
``missed``; the unlinked activity is surfaced separately (e.g. as a
second day entry in Phase B ``get_weekly_plan``).
``GET /api/plan/current-week`` only iterates planned workouts today
and therefore does not emit the ``unplanned`` day-state; full
surfacing is tracked as Phase B work.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional


class PlanStatus(str, Enum):
    """V1.6 §6 enum values. ``str`` base makes JSON serialization trivial."""

    PLANNED_ONLY = "planned_only"
    IN_PROGRESS = "in_progress"
    EXECUTED = "executed"
    MISSED = "missed"
    UNPLANNED = "unplanned"


def plan_status_for_activity(
    matched_plan_workout_id: Optional[int],
) -> PlanStatus:
    """
    Per-activity pairing: ``EXECUTED`` iff the activity is linked to a
    planned workout, else ``UNPLANNED``.

    Called by the canonical ``build_run_execution_block(act)`` so the
    LLM ``get_run_summary`` tool and any Phase B plan-aware tool get
    ``plan_status`` without re-reading the activity row.
    """
    if matched_plan_workout_id is not None:
        return PlanStatus.EXECUTED
    return PlanStatus.UNPLANNED


def plan_status_for_day(
    *,
    has_planned_workout: bool,
    has_matching_activity: bool,
    day_date: date,
    today: date,
) -> Optional[PlanStatus]:
    """
    Per-plan-day pairing. Returns one of the five V1.6 §6 enum values,
    or ``None`` for a day with neither a planned workout nor an
    activity (empty rest / gap day; the spec does not define a status
    for that case).

    Args:
        has_planned_workout: ``True`` iff a ``PlanWorkout`` row exists
            for the user on ``day_date``.
        has_matching_activity: ``True`` iff an ``Activity`` row exists
            whose ``matched_plan_workout_id`` points to this day's
            planned workout. Callers MUST NOT set this to ``True`` for
            activities on the same day that are unlinked — those are
            handled as ``unplanned`` from the activity's own view.
        day_date: the plan-day date in the user's local timezone.
        today: "today" in the user's local timezone (from
            ``src.utils.date_helpers.get_today_date_in_timezone``). Do
            not pass a server-local date; temporal semantics drift.

    Invariant: a day with a planned workout always yields a non-``None``
    status, regardless of ``today`` position.
    """
    if has_planned_workout and has_matching_activity:
        return PlanStatus.EXECUTED
    if has_planned_workout:
        if day_date > today:
            return PlanStatus.PLANNED_ONLY
        if day_date == today:
            return PlanStatus.IN_PROGRESS
        return PlanStatus.MISSED
    if has_matching_activity:
        # No planned workout but an activity exists → unplanned.
        # Current ``/api/plan/current-week`` does not reach this branch
        # because its day list is driven by planned workouts only;
        # Phase B ``get_weekly_plan`` will surface these day entries.
        return PlanStatus.UNPLANNED
    return None

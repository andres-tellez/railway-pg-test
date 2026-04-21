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
from typing import Optional, Sequence


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


def derive_violated_rest_day(
    *,
    plan_status_value: PlanStatus,
    day_weekday: int,
    plan_training_days: Optional[Sequence[str]] = None,
) -> bool:
    """
    Canonical producer for V1.6 §6 ``violated_rest_day`` derived flag.

    PHASE_3_IMPLEMENTATION_CHECKLIST §X.5 single-source-of-truth:
    colocated with ``plan_status`` derivation as called for in the
    checklist ("Same module as plan_status — colocated derivation").
    The LLM (V1.6 §19) must NOT derive this from heuristics.

    Spec (SMARTCOACH_SYSTEM_SPEC_V1.md §6)::

        violated_rest_day = true  iff  plan_status == UNPLANNED
                                       AND  the day was a planned
                                            rest day
        violated_rest_day = false  otherwise

    Rest-day modeling in this codebase
    ----------------------------------
    A rest day is **implicit**: ``PlanWorkout`` rows are created only
    for training days. The user's training days are stored as an array
    of day-name strings (``["Mon", "Wed", "Thu", "Sat"]`` etc.) on
    ``plans.training_days``. Any weekday not in that list is a planned
    rest day.

    Args:
        plan_status_value: the already-derived ``PlanStatus`` for the
            pairing. Required so we can short-circuit without touching
            training_days for non-UNPLANNED cases.
        day_weekday: ``date.weekday()`` for the day in question (0 =
            Monday, 6 = Sunday). Callers should use the activity's
            local-timezone date when possible; see TZ caveat below.
        plan_training_days: ``plan.training_days`` value (nullable; the
            column is ``Optional``). Accepts both full ("Monday") and
            abbreviated ("Mon") day-name formats — normalized via
            ``src.utils.date_helpers.DAY_TO_WEEKDAY``.

    Returns:
        ``True`` only when ``plan_status_value == UNPLANNED`` and the
        day is not among the training days.

        ``False`` when:
        * ``plan_status_value`` is anything other than ``UNPLANNED``
          (every such case has a planned workout by definition → not a
          rest day).
        * ``plan_training_days`` is ``None`` / empty. Per the spec the
          flag is a boolean, and "false otherwise" covers the
          can't-prove case. This is a safe default: coach §19 applies
          *stronger* emphasis when the flag is true; defaulting to
          false prevents erroneous escalation when the plan metadata
          is incomplete.

    TZ caveat (tracked for V1.7)
    ----------------------------
    ``day_weekday`` is computed by callers from ``activity.start_date``
    (a UTC timestamp). For most users the UTC day matches the local
    day, but activities that straddle midnight relative to the user's
    local timezone may drift by one weekday. Proper resolution
    requires a stored local date on activities; out of scope for V1.6.
    """
    if plan_status_value != PlanStatus.UNPLANNED:
        return False
    if not plan_training_days:
        return False
    # Imported lazily to avoid a module-level dependency on date_helpers
    # just for the normalization table (which is the only thing we
    # need, and only for the unplanned branch).
    from src.utils.date_helpers import DAY_TO_WEEKDAY

    training_weekdays = {DAY_TO_WEEKDAY.get(d) for d in plan_training_days}
    training_weekdays.discard(None)
    return day_weekday not in training_weekdays

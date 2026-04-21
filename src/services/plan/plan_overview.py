"""
Canonical builder for the V1.6 §6 **plan overview** payload.

Single source of truth (PHASE_3_IMPLEMENTATION_CHECKLIST §X.5) for the
LLM agent tool ``get_plan_overview`` (V1.6 Phase B 3B.5, AGENTIC_COACH
Topic 9).

Scope
-----
An end-to-end, **planned-only** summary of the athlete's active (or most
recently created) training plan:

* Plan metadata — ``plan_id``, ``plan_name``, ``race_date``,
  ``race_distance``.
* ``phase_blocks`` — one entry per contiguous phase block in the plan
  (Base / Build / Peak / Taper). Each block carries its week span,
  workout count, planned mileage, and the canonical
  ``phase_kpi_priority`` ordered emphasis list.
* ``volume_curve`` — one entry per Monday-to-Sunday plan week, with
  planned run count and planned mileage total. The coach uses this to
  narrate progression, deload weeks, and peak mileage.
* ``long_run_progression`` — one entry per plan week exposing the
  longest planned run (date, miles, and canonical run-type key). The
  coach uses this to narrate long-run ramp-up and taper.

Future-week rule (§19.5) — extended to the full plan
----------------------------------------------------
``get_plan_overview`` is purely plan-side. No ``Activity`` row is ever
read. This makes the §19.5 future-week contract ("no ``actual.*``, no
derived metrics, no predicted outcomes") structurally impossible to
violate for **any** week the overview touches, not only future ones.
The ``volume_curve`` entries therefore describe what the plan says; the
coach must use ``get_weekly_plan`` (3B.2) if it needs actuals for a
past/current week.

Derivation policy
-----------------
Every deterministic field is derived from the canonical producers:

* Phase resolution for a week's day span — delegated to
  :func:`src.services.phase.phase_priority.resolve_week_phase`
  (§7 majority-of-days / plurality rule with later-phase tie-break).
* ``phase_kpi_priority`` for each phase block — delegated to
  :func:`src.services.phase.phase_priority.phase_kpi_priority_for_phase`
  (§8 ordered emphasis table).
* Canonical run-type identification for the long-run selector —
  delegated to :mod:`src.utils.run_type_constants`.
* Week bounds — delegated to
  :func:`src.utils.date_helpers.get_week_bounds_for_date` so plan-week
  boundaries agree byte-exact with :mod:`weekly_plan`.

This module owns only the **composition** — grouping workouts into
weeks, grouping consecutive same-phase weeks into phase blocks, and
picking the long run per week.

Long-run selection policy
-------------------------
A week's "long run" is resolved as:

1. If any planned workout in the week has canonical ``run_type_key ==
   "long"``, the longest-miles such workout wins.
2. Otherwise, the single longest-miles planned workout of the week
   wins (Base weeks can have no explicit long; the coach still needs
   a "largest session" anchor for progression narrative).
3. If the week has no planned workouts, ``long_run_date`` /
   ``long_run_miles`` / ``long_run_type`` are ``None``.

This policy is deterministic and idempotent across plan rebuilds.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.smartcoach_mobile_coach.display_format import format_distance_mi
from src.services.phase.phase_priority import (
    phase_kpi_priority_for_phase,
    resolve_week_phase,
)
from src.services.plan.weekly_plan import resolve_plan_workout_run_type_key
from src.utils.date_helpers import (
    WeekTemporality,
    classify_week_temporality,
    get_week_bounds_for_date,
)
from src.utils.run_type_constants import RUN_TYPE_LONG
from src.utils.timezone_helpers import get_today_date_in_timezone

logger = logging.getLogger(__name__)


def _load_active_or_most_recent_plan(session: Session, user_id: UUID):
    """
    Return the plan row the overview renders against, or ``None``.

    Mirrors :func:`src.services.plan.weekly_plan._load_active_or_most_recent_plan`
    exactly — both surfaces must agree on "which plan is this?".
    Duplicated here (rather than imported) to avoid coupling the two
    service modules' private helpers; the duplication is intentional
    and tested for behavioural parity (§X.5 note below).
    """
    plan_row = (
        session.query(
            Plan.id,
            Plan.plan_name,
            Plan.race_date,
            Plan.race_distance,
        )
        .filter(Plan.user_id == user_id, Plan.is_active.is_(True))
        .order_by(Plan.created_at.desc())
        .first()
    )
    if plan_row is not None:
        return plan_row
    return (
        session.query(
            Plan.id,
            Plan.plan_name,
            Plan.race_date,
            Plan.race_distance,
        )
        .filter(Plan.user_id == user_id)
        .order_by(Plan.created_at.desc())
        .first()
    )


def _select_long_run(
    workouts_in_week: List[PlanWorkout],
) -> Optional[Dict[str, Any]]:
    """
    Pick the week's long-run anchor from its planned workouts.

    See module docstring for the selection policy.
    """
    if not workouts_in_week:
        return None

    long_candidates: List[PlanWorkout] = []
    for w in workouts_in_week:
        if resolve_plan_workout_run_type_key(w) == RUN_TYPE_LONG:
            long_candidates.append(w)

    source = long_candidates if long_candidates else list(workouts_in_week)
    winner = max(source, key=lambda w: (w.miles or 0.0))
    return {
        "long_run_date": winner.date.isoformat(),
        "long_run_miles": (float(winner.miles) if winner.miles is not None else None),
        "long_run_type": resolve_plan_workout_run_type_key(winner),
    }


def _build_volume_curve_entry(
    week_index: int,
    week_start: date,
    week_end: date,
    workouts: List[PlanWorkout],
    today: date,
) -> Dict[str, Any]:
    """
    Volume-curve row for a single plan week.

    Fields are all planned-side. The ``week_temporality`` is surfaced
    at the row level so the coach can reason about progression vs.
    historical context without re-deriving from ``today``.
    """
    phase_labels = [w.phase for w in workouts]
    resolved = resolve_week_phase(phase_labels)
    planned_runs = len(workouts)
    planned_miles_total = sum((w.miles or 0.0) for w in workouts)
    temporality = classify_week_temporality(week_start, today=today)

    return {
        "week_index": week_index,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "phase": resolved.value if resolved is not None else None,
        "planned_runs": planned_runs,
        "planned_miles_total": planned_miles_total,
        "week_temporality": temporality.value,
        # V1.6 3B.7 — Topic 4 display-ready string for the weekly
        # volume number. Coach can cite ``display.planned_miles_total``
        # directly instead of rounding the float on the fly.
        "display": {
            "planned_miles_total": format_distance_mi(planned_miles_total),
        },
    }


def _group_phase_blocks(
    volume_curve: List[Dict[str, Any]],
    per_week_workouts: List[List[PlanWorkout]],
) -> List[Dict[str, Any]]:
    """
    Group consecutive same-phase weeks into phase blocks.

    A "block" is a run of consecutive plan weeks that resolve to the
    same phase (via :func:`resolve_week_phase`). Transition weeks
    therefore belong to whichever phase won the majority; that matches
    the coach's week-level emphasis and keeps the block boundaries
    consistent with ``get_weekly_plan``'s per-week ``phase_kpi_priority``.

    Each block emits the canonical §8 ``phase_kpi_priority`` ordered
    emphasis list for its phase so the coach does not need to re-derive
    it per week when narrating the plan arc.
    """
    blocks: List[Dict[str, Any]] = []
    if not volume_curve:
        return blocks

    current_phase: Optional[str] = None
    start_week: int = 0
    num_weeks: int = 0
    num_runs: int = 0
    total_miles: float = 0.0

    def _finalize(end_week: int) -> None:
        if current_phase is None or num_weeks == 0:
            return
        try:
            from src.services.phase.phase_priority import Phase

            phase_enum = Phase(current_phase)
            priority = [
                {"kpi_id": e.kpi_id, "label": e.label}
                for e in phase_kpi_priority_for_phase(phase_enum)
            ]
        except ValueError:
            priority = []
        blocks.append(
            {
                "phase": current_phase,
                "start_week": start_week,
                "end_week": end_week,
                "num_weeks": num_weeks,
                "num_runs": num_runs,
                "total_miles": total_miles,
                "phase_kpi_priority": priority,
                # V1.6 3B.7 — display string for the phase's total volume.
                "display": {
                    "total_miles": format_distance_mi(total_miles),
                },
            }
        )

    for row, workouts in zip(volume_curve, per_week_workouts):
        phase = row["phase"]
        if phase is None:
            # A week with no canonical-phase evidence breaks the run;
            # emit the prior block (if any) and start a None gap. The
            # None gap itself is NOT surfaced as a phase block because
            # the coach cannot emphasize a phase it can't identify.
            if current_phase is not None:
                _finalize(row["week_index"] - 1)
                current_phase = None
                num_weeks = 0
                num_runs = 0
                total_miles = 0.0
            continue

        if phase != current_phase:
            _finalize(row["week_index"] - 1)
            current_phase = phase
            start_week = row["week_index"]
            num_weeks = 0
            num_runs = 0
            total_miles = 0.0

        num_weeks += 1
        num_runs += len(workouts)
        total_miles += sum((w.miles or 0.0) for w in workouts)

    if current_phase is not None:
        _finalize(volume_curve[-1]["week_index"])

    return blocks


def build_plan_overview_payload(
    session: Session,
    user_id: UUID,
    *,
    tz: str = "UTC",
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Build the V1.6 Phase B 3B.5 plan overview payload.

    Args:
        session: Active SQLAlchemy session.
        user_id: Internal user UUID (not Auth0 subject).
        tz: IANA timezone name used to resolve "today" for the
            ``week_temporality`` field on each volume-curve row.
            Defaults to UTC.
        today: Optional explicit "today" override (tests). Overrides
            ``tz`` when provided.

    Returns:
        Either an error envelope

            ``{"error": "no_plan", "message": "No plan found"}``

        or the full payload. The payload is **planned-only** — no
        activity join runs, so no ``actual.*`` field can appear
        regardless of caller behaviour.

    The error branch never raises — callers (HTTP route, LLM tool)
    translate it to their own error shape.
    """
    if not isinstance(tz, str) or not tz.strip():
        tz_norm = "UTC"
    else:
        tz_norm = tz.strip()

    resolved_today: date = (
        today if today is not None else get_today_date_in_timezone(tz_norm)
    )

    plan_row = _load_active_or_most_recent_plan(session, user_id)
    if plan_row is None:
        return {"error": "no_plan", "message": "No plan found"}

    workouts: List[PlanWorkout] = (
        session.query(PlanWorkout)
        .filter(PlanWorkout.plan_id == plan_row.id)
        .order_by(PlanWorkout.date)
        .all()
    )

    if not workouts:
        return {
            "plan_id": plan_row.id,
            "plan_name": plan_row.plan_name,
            "race_date": (
                plan_row.race_date.isoformat() if plan_row.race_date else None
            ),
            "race_distance": plan_row.race_distance,
            "timezone": tz_norm,
            "today": resolved_today.isoformat(),
            "plan_start": None,
            "plan_end": None,
            "total_weeks": 0,
            "total_planned_runs": 0,
            "total_planned_miles": 0.0,
            "display": {
                "total_planned_miles": format_distance_mi(0.0),
            },
            "phase_blocks": [],
            "volume_curve": [],
            "long_run_progression": [],
        }

    # Group workouts by their Monday anchor. A single pass is enough
    # because the query already returned them in date-ascending order.
    by_monday: Dict[date, List[PlanWorkout]] = {}
    for w in workouts:
        monday, _sunday = get_week_bounds_for_date(w.date)
        by_monday.setdefault(monday, []).append(w)

    first_monday = min(by_monday.keys())
    last_monday = max(by_monday.keys())
    last_sunday = last_monday + timedelta(days=6)

    # Walk the plan week-by-week from first_monday..last_monday so
    # the volume curve has a row for every week even if a given week
    # has zero workouts (rare but possible — deload at end of block).
    volume_curve: List[Dict[str, Any]] = []
    long_run_progression: List[Dict[str, Any]] = []
    per_week_workouts: List[List[PlanWorkout]] = []

    cursor = first_monday
    week_index = 0
    while cursor <= last_monday:
        week_index += 1
        week_end = cursor + timedelta(days=6)
        this_week = by_monday.get(cursor, [])
        per_week_workouts.append(this_week)

        volume_curve.append(
            _build_volume_curve_entry(
                week_index=week_index,
                week_start=cursor,
                week_end=week_end,
                workouts=this_week,
                today=resolved_today,
            )
        )

        long_run_row = _select_long_run(this_week) or {
            "long_run_date": None,
            "long_run_miles": None,
            "long_run_type": None,
        }
        long_run_progression.append(
            {
                "week_index": week_index,
                "week_start": cursor.isoformat(),
                **long_run_row,
                # V1.6 3B.7 — display string for the long-run mileage.
                "display": {
                    "long_run_miles": (
                        format_distance_mi(long_run_row["long_run_miles"])
                        if long_run_row["long_run_miles"] is not None
                        else None
                    ),
                },
            }
        )

        cursor = cursor + timedelta(days=7)

    phase_blocks = _group_phase_blocks(volume_curve, per_week_workouts)

    total_planned_runs = sum(len(ws) for ws in per_week_workouts)
    total_planned_miles = sum((w.miles or 0.0) for w in workouts)

    return {
        "plan_id": plan_row.id,
        "plan_name": plan_row.plan_name,
        "race_date": (plan_row.race_date.isoformat() if plan_row.race_date else None),
        "race_distance": plan_row.race_distance,
        "timezone": tz_norm,
        "today": resolved_today.isoformat(),
        "plan_start": first_monday.isoformat(),
        "plan_end": last_sunday.isoformat(),
        "total_weeks": week_index,
        "total_planned_runs": total_planned_runs,
        "total_planned_miles": total_planned_miles,
        "display": {
            "total_planned_miles": format_distance_mi(total_planned_miles),
        },
        "phase_blocks": phase_blocks,
        "volume_curve": volume_curve,
        "long_run_progression": long_run_progression,
    }


__all__ = [
    "build_plan_overview_payload",
]

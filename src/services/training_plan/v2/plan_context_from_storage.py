"""
Materialize :class:`~src.services.training_plan.v2.plan_context.PlanContext`
from the athlete's saved plan (``plans`` + ``plan_workouts``).

Used when the V2 generation pipeline is not running — e.g. coach tool
``explain_current_plan`` — so :func:`~src.services.training_plan.v2.plan_insights.build_plan_insights`
and :mod:`~src.services.training_plan.v2.plan_coach` see the same week-level
shape they expect from ``detailed_plan.weeks`` (``week_number``,
``weekly_mileage``, ``long_run_miles``, optional ``phase``).

Week grouping and long-run selection mirror
:func:`src.services.plan.plan_overview.build_plan_overview_payload` (§X.5).
When ``plans.context_snapshot`` is present (saved at generation time), validation,
spine quality, decision trace, and metadata are rehydrated from it; otherwise the
same read-only defaults as before apply.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.services.phase.phase_priority import resolve_week_phase
from src.services.plan.plan_overview import (
    _load_active_or_most_recent_plan,
    _select_long_run,
)
from src.services.training_plan.v2.plan_context import PlanContext
from src.utils.date_helpers import get_week_bounds_for_date


def build_plan_context_from_active_plan(
    session: Session,
    user_id: UUID,
) -> Optional[PlanContext]:
    """
    Return a :class:`PlanContext` for the active (or most recent) plan, or
    ``None`` if no plan row exists.

    Without ``plans.context_snapshot``, ``validation`` defaults to
    ``{"valid": True, "issues": []}`` and ``spine_quality_issues`` to ``[]``.
    """
    plan_row = _load_active_or_most_recent_plan(session, user_id)
    if plan_row is None:
        return None

    snapshot = (
        session.query(Plan.context_snapshot).filter(Plan.id == plan_row.id).scalar()
    )

    workouts: List[PlanWorkout] = (
        session.query(PlanWorkout)
        .filter(PlanWorkout.plan_id == plan_row.id)
        .order_by(PlanWorkout.date)
        .all()
    )

    weeks_payload: List[Dict[str, Any]] = []
    meta = {
        "plan_id": plan_row.id,
        "plan_name": plan_row.plan_name,
        "race_date": (plan_row.race_date.isoformat() if plan_row.race_date else None),
        "race_distance": plan_row.race_distance,
    }

    if not workouts:
        ctx = PlanContext()
        ctx.detailed_plan = {"weeks": []}
        if snapshot is not None and isinstance(snapshot, dict):
            ctx.validation = snapshot.get("validation")
            ctx.spine_quality_issues = snapshot.get("spine_quality_issues")
            ctx.decision_trace = snapshot.get("decision_trace")
            ctx.metadata = snapshot.get("metadata")
            if ctx.metadata is None:
                ctx.metadata = meta
        else:
            ctx.validation = {"valid": True, "issues": []}
            ctx.spine_quality_issues = []
            ctx.metadata = meta
        return ctx

    by_monday: Dict[date, List[PlanWorkout]] = {}
    for w in workouts:
        monday, _sunday = get_week_bounds_for_date(w.date)
        by_monday.setdefault(monday, []).append(w)

    first_monday = min(by_monday.keys())
    last_monday = max(by_monday.keys())

    cursor = first_monday
    week_index = 0
    while cursor <= last_monday:
        week_index += 1
        this_week = by_monday.get(cursor, [])
        weekly_total = sum((w.miles or 0.0) for w in this_week)
        phase_labels = [w.phase for w in this_week]
        resolved = resolve_week_phase(phase_labels)
        phase_str = resolved.value if resolved is not None else None

        long_run_row = _select_long_run(this_week) or {}
        lr_miles = long_run_row.get("long_run_miles")

        weeks_payload.append(
            {
                "week_number": week_index,
                "weekly_mileage": weekly_total,
                "long_run_miles": lr_miles,
                "phase": phase_str,
            }
        )
        cursor = cursor + timedelta(days=7)

    ctx = PlanContext()
    ctx.detailed_plan = {"weeks": weeks_payload}
    if snapshot is not None and isinstance(snapshot, dict):
        ctx.validation = snapshot.get("validation")
        ctx.spine_quality_issues = snapshot.get("spine_quality_issues")
        ctx.decision_trace = snapshot.get("decision_trace")
        ctx.metadata = snapshot.get("metadata")
        if ctx.metadata is None:
            ctx.metadata = meta
    else:
        ctx.validation = {"valid": True, "issues": []}
        ctx.spine_quality_issues = []
        ctx.metadata = meta
    return ctx


__all__ = ["build_plan_context_from_active_plan"]

"""
Canonical builder for the V1.6 §6 weekly-plan payload.

Single source of truth (PHASE_3_IMPLEMENTATION_CHECKLIST §X.5) for:

1. The HTTP route ``GET /api/plan/current-week``
   (:mod:`src.routes.plan_routes`).
2. The LLM agent tool ``get_weekly_plan(week_start_iso)``
   (:mod:`src.smartcoach_mobile_coach.agent_tools`; V1.6 Phase B 3B.2).

Both consumers call :func:`build_weekly_plan_payload` and emit its output
verbatim (minus HTTP envelope concerns). The tool is just "the route
without Flask" — which keeps the LLM view and the mobile view byte-exact
identical, so the coach and the app can never disagree on what the
week looks like.

Spec references (SMARTCOACH_SYSTEM_SPEC_V1.md)
-----------------------------------------------
§6 "Plan vs Actual — Namespace Isolation"
    Per-day entries use canonical ``planned.*`` / ``actual.*`` namespaces.
    ``actual.*`` may only appear when a matching activity exists. For
    future weeks, ``actual.*`` is never emitted (see §19.5). The
    pairing-level controllers ``plan_status``, ``violated_rest_day``,
    and ``deviation_direction`` live at the top of each day entry.

§7 "Adherence (Separate from Performance)"
    Weekly aggregate ``adherence_runs_pct`` is produced by
    :func:`src.services.scoring.adherence.compute_weekly_adherence` and
    emitted for PAST / CURRENT weeks only. Future weeks have no runs
    to aggregate, so the ``adherence`` block is ``None``.

§8 "Phase KPI Priority (Deterministic V1.6)"
    Weekly ``phase_kpi_priority`` is produced by
    :func:`src.services.phase.phase_priority.compute_phase_kpi_priority_for_week`
    for all temporalities — a future week's emphasis is a statement
    about the planned phase, not about any execution, so it is valid
    to emit for FUTURE as well as PAST / CURRENT.

§19.5 "Future-Week Rules (LLM Contract)"
    The LLM must not predict outcomes, invent actuals, or describe
    a future week in past tense. This module enforces the PAYLOAD side
    of that contract — it is structurally impossible for the tool to
    return an ``actual`` field on a future week because the activity
    join is skipped entirely. The prompt-side enforcement lives in
    Phase C 3C.4.

Future-week contract (3B.3 — deterministic enforcement)
-------------------------------------------------------
The builder distinguishes the three temporalities via
:func:`src.utils.date_helpers.classify_week_temporality`:

* **PAST / CURRENT** — full shape: plan + matched activities +
  ``plan_status`` per-day + ``adherence`` block + ``phase_kpi_priority``.
* **FUTURE** — plan-only shape:
  - No activity query runs (performance + correctness guarantee).
  - Each day's ``execution`` field is always ``None``.
  - Each day's ``plan_status`` is always ``"planned_only"`` (§6 enum).
  - Each day's ``violated_rest_day`` is always ``False`` (rest days
    in the future are not "violated" — there is no activity yet).
  - Top-level ``adherence`` block is ``None`` (nothing to aggregate).
  - Top-level ``phase_kpi_priority`` is still emitted because it
    describes planned emphasis, not execution.

Derivation policy
-----------------
All deterministic fields are derived on read from the canonical
producers. This module never re-implements:

* ``plan_status`` — delegated to
  :func:`src.services.plan.plan_status.plan_status_for_day`.
* ``violated_rest_day`` — folded into the per-activity execution
  block by :func:`src.smartcoach_mobile_coach.run_insight.build_run_execution_block`.
* ``deviation_direction`` — idem, inside ``actual.*``.
* ``adherence_runs_pct`` — delegated to
  :func:`src.services.scoring.adherence.compute_weekly_adherence`.
* ``phase_kpi_priority`` — delegated to
  :func:`src.services.phase.phase_priority.compute_phase_kpi_priority_for_week`.

The only thing this module owns is the **composition** (assembling
the canonical pieces into the wire payload) and the **future-week
gate** (skipping the activity join and setting the static fields).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.db.models.activities import Activity
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.services.phase.phase_priority import compute_phase_kpi_priority_for_week
from src.services.plan.plan_status import plan_status_for_day
from src.services.scoring.adherence import (
    WeeklyAdherenceEntry,
    compute_weekly_adherence,
)
from src.smartcoach_mobile_coach.run_insight import (
    build_run_execution_block,
    execution_block_to_weekly_plan_shape,
)
from src.utils.date_helpers import (
    WeekTemporality,
    classify_week_temporality,
    get_week_bounds_for_date,
)
from src.utils.run_type_constants import (
    RUN_TYPE_DEFINITIONS,
    RUN_TYPE_EASY,
    normalize_run_type_key,
)
from src.utils.timezone_helpers import get_today_date_in_timezone

logger = logging.getLogger(__name__)

_WEEKDAY_LABELS: Tuple[str, ...] = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _resolve_run_type_key(w: PlanWorkout) -> str:
    """
    Canonical run_type_key for a PlanWorkout row.

    Duplicates the intent of
    ``plan_routes._resolve_run_type_key_for_workout`` because the
    route-side helper is module-private. Once Phase B stabilizes,
    that helper should be deleted and its single call site should
    import from here (§X.5 cleanup tracked separately).

    Resolution order:

    1. Stored ``w.run_type_key`` normalized through the canonical map
       (:mod:`src.utils.run_type_constants`).
    2. Fallback: normalize ``w.workout_type`` (legacy rows that
       predate ``run_type_key`` persistence).
    3. Final fallback: ``RUN_TYPE_EASY``.
    """
    return (
        normalize_run_type_key(getattr(w, "run_type_key", None))
        or normalize_run_type_key(getattr(w, "workout_type", None))
        or RUN_TYPE_EASY
    )


def _load_active_or_most_recent_plan(session: Session, user_id: UUID):
    """
    Return the plan metadata row we render against, or ``None``.

    Prefers the active plan; falls back to the most-recently-created
    plan so a user who completed a plan but has no new active plan
    can still see their most recent training week. Mirrors the
    behaviour of the HTTP route.
    """
    plan_row = (
        session.query(
            Plan.id,
            Plan.plan_name,
            Plan.race_date,
            Plan.race_distance,
            Plan.training_days,
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
            Plan.training_days,
        )
        .filter(Plan.user_id == user_id)
        .order_by(Plan.created_at.desc())
        .first()
    )


def _load_matched_activities_by_pw_id(
    session: Session,
    user_id: UUID,
    plan_workout_ids: List[int],
) -> Dict[int, Activity]:
    """
    Return ``{plan_workout_id: Activity}`` for the most recent activity
    matching each plan workout.

    Only the most recent activity per ``matched_plan_workout_id`` wins;
    historical duplicate matches (re-sync, re-upload) are ignored. This
    matches the current HTTP route behaviour.
    """
    if not plan_workout_ids:
        return {}

    acts = (
        session.query(Activity)
        .filter(
            Activity.matched_plan_workout_id.in_(plan_workout_ids),
            Activity.user_id == user_id,
        )
        .order_by(desc(Activity.start_date))
        .all()
    )
    by_pw: Dict[int, Activity] = {}
    for a in acts:
        mpw = a.matched_plan_workout_id
        if mpw is not None and mpw not in by_pw:
            by_pw[mpw] = a
    return by_pw


def _build_future_week_day_entry(
    w: PlanWorkout,
    canonical_run_type_key: str,
    target_hr: Optional[Any],
) -> Dict[str, Any]:
    """
    Per-day entry for a FUTURE week (§19.5 / 3B.3).

    No ``execution`` block, ``plan_status="planned_only"``, and
    ``violated_rest_day=False``. The ``actual.*`` namespace is
    structurally absent because the activity query was skipped.
    """
    rt_def = (
        RUN_TYPE_DEFINITIONS.get(canonical_run_type_key)
        or RUN_TYPE_DEFINITIONS[RUN_TYPE_EASY]
    )
    return {
        "date": w.date.isoformat(),
        "weekday": _WEEKDAY_LABELS[w.date.weekday()],
        "plan_workout_id": w.id,
        # V1.6 §6 enum: a workout that hasn't happened yet is
        # ``planned_only`` regardless of today's date.
        "plan_status": "planned_only",
        # No activity → no possibility of a rest-day violation.
        "violated_rest_day": False,
        "run_type_key": canonical_run_type_key,
        "run_type": {
            "key": rt_def.key,
            "display_name": rt_def.display_name,
            "target_zone_ids": list(rt_def.target_zone_ids),
        },
        "workout_type": w.workout_type,
        "intensity": w.intensity,
        "description": w.description,
        "miles": w.miles,
        "target_zone": w.target_zone,
        "target_hr": target_hr,
        "focus": w.focus,
        "phase": w.phase,
        # 3B.3: future-week contract — ``execution`` is None.
        "execution": None,
    }


def _build_past_current_day_entry(
    w: PlanWorkout,
    canonical_run_type_key: str,
    target_hr: Optional[Any],
    activity: Optional[Activity],
    plan_training_days: Optional[Any],
    today: date,
) -> Tuple[Dict[str, Any], Optional[WeeklyAdherenceEntry]]:
    """
    Per-day entry for a PAST or CURRENT week plus its adherence entry.

    Returns ``(day_dict, adherence_entry_or_None)``. The adherence
    entry is ``None`` only when ``plan_status_for_day`` returned
    ``None``; in practice every loop iteration here is driven by a
    real ``PlanWorkout`` so we always have an entry, but we preserve
    the defensive guard to honor the aggregator contract.
    """
    rt_def = (
        RUN_TYPE_DEFINITIONS.get(canonical_run_type_key)
        or RUN_TYPE_DEFINITIONS[RUN_TYPE_EASY]
    )

    execution = (
        execution_block_to_weekly_plan_shape(
            build_run_execution_block(activity, plan_training_days=plan_training_days),
            activity,
        )
        if activity is not None
        else None
    )

    day_plan_status = plan_status_for_day(
        has_planned_workout=True,
        has_matching_activity=activity is not None,
        day_date=w.date,
        today=today,
    )

    entry: Optional[WeeklyAdherenceEntry] = None
    if day_plan_status is not None:
        entry = WeeklyAdherenceEntry(
            plan_status=day_plan_status,
            completion_pct=(
                getattr(activity, "completion_pct", None)
                if activity is not None
                else None
            ),
            planned_miles=w.miles,
            actual_miles=(
                getattr(activity, "actual_miles", None)
                if activity is not None
                else None
            ),
        )

    day = {
        "date": w.date.isoformat(),
        "weekday": _WEEKDAY_LABELS[w.date.weekday()],
        "plan_workout_id": w.id,
        "plan_status": day_plan_status.value if day_plan_status else None,
        # A day with a planned workout is by definition NOT a rest day,
        # so violated_rest_day is always False for route-driven entries.
        # When Phase B extends the builder to surface unplanned-day
        # activities, the true branch will be reached via the
        # execution block's derivation (already wired).
        "violated_rest_day": False,
        "run_type_key": canonical_run_type_key,
        "run_type": {
            "key": rt_def.key,
            "display_name": rt_def.display_name,
            "target_zone_ids": list(rt_def.target_zone_ids),
        },
        "workout_type": w.workout_type,
        "intensity": w.intensity,
        "description": w.description,
        "miles": w.miles,
        "target_zone": w.target_zone,
        "target_hr": target_hr,
        "focus": w.focus,
        "phase": w.phase,
        "execution": execution,
    }
    return day, entry


def build_weekly_plan_payload(
    session: Session,
    user_id: UUID,
    *,
    tz: str = "UTC",
    target_week_start: Optional[date] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Build the V1.6 §6 weekly-plan payload for any past / current /
    future Monday-to-Sunday window.

    Args:
        session: Active SQLAlchemy session.
        user_id: Internal user UUID (not Auth0 subject).
        tz: IANA timezone name used to resolve "today" when
            ``today`` is not supplied. Defaults to UTC.
        target_week_start: Any date within the target week; normalized
            to that week's Monday via
            :func:`src.utils.date_helpers.get_week_bounds_for_date`.
            ``None`` (default) resolves to the athlete's current week.
        today: Optional explicit "today" override (primarily for
            tests). When provided, overrides ``tz``.

    Returns:
        Either an error envelope:

            ``{"error": "no_plan", "message": "No plan found"}``

        or a full payload dict:

            ``{
                "plan_id": int,
                "plan_name": str | None,
                "race_date": str | None,
                "race_distance": str | None,
                "timezone": str,
                "today": "YYYY-MM-DD",
                "week_start": "YYYY-MM-DD",
                "week_end": "YYYY-MM-DD",
                "week_temporality": "past" | "current" | "future",
                "days": [...],
                "adherence": {...} | None,  # None for FUTURE weeks
                "phase_kpi_priority": {...} | None,
            }``

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

    anchor_date = target_week_start if target_week_start is not None else resolved_today
    week_start, week_end = get_week_bounds_for_date(anchor_date)
    temporality = classify_week_temporality(week_start, today=resolved_today)

    # Fetch planned workouts for the target week. Always needed,
    # regardless of temporality.
    workouts = (
        session.query(PlanWorkout)
        .filter(
            PlanWorkout.plan_id == plan_row.id,
            PlanWorkout.date >= week_start,
            PlanWorkout.date <= week_end,
        )
        .order_by(PlanWorkout.date)
        .all()
    )

    # FUTURE weeks: skip activity join entirely (3B.3 deterministic
    # future-week contract). PAST / CURRENT: load matched activities.
    if temporality == WeekTemporality.FUTURE:
        execution_by_pw: Dict[int, Activity] = {}
    else:
        execution_by_pw = _load_matched_activities_by_pw_id(
            session, user_id, [w.id for w in workouts]
        )

    # Legacy fallback for rows missing target_hr. Imported lazily to
    # avoid pulling the heavy plan_storage_service onto the hot path
    # when all rows already have stored zones (common case).
    plan_training_days = plan_row.training_days
    days: List[Dict[str, Any]] = []
    adherence_entries: List[WeeklyAdherenceEntry] = []

    need_hr_fallback = any(not w.target_hr for w in workouts)
    user_profile = None
    PlanStorageService = None  # noqa: N806
    if need_hr_fallback:
        from src.db.dao.user_profile_dao import get_user_profile
        from src.services.training_plan.plan_storage_service import (
            PlanStorageService as _PlanStorageService,
        )

        PlanStorageService = _PlanStorageService  # noqa: N806
        user_profile = get_user_profile(session, str(user_id))

    for w in workouts:
        canonical = _resolve_run_type_key(w)
        target_hr = w.target_hr
        if not target_hr and PlanStorageService is not None:
            target_hr = PlanStorageService._calculate_hr_zone(canonical, user_profile)

        if temporality == WeekTemporality.FUTURE:
            days.append(_build_future_week_day_entry(w, canonical, target_hr))
            continue

        act = execution_by_pw.get(w.id)
        day, entry = _build_past_current_day_entry(
            w=w,
            canonical_run_type_key=canonical,
            target_hr=target_hr,
            activity=act,
            plan_training_days=plan_training_days,
            today=resolved_today,
        )
        days.append(day)
        if entry is not None:
            adherence_entries.append(entry)

    # Week-level phase_kpi_priority — emitted for all temporalities
    # because a future week's emphasis is a statement about the
    # planned phase, not about execution (§8, §19.4).
    phase_kpi_result = compute_phase_kpi_priority_for_week(w.phase for w in workouts)
    if phase_kpi_result.phase is None:
        phase_kpi_payload: Optional[Dict[str, Any]] = None
    else:
        phase_kpi_payload = {
            "phase": phase_kpi_result.phase.value,
            "priority": [
                {"kpi_id": e.kpi_id, "label": e.label}
                for e in phase_kpi_result.priority
            ],
            "day_counts": dict(phase_kpi_result.day_counts),
        }

    # Weekly adherence — only meaningful for PAST / CURRENT. For
    # FUTURE weeks the block is ``None`` (3B.3 future-week contract).
    adherence_payload: Optional[Dict[str, Any]]
    if temporality == WeekTemporality.FUTURE:
        adherence_payload = None
    else:
        adherence_result = compute_weekly_adherence(adherence_entries)
        adherence_payload = {
            "adherence_runs_pct": adherence_result.adherence_runs_pct,
            "completed_runs": adherence_result.completed_runs,
            "planned_runs": adherence_result.planned_runs,
            "band": adherence_result.band.value if adherence_result.band else None,
            "completion_miles_pct": adherence_result.completion_miles_pct_weekly,
            "planned_miles_total": adherence_result.planned_miles_total,
            "actual_miles_matched_total": (adherence_result.actual_miles_matched_total),
        }

    return {
        "plan_id": plan_row.id,
        "plan_name": plan_row.plan_name,
        "race_date": (plan_row.race_date.isoformat() if plan_row.race_date else None),
        "race_distance": plan_row.race_distance,
        "timezone": tz_norm,
        "today": resolved_today.isoformat(),
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "week_temporality": temporality.value,
        "days": days,
        "adherence": adherence_payload,
        "phase_kpi_priority": phase_kpi_payload,
    }


__all__ = [
    "build_weekly_plan_payload",
]

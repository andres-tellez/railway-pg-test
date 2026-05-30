"""
Canonical structured plan-adjustment writer for V1.6 Phase E.

This module is the ONLY place that validates and applies coach-driven
plan mutations for the minimal structured operation set:

* ``adjust_volume``
* ``adjust_intensity``
* ``add_run``
* ``remove_run``

Design contract
---------------
* The LLM never mutates the plan directly. It emits a structured tool
  call; this module normalizes, validates, caps, and applies it.
* Every requested operation produces an audit-log entry in
  ``weekly_decision_log`` (applied or rejected).
* Volume-affecting operations are constrained against the prior week's
  total mileage with a hard ``±10 %`` cap (fallback: current week's
  total when no prior week exists in the plan).
* Intensity increases are capped at ``+1`` quality run per week.
* Intensity decreases are unbounded for safety, but dropping below the
  phase minimum requires an explicit ``reason_code``.
* The day after a Long Run may not become a training day, and may not
  become a quality day.
* Mileage is normalized to ``0.5``-mile granularity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.runner_profile.plan_workout_taxonomy import (
    is_quality_workout as taxonomy_is_quality,
    pace_zone_key_for_taxonomy,
    placement_role_for_taxonomy,
    resolve_taxonomy_and_placement,
    workout_display_label,
)
from src.db.dao.plan_workouts_dao import get_workouts_for_week
from src.db.dao.weekly_decision_log_dao import create_decision_log
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.utils.date_helpers import (
    DAY_NAMES_FULL,
    date_to_day_name,
    day_name_to_weekday,
    get_week_bounds_for_date,
    get_week_start_for_date,
    normalize_day_name,
)

logger = logging.getLogger(__name__)

PLAN_ADJUSTMENTS_SCHEMA_VERSION = 1

_ALLOWED_OPS = frozenset(
    {
        "adjust_volume",
        "adjust_intensity",
        "add_run",
        "remove_run",
    }
)
_ALLOWED_RUN_TYPES = frozenset({"easy", "recovery", "tempo", "long"})
_ALLOWED_REASON_CODES = frozenset(
    {"injury_signal", "adherence_low", "deload_week", "user_preference", "illness"}
)

_MAX_VOLUME_CHANGE_PCT = 10.0
_MILE_GRANULARITY = 0.5
_MIN_RUNS_PER_WEEK = 3
_MAX_RUNS_PER_WEEK = 6

# V1.6 §16 phase quality floor / ceiling for the minimal Phase E writer.
_PHASE_MIN_QUALITY = {"Base": 0, "Build": 1, "Peak": 1, "Taper": 0}
_PHASE_MAX_QUALITY = {"Base": 0, "Build": 2, "Peak": 2, "Taper": 1}

_QUALITY_WORKOUT_TOKENS = ("tempo", "threshold", "interval", "hill", "fartlek")
_QUALITY_INTENSITY_TOKENS = {"z3", "z4", "m"}


@dataclass
class _WeekContext:
    plan: Plan
    week_start: date
    week_end: date
    baseline_total_miles: float
    workouts: List[PlanWorkout]


def _load_active_plan(session: Session, user_id: UUID) -> Optional[Plan]:
    return (
        session.query(Plan)
        .filter(Plan.user_id == user_id, Plan.is_active.is_(True))
        .order_by(Plan.created_at.desc())
        .first()
    )


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _round_half_mile(value: float) -> float:
    return round(max(0.0, float(value)) / _MILE_GRANULARITY) * _MILE_GRANULARITY


def _floor_half_mile(value: float) -> float:
    units = int(max(0.0, float(value)) / _MILE_GRANULARITY)
    return units * _MILE_GRANULARITY


def _week_total_miles(workouts: List[PlanWorkout]) -> float:
    return round(
        sum(float(getattr(workout, "miles", 0.0) or 0.0) for workout in workouts),
        2,
    )


def _is_long_run(workout: PlanWorkout) -> bool:
    key = (workout.run_type_key or "").strip().lower()
    if key in {"long", "long_run"}:
        return True
    label = (workout.workout_type or "").strip().lower()
    return "long" in label


def _is_quality_workout(workout: PlanWorkout) -> bool:
    if _is_long_run(workout):
        return False
    intensity = (workout.intensity or "").strip().lower()
    if intensity in _QUALITY_INTENSITY_TOKENS:
        return True
    label = (workout.workout_type or "").strip().lower()
    return any(token in label for token in _QUALITY_WORKOUT_TOKENS)


def _count_quality_runs(workouts: List[PlanWorkout]) -> int:
    return sum(1 for workout in workouts if _is_quality_workout(workout))


def _resolve_phase(workouts: List[PlanWorkout]) -> str:
    counts: Dict[str, int] = {}
    for workout in workouts:
        raw = (workout.phase or "").strip()
        if raw:
            counts[raw] = counts.get(raw, 0) + 1
    if not counts:
        return "Base"
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _weeks_remaining(plan: Plan, week_start: date) -> Optional[int]:
    if not plan.race_date:
        return None
    delta_days = (plan.race_date - week_start).days
    return max(0, delta_days // 7)


def _serialize_workout(workout: PlanWorkout) -> Dict[str, Any]:
    return {
        "id": workout.id,
        "date": workout.date.isoformat() if workout.date else None,
        "day": date_to_day_name(workout.date) if workout.date else None,
        "workout_type": workout.workout_type,
        "description": workout.description,
        "miles": float(workout.miles or 0.0),
        "intensity": workout.intensity,
        "run_type_key": workout.run_type_key,
        "phase": workout.phase,
    }


def _quality_cap_for_phase(phase: str) -> int:
    return _PHASE_MAX_QUALITY.get(phase, 1)


def _quality_floor_for_phase(phase: str) -> int:
    return _PHASE_MIN_QUALITY.get(phase, 0)


def _load_week_context(
    session: Session,
    user_id: UUID,
    week_start_raw: Any,
) -> Tuple[str, Dict[str, Any]] | Tuple[str, _WeekContext]:
    if not isinstance(week_start_raw, str) or not str(week_start_raw).strip():
        return (
            "invalid_week_start_date",
            {
                "error": "invalid_week_start_date",
                "message": "week_start_date must be a YYYY-MM-DD string.",
            },
        )

    try:
        week_start = get_week_start_for_date(str(week_start_raw).strip())
    except Exception:
        return (
            "invalid_week_start_date",
            {
                "error": "invalid_week_start_date",
                "message": "week_start_date must be a YYYY-MM-DD string.",
            },
        )

    plan = _load_active_plan(session, user_id)
    if plan is None:
        return (
            "no_active_plan",
            {
                "error": "no_active_plan",
                "message": "No active plan on file for this user.",
            },
        )

    week_start, week_end = get_week_bounds_for_date(week_start)
    workouts = list(get_workouts_for_week(session, plan.id, week_start, week_end))
    if not workouts:
        return (
            "no_plan_week",
            {
                "error": "no_plan_week",
                "message": "No workouts found for that plan week.",
                "week_start_date": week_start.isoformat(),
            },
        )

    previous_start = week_start - timedelta(days=7)
    previous_end = week_end - timedelta(days=7)
    previous_workouts = list(
        get_workouts_for_week(session, plan.id, previous_start, previous_end)
    )
    current_total = _week_total_miles(workouts)
    baseline_total = _week_total_miles(previous_workouts) or current_total

    return (
        "ok",
        _WeekContext(
            plan=plan,
            week_start=week_start,
            week_end=week_end,
            baseline_total_miles=baseline_total,
            workouts=workouts,
        ),
    )


def _metrics_snapshot(
    ctx: _WeekContext, before_total: float, after_total: float
) -> Dict[str, Any]:
    return {
        "schema_version": PLAN_ADJUSTMENTS_SCHEMA_VERSION,
        "baseline_total_miles": ctx.baseline_total_miles,
        "week_total_miles_before": before_total,
        "week_total_miles_after": after_total,
        "week_run_count_after": len(ctx.workouts),
        "quality_run_count_after": _count_quality_runs(ctx.workouts),
    }


def _create_audit_log(
    session: Session,
    *,
    ctx: _WeekContext,
    operation: Dict[str, Any],
    normalized: Dict[str, Any],
    status: str,
    message: str,
    caps_applied: List[str],
    affected_workouts: List[PlanWorkout],
    before_total: float,
    after_total: float,
) -> int:
    log = create_decision_log(
        session=session,
        plan_id=ctx.plan.id,
        week_num=int(
            (
                (
                    ctx.week_start
                    - get_week_start_for_date(
                        ctx.plan.created_at.date()
                        if ctx.plan.created_at
                        else ctx.week_start
                    )
                ).days
                // 7
            )
            + 1
        ),
        week_start_date=ctx.week_start,
        decision_type="plan_adjustment",
        trigger_reason=message,
        metrics_json=_metrics_snapshot(ctx, before_total, after_total),
        adjustments_json={
            "schema_version": PLAN_ADJUSTMENTS_SCHEMA_VERSION,
            "status": status,
            "requested": operation,
            "normalized": normalized,
            "caps_applied": caps_applied,
            "affected_workouts": [
                _serialize_workout(workout) for workout in affected_workouts
            ],
        },
        match_score=0.0,
        phase=_resolve_phase(ctx.workouts),
        weeks_remaining=_weeks_remaining(ctx.plan, ctx.week_start),
    )
    return int(log.id)


def _volume_bounds(ctx: _WeekContext) -> Tuple[float, float]:
    baseline = max(0.0, ctx.baseline_total_miles)
    lo = _round_half_mile(baseline * 0.90)
    hi = _round_half_mile(baseline * 1.10)
    return lo, hi


def _normalize_day(raw: Any) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    candidate = normalize_day_name(raw.strip())
    return candidate if candidate in DAY_NAMES_FULL else None


def _date_for_day(ctx: _WeekContext, day_name: str) -> date:
    return ctx.week_start + timedelta(days=day_name_to_weekday(day_name))


def _workout_for_day(ctx: _WeekContext, day_name: str) -> Optional[PlanWorkout]:
    target_date = _date_for_day(ctx, day_name)
    for workout in ctx.workouts:
        if workout.date == target_date:
            return workout
    return None


def _coach_taxonomy_type(run_type: str) -> str:
    """Map minimal coach adjustment run_type to taxonomy key."""
    if run_type == "recovery":
        return "easy"
    if run_type == "long":
        return "long_run"
    return run_type


def _db_fields_for_added_run(
    *,
    ctx: _WeekContext,
    day_name: str,
    run_type: str,
    miles: float,
) -> Dict[str, Any]:
    workout_date = _date_for_day(ctx, day_name)
    taxonomy_type, persisted_key = resolve_taxonomy_and_placement(
        _coach_taxonomy_type(run_type)
    )
    return {
        "plan_id": ctx.plan.id,
        "date": workout_date,
        "workout_type": workout_display_label(taxonomy_type),
        "description": f"{workout_display_label(taxonomy_type)} (coach adjustment)",
        "miles": miles,
        "intensity": pace_zone_key_for_taxonomy(taxonomy_type),
        "run_type_key": persisted_key,
        "phase": _resolve_phase(ctx.workouts),
        "allow_quality": taxonomy_is_quality(taxonomy_type),
    }


def _day_after_long_is_training(ctx: _WeekContext, candidate_day: str) -> bool:
    candidate_date = _date_for_day(ctx, candidate_day)
    previous_date = candidate_date - timedelta(days=1)
    for workout in ctx.workouts:
        if workout.date == previous_date and _is_long_run(workout):
            return True
    return False


def _quality_adjacent(ctx: _WeekContext, candidate_day: str) -> bool:
    candidate_date = _date_for_day(ctx, candidate_day)
    for delta in (-1, 1):
        neighbor = candidate_date + timedelta(days=delta)
        for workout in ctx.workouts:
            if workout.date == neighbor and _is_quality_workout(workout):
                return True
    return False


def _allocate_adjusted_miles(
    rows: List[PlanWorkout],
    target_total: float,
) -> List[float]:
    if not rows:
        return []
    current_total = sum(float(row.miles or 0.0) for row in rows)
    if current_total <= 0:
        return [float(row.miles or 0.0) for row in rows]

    target_units = int(round(target_total / _MILE_GRANULARITY))
    raw_units = [
        (float(row.miles or 0.0) / current_total) * target_units for row in rows
    ]
    base_units = [int(value) for value in raw_units]
    assigned = sum(base_units)
    remainders = [
        (raw_units[idx] - base_units[idx], idx) for idx in range(len(raw_units))
    ]
    for _fraction, idx in sorted(remainders, reverse=True):
        if assigned >= target_units:
            break
        base_units[idx] += 1
        assigned += 1
    return [units * _MILE_GRANULARITY for units in base_units]


def _apply_adjust_volume(
    ctx: _WeekContext,
    requested: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], List[str], List[PlanWorkout], str]:
    delta_pct = _coerce_float(requested.get("delta_pct"))
    if delta_pct is None:
        return (
            "rejected",
            {"op": "adjust_volume"},
            [],
            [],
            "adjust_volume requires numeric delta_pct.",
        )

    normalized_delta = max(
        -_MAX_VOLUME_CHANGE_PCT, min(_MAX_VOLUME_CHANGE_PCT, delta_pct)
    )
    caps_applied: List[str] = []
    if normalized_delta != delta_pct:
        caps_applied.append("volume_delta_pct_capped_10")

    before_total = _week_total_miles(ctx.workouts)
    min_total, max_total = _volume_bounds(ctx)
    requested_total = _round_half_mile(
        before_total * (1.0 + (normalized_delta / 100.0))
    )
    target_total = min(max(requested_total, min_total), max_total)
    if target_total != requested_total:
        caps_applied.append("weekly_total_capped_by_prior_week")

    adjustable = [row for row in ctx.workouts if not _is_long_run(row)]
    if not adjustable:
        adjustable = list(ctx.workouts)
    if not adjustable:
        return (
            "rejected",
            {"op": "adjust_volume", "delta_pct": normalized_delta},
            caps_applied,
            [],
            "No workouts available to adjust.",
        )

    fixed_total = before_total - sum(float(row.miles or 0.0) for row in adjustable)
    target_adjustable_total = max(0.0, target_total - fixed_total)
    new_miles = _allocate_adjusted_miles(adjustable, target_adjustable_total)
    for row, miles in zip(sorted(adjustable, key=lambda item: item.date), new_miles):
        row.miles = _round_half_mile(miles)

    return (
        "applied",
        {
            "op": "adjust_volume",
            "delta_pct_requested": delta_pct,
            "delta_pct_applied": (
                round(
                    ((_week_total_miles(ctx.workouts) - before_total) / before_total)
                    * 100.0,
                    2,
                )
                if before_total > 0
                else 0.0
            ),
        },
        caps_applied,
        list(adjustable),
        "Applied structured volume adjustment.",
    )


def _apply_adjust_intensity(
    ctx: _WeekContext,
    requested: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], List[str], List[PlanWorkout], str]:
    quality_delta = _coerce_int(requested.get("quality_delta"))
    reason_code = requested.get("reason_code")
    if quality_delta is None or quality_delta == 0:
        return (
            "rejected",
            {"op": "adjust_intensity"},
            [],
            [],
            "adjust_intensity requires non-zero integer quality_delta.",
        )

    phase = _resolve_phase(ctx.workouts)
    caps_applied: List[str] = []
    if quality_delta > 0:
        normalized_delta = 1
        if quality_delta != 1:
            caps_applied.append("quality_increase_capped_plus_1")

        current_quality = _count_quality_runs(ctx.workouts)
        quality_cap = _quality_cap_for_phase(phase)
        if current_quality >= quality_cap:
            return (
                "rejected",
                {"op": "adjust_intensity", "quality_delta": normalized_delta},
                caps_applied,
                [],
                f"{phase} phase is already at its quality ceiling.",
            )
        if current_quality == 1 and len(ctx.workouts) < 5:
            return (
                "rejected",
                {"op": "adjust_intensity", "quality_delta": normalized_delta},
                caps_applied,
                [],
                "A second quality run requires at least 5 runs in the week.",
            )

        eligible = []
        for workout in sorted(ctx.workouts, key=lambda item: item.date):
            day_name = date_to_day_name(workout.date)
            if _is_long_run(workout) or _is_quality_workout(workout):
                continue
            if _day_after_long_is_training(ctx, day_name):
                continue
            if _quality_adjacent(ctx, day_name):
                continue
            eligible.append(workout)
        if not eligible:
            return (
                "rejected",
                {"op": "adjust_intensity", "quality_delta": normalized_delta},
                caps_applied,
                [],
                "No eligible workout could be upgraded without breaking spacing rules.",
            )

        workout = eligible[0]
        taxonomy_type = "tempo"
        workout.workout_type = workout_display_label(taxonomy_type)
        workout.description = (
            f"{workout_display_label(taxonomy_type)} (coach adjustment)"
        )
        workout.intensity = pace_zone_key_for_taxonomy(taxonomy_type)
        workout.run_type_key = placement_role_for_taxonomy(taxonomy_type)
        workout.allow_quality = True
        return (
            "applied",
            {"op": "adjust_intensity", "quality_delta_applied": 1},
            caps_applied,
            [workout],
            "Applied structured intensity increase.",
        )

    # quality decrease — unbounded, but quality floor may require reason_code
    normalized_delta = quality_delta
    quality_rows = [
        workout
        for workout in sorted(ctx.workouts, key=lambda item: item.date, reverse=True)
        if _is_quality_workout(workout)
    ]
    if not quality_rows:
        return (
            "rejected",
            {"op": "adjust_intensity", "quality_delta": normalized_delta},
            [],
            [],
            "No quality workouts are available to de-intensify.",
        )

    to_convert = quality_rows[: abs(normalized_delta)]
    resulting_quality = _count_quality_runs(ctx.workouts) - len(to_convert)
    quality_floor = _quality_floor_for_phase(phase)
    if resulting_quality < quality_floor:
        if not isinstance(reason_code, str) or reason_code not in _ALLOWED_REASON_CODES:
            return (
                "rejected",
                {
                    "op": "adjust_intensity",
                    "quality_delta": normalized_delta,
                    "requires_reason_code": True,
                },
                [],
                [],
                f"{phase} quality floor requires reason_code when dropping below minimum.",
            )
        caps_applied.append("quality_floor_override_with_reason_code")

    for workout in to_convert:
        workout.workout_type = workout_display_label("easy")
        workout.description = "Easy (coach adjustment from quality)"
        workout.intensity = pace_zone_key_for_taxonomy("easy")
        workout.run_type_key = placement_role_for_taxonomy("easy")
        workout.allow_quality = False

    return (
        "applied",
        {
            "op": "adjust_intensity",
            "quality_delta_applied": -len(to_convert),
            "reason_code": reason_code if isinstance(reason_code, str) else None,
        },
        caps_applied,
        to_convert,
        "Applied structured intensity decrease.",
    )


def _apply_add_run(
    session: Session,
    ctx: _WeekContext,
    requested: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], List[str], List[PlanWorkout], str]:
    day_name = _normalize_day(requested.get("day"))
    run_type = str(requested.get("run_type") or "").strip().lower()
    requested_miles = _coerce_float(requested.get("miles"))
    if (
        day_name is None
        or run_type not in _ALLOWED_RUN_TYPES
        or requested_miles is None
    ):
        return (
            "rejected",
            {"op": "add_run"},
            [],
            [],
            "add_run requires valid day, run_type, and miles.",
        )

    if len(ctx.workouts) >= _MAX_RUNS_PER_WEEK:
        return (
            "rejected",
            {"op": "add_run", "day": day_name, "run_type": run_type},
            [],
            [],
            "Cannot add a run beyond the 6-run weekly maximum.",
        )

    if _workout_for_day(ctx, day_name) is not None:
        return (
            "rejected",
            {"op": "add_run", "day": day_name, "run_type": run_type},
            [],
            [],
            f"{day_name} already has a planned workout.",
        )

    if run_type == "long" and any(_is_long_run(workout) for workout in ctx.workouts):
        return (
            "rejected",
            {"op": "add_run", "day": day_name, "run_type": run_type},
            [],
            [],
            "The week already has a Long Run anchor.",
        )

    if _day_after_long_is_training(ctx, day_name):
        return (
            "rejected",
            {"op": "add_run", "day": day_name, "run_type": run_type},
            [],
            [],
            "The day after a Long Run cannot be converted into a training day.",
        )

    if run_type == "tempo" and _quality_adjacent(ctx, day_name):
        return (
            "rejected",
            {"op": "add_run", "day": day_name, "run_type": run_type},
            [],
            [],
            "Quality workouts cannot be placed back-to-back.",
        )

    if run_type == "tempo":
        phase = _resolve_phase(ctx.workouts)
        current_quality = _count_quality_runs(ctx.workouts)
        quality_cap = _quality_cap_for_phase(phase)
        if current_quality >= quality_cap:
            return (
                "rejected",
                {"op": "add_run", "day": day_name, "run_type": run_type},
                [],
                [],
                f"{phase} phase is already at its quality ceiling.",
            )
        if current_quality == 1 and len(ctx.workouts) < 5:
            return (
                "rejected",
                {"op": "add_run", "day": day_name, "run_type": run_type},
                [],
                [],
                "A second quality run requires at least 5 runs in the week.",
            )

    before_total = _week_total_miles(ctx.workouts)
    _min_total, max_total = _volume_bounds(ctx)
    normalized_miles = _round_half_mile(requested_miles)
    caps_applied: List[str] = []
    remaining_headroom = _floor_half_mile(max_total - before_total)
    applied_miles = min(normalized_miles, remaining_headroom)
    if applied_miles != normalized_miles:
        caps_applied.append("add_run_capped_by_weekly_volume")
    if applied_miles < _MILE_GRANULARITY:
        return (
            "rejected",
            {
                "op": "add_run",
                "day": day_name,
                "run_type": run_type,
                "miles": normalized_miles,
            },
            caps_applied,
            [],
            "No volume headroom remains under the weekly ±10% cap.",
        )

    row = PlanWorkout(
        **_db_fields_for_added_run(
            ctx=ctx, day_name=day_name, run_type=run_type, miles=applied_miles
        )
    )
    session.add(row)
    session.flush()
    ctx.workouts.append(row)
    ctx.workouts.sort(key=lambda item: item.date)
    return (
        "applied",
        {
            "op": "add_run",
            "day": day_name,
            "run_type": run_type,
            "miles_requested": normalized_miles,
            "miles_applied": applied_miles,
        },
        caps_applied,
        [row],
        "Added structured run adjustment.",
    )


def _apply_remove_run(
    session: Session,
    ctx: _WeekContext,
    requested: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], List[str], List[PlanWorkout], str]:
    day_name = _normalize_day(requested.get("day"))
    reason_code = requested.get("reason_code")
    if day_name is None:
        return (
            "rejected",
            {"op": "remove_run"},
            [],
            [],
            "remove_run requires a valid day.",
        )

    workout = _workout_for_day(ctx, day_name)
    if workout is None:
        return (
            "rejected",
            {"op": "remove_run", "day": day_name},
            [],
            [],
            f"No planned workout exists on {day_name}.",
        )

    if _is_long_run(workout):
        return (
            "rejected",
            {"op": "remove_run", "day": day_name},
            [],
            [],
            "The Long Run anchor cannot be removed by this minimal adjustment writer.",
        )

    if len(ctx.workouts) <= _MIN_RUNS_PER_WEEK:
        return (
            "rejected",
            {"op": "remove_run", "day": day_name},
            [],
            [],
            "Cannot drop below the 3-run weekly minimum.",
        )

    phase = _resolve_phase(ctx.workouts)
    if _is_quality_workout(workout):
        resulting_quality = _count_quality_runs(ctx.workouts) - 1
        quality_floor = _quality_floor_for_phase(phase)
        if resulting_quality < quality_floor:
            if (
                not isinstance(reason_code, str)
                or reason_code not in _ALLOWED_REASON_CODES
            ):
                return (
                    "rejected",
                    {
                        "op": "remove_run",
                        "day": day_name,
                        "requires_reason_code": True,
                    },
                    [],
                    [],
                    f"{phase} quality floor requires reason_code when removing this run.",
                )

    before_total = _week_total_miles(ctx.workouts)
    min_total, _max_total = _volume_bounds(ctx)
    after_total = round(before_total - float(workout.miles or 0.0), 2)
    if after_total < min_total:
        return (
            "rejected",
            {"op": "remove_run", "day": day_name},
            [],
            [],
            "Removing this run would break the weekly -10% volume floor.",
        )

    ctx.workouts = [row for row in ctx.workouts if row.id != workout.id]
    session.delete(workout)
    session.flush()
    return (
        "applied",
        {
            "op": "remove_run",
            "day": day_name,
            "removed_workout_id": workout.id,
            "reason_code": reason_code if isinstance(reason_code, str) else None,
        },
        [],
        [workout],
        "Removed structured run adjustment.",
    )


def apply_plan_adjustments(
    session: Session,
    user_id: UUID,
    *,
    week_start_date_raw: Any,
    operations_raw: Any,
) -> Tuple[str, Dict[str, Any]]:
    """Normalize, validate, apply, and audit a batch of plan adjustments."""
    status, loaded = _load_week_context(session, user_id, week_start_date_raw)
    if status != "ok":
        return status, loaded
    ctx = loaded

    if not isinstance(operations_raw, list) or not operations_raw:
        return (
            "invalid_operations",
            {
                "error": "invalid_operations",
                "message": "operations must be a non-empty array of structured operations.",
            },
        )

    week_total_before = _week_total_miles(ctx.workouts)
    results: List[Dict[str, Any]] = []

    for index, raw_op in enumerate(operations_raw):
        op_payload = raw_op if isinstance(raw_op, dict) else {}
        op_name = (
            str(op_payload.get("op") or op_payload.get("operation") or "")
            .strip()
            .lower()
        )
        before_total = _week_total_miles(ctx.workouts)

        if op_name not in _ALLOWED_OPS:
            normalized = {"op": op_name or None}
            message = f"Unsupported operation: {op_name or '<missing>'}."
            audit_id = _create_audit_log(
                session,
                ctx=ctx,
                operation=op_payload if isinstance(raw_op, dict) else {"raw": raw_op},
                normalized=normalized,
                status="rejected",
                message=message,
                caps_applied=[],
                affected_workouts=[],
                before_total=before_total,
                after_total=before_total,
            )
            results.append(
                {
                    "index": index,
                    "requested": (
                        op_payload if isinstance(raw_op, dict) else {"raw": raw_op}
                    ),
                    "normalized": normalized,
                    "status": "rejected",
                    "message": message,
                    "caps_applied": [],
                    "audit_log_id": audit_id,
                }
            )
            continue

        if op_name == "adjust_volume":
            op_status, normalized, caps_applied, affected, message = (
                _apply_adjust_volume(ctx, op_payload)
            )
        elif op_name == "adjust_intensity":
            op_status, normalized, caps_applied, affected, message = (
                _apply_adjust_intensity(ctx, op_payload)
            )
        elif op_name == "add_run":
            op_status, normalized, caps_applied, affected, message = _apply_add_run(
                session, ctx, op_payload
            )
        else:
            op_status, normalized, caps_applied, affected, message = _apply_remove_run(
                session, ctx, op_payload
            )

        after_total = _week_total_miles(ctx.workouts)
        audit_id = _create_audit_log(
            session,
            ctx=ctx,
            operation=op_payload,
            normalized=normalized,
            status=op_status,
            message=message,
            caps_applied=caps_applied,
            affected_workouts=affected,
            before_total=before_total,
            after_total=after_total,
        )
        results.append(
            {
                "index": index,
                "requested": op_payload,
                "normalized": normalized,
                "status": op_status,
                "message": message,
                "caps_applied": caps_applied,
                "audit_log_id": audit_id,
                "affected_workouts": [
                    _serialize_workout(workout) for workout in affected
                ],
                "week_total_miles_before": before_total,
                "week_total_miles_after": after_total,
            }
        )

    week_total_after = _week_total_miles(ctx.workouts)
    applied_count = sum(1 for item in results if item["status"] == "applied")
    rejected_count = len(results) - applied_count
    return (
        "ok",
        {
            "schema_version": PLAN_ADJUSTMENTS_SCHEMA_VERSION,
            "saved": applied_count > 0,
            "plan_id": ctx.plan.id,
            "week_start_date": ctx.week_start.isoformat(),
            "week_end_date": ctx.week_end.isoformat(),
            "baseline_total_miles": ctx.baseline_total_miles,
            "week_total_miles_before": week_total_before,
            "week_total_miles_after": week_total_after,
            "applied_count": applied_count,
            "rejected_count": rejected_count,
            "operations": results,
            "message": (
                "Applied plan adjustments."
                if applied_count > 0
                else "No plan adjustments were applied."
            ),
        },
    )


__all__ = [
    "PLAN_ADJUSTMENTS_SCHEMA_VERSION",
    "apply_plan_adjustments",
]

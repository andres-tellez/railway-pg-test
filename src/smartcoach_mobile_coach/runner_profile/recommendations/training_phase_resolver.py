from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from src.db.models.activities import Activity
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.services.phase.phase_priority import (
    Phase,
    compute_phase_kpi_priority_for_week,
)
from src.utils.date_helpers import get_week_bounds_for_date, get_week_start_for_date
from src.utils.normalize import normalize_postgres_row
from src.utils.timezone_helpers import DEFAULT_TIMEZONE, get_today_date_in_timezone


@dataclass(frozen=True)
class PlanSpanPhaseInferenceConfig:
    """
    Fallback ratios when inferring phase from position in plan span.

    Mirrors :func:`src.services.training_plan.weekly_rebuild_service._determine_phase`
    (Base → Build → Peak → Taper by week fraction). Used only when the current week's
    ``plan_workouts`` rows yield no usable ``phase`` labels.
    """

    base_end_fraction: float = 0.4
    build_end_fraction: float = 0.7
    peak_end_fraction: float = 0.9


DEFAULT_PLAN_SPAN_PHASE_INFERENCE_CONFIG = PlanSpanPhaseInferenceConfig()


@dataclass(frozen=True)
class TrainingPhaseResolution:
    """Result of resolving training phase from plan + calendar context."""

    phase: str
    source: str
    week_start: date | None


def _coerce_iana_timezone(raw: str | None) -> str | None:
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None

    candidates = [cleaned]
    if " " in cleaned:
        tail = cleaned.rsplit(" ", 1)[-1].strip()
        if tail and tail != cleaned:
            candidates.append(tail)

    for cand in candidates:
        try:
            ZoneInfo(cand)
            return cand
        except ZoneInfoNotFoundError:
            continue
    return None


def _resolve_iana_timezone(session: Session, user_id: str) -> str:
    """Best-effort athlete calendar; defaults to UTC when unknown."""
    try:
        from src.db.dao.user_profile_dao import get_user_profile
    except Exception:  # pragma: no cover - import guard for edge environments
        get_user_profile = None

    if get_user_profile is not None:
        raw = get_user_profile(session, str(user_id))
        if raw:
            row = normalize_postgres_row(raw) if isinstance(raw, dict) else raw
            if isinstance(row, dict):
                tz = _coerce_iana_timezone(
                    row.get("user_timezone")
                    or row.get("timezone")
                    or row.get("iana_timezone")
                )
                if tz:
                    return tz

    latest_tz = (
        session.query(Activity.timezone)
        .filter(Activity.user_id == str(user_id), Activity.timezone.isnot(None))
        .order_by(Activity.start_date.desc())
        .first()
    )
    if latest_tz and latest_tz[0]:
        tz = _coerce_iana_timezone(str(latest_tz[0]))
        if tz:
            return tz
    return DEFAULT_TIMEZONE


def _infer_phase_from_week_index(
    week_index_1based: int,
    total_weeks: int,
    *,
    config: PlanSpanPhaseInferenceConfig = DEFAULT_PLAN_SPAN_PHASE_INFERENCE_CONFIG,
) -> Phase:
    tw = max(1, int(total_weeks))
    w = max(1, min(int(week_index_1based), tw))
    if w <= tw * config.base_end_fraction:
        return Phase.BASE
    if w <= tw * config.build_end_fraction:
        return Phase.BUILD
    if w <= tw * config.peak_end_fraction:
        return Phase.PEAK
    return Phase.TAPER


def _plan_workout_date_bounds(
    session: Session, plan_id: int
) -> tuple[date | None, date | None]:
    mn = (
        session.query(PlanWorkout.date)
        .filter(PlanWorkout.plan_id == plan_id)
        .order_by(PlanWorkout.date.asc())
        .first()
    )
    mx = (
        session.query(PlanWorkout.date)
        .filter(PlanWorkout.plan_id == plan_id)
        .order_by(PlanWorkout.date.desc())
        .first()
    )
    if not mn or not mx:
        return None, None
    return mn[0], mx[0]


def resolve_current_training_phase(
    session: Session,
    user_id: str,
    *,
    plan: Plan | None,
    today: date | None = None,
    tz: str | None = None,
    span_config: PlanSpanPhaseInferenceConfig | None = None,
) -> TrainingPhaseResolution:
    """
    Resolve the athlete's current training phase for recommendation policy.

    Primary: same week-level rule as weekly plan — :func:`compute_phase_kpi_priority_for_week`
    on the current calendar week's ``plan_workouts.phase`` values.

    Fallback: infer from week index along [first plan Monday .. race Monday] (or last
    workout Monday) using :class:`PlanSpanPhaseInferenceConfig` ratios.

    When no plan exists, returns ``Base`` with source ``no_plan`` (conservative default).
    """
    if plan is None:
        return TrainingPhaseResolution(
            phase=Phase.BASE.value,
            source="no_plan",
            week_start=None,
        )

    cfg = span_config or DEFAULT_PLAN_SPAN_PHASE_INFERENCE_CONFIG
    tz_name = (
        tz or _resolve_iana_timezone(session, user_id) or DEFAULT_TIMEZONE
    ).strip()
    resolved_today = today if today is not None else get_today_date_in_timezone(tz_name)
    week_start, week_end = get_week_bounds_for_date(resolved_today)

    workouts = (
        session.query(PlanWorkout)
        .filter(
            PlanWorkout.plan_id == plan.id,
            PlanWorkout.date >= week_start,
            PlanWorkout.date <= week_end,
        )
        .order_by(PlanWorkout.date)
        .all()
    )

    phase_result = compute_phase_kpi_priority_for_week(w.phase for w in workouts)
    if phase_result.phase is not None:
        return TrainingPhaseResolution(
            phase=phase_result.phase.value,
            source="plan_workouts_current_week",
            week_start=week_start,
        )

    # Fallback: position within plan span (no labeled phases this week or empty week).
    min_d, max_d = _plan_workout_date_bounds(session, int(plan.id))
    if min_d is None or max_d is None:
        return TrainingPhaseResolution(
            phase=Phase.BASE.value,
            source="no_plan_workouts",
            week_start=week_start,
        )

    plan_start_monday = get_week_start_for_date(min_d)
    if plan.race_date is not None:
        end_monday = get_week_start_for_date(plan.race_date)
    else:
        end_monday = get_week_start_for_date(max_d)

    if end_monday < plan_start_monday:
        end_monday = plan_start_monday

    total_weeks = max(
        1,
        (end_monday - plan_start_monday).days // 7 + 1,
    )
    current_monday = get_week_start_for_date(resolved_today)
    raw_index = (current_monday - plan_start_monday).days // 7 + 1
    week_index = max(1, min(raw_index, total_weeks))

    inferred = _infer_phase_from_week_index(week_index, total_weeks, config=cfg)
    return TrainingPhaseResolution(
        phase=inferred.value,
        source="plan_span_progress",
        week_start=week_start,
    )


__all__ = [
    "DEFAULT_PLAN_SPAN_PHASE_INFERENCE_CONFIG",
    "PlanSpanPhaseInferenceConfig",
    "TrainingPhaseResolution",
    "resolve_current_training_phase",
]

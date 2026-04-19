"""
Run execution analysis service.

Phase 1 responsibilities:
- Match a completed activity to the active plan workout for that date
- Classify executed run type from HR zone distribution
- Compute zone compliance, above/below deviation, score, and completion
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
import logging
import re
from zoneinfo import ZoneInfo

from sqlalchemy import and_, text
from sqlalchemy.orm import Session

from src.db.models.activities import Activity
from src.utils.run_type_constants import (
    CANONICAL_RUN_TYPES,
    RUN_TYPE_DEFINITIONS,
    RUN_TYPE_EASY,
    RUN_TYPE_LONG,
    normalize_run_type_key,
)
from src.utils.activity_local_date_sql import ACTIVITY_LOCAL_DATE_SQL_FRAGMENT

logger = logging.getLogger(__name__)

_GMT_OFFSET_RE = re.compile(r"\(GMT([+-])(\d{2}):?(\d{2})\)")


@dataclass(frozen=True)
class PlanMatch:
    workout_id: int
    planned_type: str | None
    planned_miles: float | None


def _zone_distribution(activity: Activity) -> dict[int, float]:
    zones = {
        1: float(activity.hr_zone_1 or 0.0),
        2: float(activity.hr_zone_2 or 0.0),
        3: float(activity.hr_zone_3 or 0.0),
        4: float(activity.hr_zone_4 or 0.0),
        5: float(activity.hr_zone_5 or 0.0),
    }
    total = sum(zones.values())
    if total <= 0:
        return zones
    return {zone_id: (value / total) * 100.0 for zone_id, value in zones.items()}


def _zone_metrics_for_type(
    distribution_pct: dict[int, float], run_type_key: str
) -> tuple[float, float, float]:
    definition = RUN_TYPE_DEFINITIONS[run_type_key]
    in_target = sum(distribution_pct.get(z, 0.0) for z in definition.target_zone_ids)
    pct_below = sum(
        distribution_pct.get(z, 0.0) for z in range(1, definition.acceptable_zone_min)
    )
    pct_above = sum(
        distribution_pct.get(z, 0.0)
        for z in range(definition.acceptable_zone_max + 1, 6)
    )
    return (round(in_target, 2), round(pct_above, 2), round(pct_below, 2))


def _score_candidate(
    run_type_key: str, in_target: float, pct_above: float, pct_below: float
) -> float:
    """
    Fitness score for executed-type selection.

    Above-zone deviation is weighted more heavily than below-zone.
    """
    definition = RUN_TYPE_DEFINITIONS[run_type_key]
    center_penalty = max(0.0, pct_above - pct_below) * 0.15
    duration_bias = 0.0
    if run_type_key == RUN_TYPE_LONG:
        duration_bias = 2.0
    if run_type_key == RUN_TYPE_EASY:
        duration_bias = 1.0
    return (
        in_target
        - (pct_above * 1.25)
        - (pct_below * 0.55)
        - center_penalty
        + duration_bias
    )


def _score_bucket(run_type_key: str, in_target: float, pct_above: float) -> str:
    profile = RUN_TYPE_DEFINITIONS[run_type_key].tolerance
    if profile is None:
        return "yellow"
    if (
        in_target >= profile.green_min_compliance
        and pct_above <= profile.green_max_above
    ):
        return "green"
    if (
        in_target >= profile.yellow_min_compliance
        and pct_above <= profile.yellow_max_above
    ):
        return "yellow"
    return "red"


def _apply_plan_alignment_penalty(
    *,
    planned_type: str | None,
    executed_type: str,
    base_score: str,
    per_type_metrics: dict[str, dict[str, float]],
) -> tuple[str, str | None]:
    """
    Penalize score when execution misses planned intent.

    Rules:
    - Matching planned/executed type: no penalty.
    - Mismatch + weak alignment to planned type => red.
    - Otherwise mismatch can be at most yellow.
    """
    if not planned_type or planned_type == executed_type:
        return base_score, None
    planned_metrics = per_type_metrics.get(planned_type)
    if not planned_metrics:
        return (
            "yellow" if base_score == "green" else base_score
        ), "mismatch_no_plan_metrics"

    profile = RUN_TYPE_DEFINITIONS[planned_type].tolerance
    if profile is None:
        return (
            "yellow" if base_score == "green" else base_score
        ), "mismatch_no_profile"

    planned_in_target = float(planned_metrics["zone_compliance_pct"])
    planned_above = float(planned_metrics["pct_above_zone"])
    if (
        planned_in_target < profile.yellow_min_compliance
        or planned_above > profile.yellow_max_above
    ):
        return "red", "mismatch_strong"
    if base_score == "green":
        return "yellow", "mismatch_moderate"
    return base_score, "mismatch_light"


def _derive_local_date(activity: Activity) -> date | None:
    if not activity.start_date:
        return None
    start_dt = activity.start_date
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

    tz_raw = (activity.timezone or "").strip()
    if not tz_raw:
        return start_dt.date()

    # Strava timezone strings are usually "(GMT-07:00) America/Denver"
    if ") " in tz_raw:
        maybe_name = tz_raw.split(") ", 1)[1].strip()
        if maybe_name:
            try:
                return start_dt.astimezone(ZoneInfo(maybe_name)).date()
            except Exception:
                pass

    offset_match = _GMT_OFFSET_RE.search(tz_raw)
    if not offset_match:
        return start_dt.date()

    sign = -1 if offset_match.group(1) == "-" else 1
    hours = int(offset_match.group(2))
    minutes = int(offset_match.group(3))
    total_minutes = sign * ((hours * 60) + minutes)
    local_dt = start_dt + timedelta(minutes=total_minutes)
    return local_dt.date()


def _match_plan_workout_sql(session: Session, activity_id: int) -> PlanMatch | None:
    row = session.execute(
        text(
            f"""
            SELECT pw.id AS workout_id, pw.run_type_key, pw.miles
            FROM activities a
            JOIN plans p
              ON p.user_id::text = a.user_id::text
             AND p.is_active = TRUE
            JOIN plan_workouts pw
              ON pw.plan_id = p.id
             AND pw.date = ({ACTIVITY_LOCAL_DATE_SQL_FRAGMENT})
            WHERE a.activity_id = :activity_id
              AND a.user_id IS NOT NULL
            ORDER BY pw.id DESC
            LIMIT 1
            """
        ),
        {"activity_id": int(activity_id)},
    ).fetchone()
    if not row:
        return None
    return PlanMatch(
        workout_id=int(row.workout_id),
        planned_type=normalize_run_type_key(row.run_type_key),
        planned_miles=float(row.miles) if row.miles is not None else None,
    )


def _match_plan_workout_sqlite(
    session: Session, activity: Activity
) -> PlanMatch | None:
    if not activity.user_id:
        return None

    local_date = _derive_local_date(activity)
    if local_date is None:
        return None

    active_plan_row = session.execute(
        text(
            """
            SELECT id
            FROM plans
            WHERE is_active = 1
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {},
    ).fetchone()
    if not active_plan_row:
        return None

    workout_row = session.execute(
        text(
            """
            SELECT id, run_type_key, miles
            FROM plan_workouts
            WHERE plan_id = :plan_id
              AND date = :local_date
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {
            "plan_id": int(active_plan_row.id),
            "local_date": local_date.isoformat(),
        },
    ).fetchone()
    if not workout_row:
        return None
    return PlanMatch(
        workout_id=int(workout_row.id),
        planned_type=normalize_run_type_key(workout_row.run_type_key),
        planned_miles=(
            float(workout_row.miles) if workout_row.miles is not None else None
        ),
    )


def match_plan_workout_for_activity(
    session: Session, activity: Activity
) -> PlanMatch | None:
    """
    Resolve the active plan workout that corresponds to this activity's local date.
    """
    dialect = session.bind.dialect.name if session.bind is not None else ""
    if dialect == "sqlite":
        return _match_plan_workout_sqlite(session, activity)
    return _match_plan_workout_sql(session, int(activity.activity_id))


def analyze_activity_execution(
    session: Session, activity: Activity, *, commit: bool = False
) -> dict[str, object] | None:
    """
    Analyze one activity and persist v1 scoring fields.
    """
    if not activity or activity.type != "Run":
        return None

    distribution_pct = _zone_distribution(activity)
    if sum(distribution_pct.values()) <= 0:
        return None

    match = match_plan_workout_for_activity(session, activity)
    planned_type = match.planned_type if match else None

    per_type_metrics: dict[str, dict[str, float]] = {}
    best_type: str | None = None
    best_fitness = float("-inf")

    for candidate in CANONICAL_RUN_TYPES:
        in_target, pct_above, pct_below = _zone_metrics_for_type(
            distribution_pct, candidate
        )
        fitness = _score_candidate(candidate, in_target, pct_above, pct_below)
        per_type_metrics[candidate] = {
            "zone_compliance_pct": round(in_target, 2),
            "pct_above_zone": round(pct_above, 2),
            "pct_below_zone": round(pct_below, 2),
            "fitness": round(fitness, 3),
        }
        if fitness > best_fitness:
            best_type = candidate
            best_fitness = fitness

    if not best_type:
        return None

    executed_type = best_type
    if planned_type and planned_type in per_type_metrics:
        # Keep planned intent when it's close to best-fit (reduces noisy type flips).
        planned_fit = float(per_type_metrics[planned_type]["fitness"])
        if (best_fitness - planned_fit) <= 6.0:
            executed_type = planned_type

    executed_metrics = per_type_metrics[executed_type]
    zone_compliance_pct = float(executed_metrics["zone_compliance_pct"])
    pct_above_zone = float(executed_metrics["pct_above_zone"])
    pct_below_zone = float(executed_metrics["pct_below_zone"])
    base_run_score = _score_bucket(executed_type, zone_compliance_pct, pct_above_zone)
    run_score, mismatch_reason = _apply_plan_alignment_penalty(
        planned_type=planned_type,
        executed_type=executed_type,
        base_score=base_run_score,
        per_type_metrics=per_type_metrics,
    )

    planned_miles = match.planned_miles if match else None
    actual_miles = (
        float(activity.conv_distance) if activity.conv_distance is not None else None
    )
    completion_pct = None
    if planned_miles and planned_miles > 0 and actual_miles is not None:
        completion_pct = round((actual_miles / planned_miles) * 100.0, 2)

    scoring_detail = {
        "schema_version": 1,
        "selection": {
            "planned_type": planned_type,
            "executed_type": executed_type,
            "chosen_by": "hr_zone_distribution",
            "base_score": base_run_score,
            "mismatch_penalty_reason": mismatch_reason,
        },
        "distribution_pct": {
            f"z{zid}": round(distribution_pct[zid], 2) for zid in (1, 2, 3, 4, 5)
        },
        "per_type_metrics": per_type_metrics,
    }

    activity.matched_plan_workout_id = match.workout_id if match else None
    activity.planned_type = planned_type
    activity.executed_type = executed_type
    activity.zone_compliance_pct = zone_compliance_pct
    activity.pct_above_zone = pct_above_zone
    activity.pct_below_zone = pct_below_zone
    activity.run_score = run_score
    activity.scoring_detail = scoring_detail
    activity.planned_miles = planned_miles
    activity.actual_miles = actual_miles
    activity.completion_pct = completion_pct

    if commit:
        session.commit()

    return {
        "activity_id": int(activity.activity_id),
        "executed_type": executed_type,
        "planned_type": planned_type,
        "run_score": run_score,
        "zone_compliance_pct": zone_compliance_pct,
    }


def analyze_recent_activity_window(
    session: Session,
    *,
    athlete_id: int,
    user_id: str | None,
    after_ts: int | None = None,
    before_ts: int | None = None,
    limit: int = 200,
) -> int:
    """
    Analyze recently synced activities and persist execution metrics.
    """
    if not user_id:
        return 0

    query = session.query(Activity).filter(
        and_(Activity.athlete_id == athlete_id, Activity.type == "Run")
    )

    if after_ts is not None:
        query = query.filter(
            Activity.start_date >= datetime.fromtimestamp(after_ts, tz=timezone.utc)
        )
    if before_ts is not None:
        query = query.filter(
            Activity.start_date <= datetime.fromtimestamp(before_ts, tz=timezone.utc)
        )

    runs = query.order_by(Activity.start_date.desc()).limit(max(1, int(limit))).all()
    updated = 0
    for run in runs:
        result = analyze_activity_execution(session, run, commit=False)
        if result is not None:
            updated += 1

    if updated:
        session.commit()
        logger.info(
            "Run execution analysis updated %s run(s) for athlete=%s user_id=%s",
            updated,
            athlete_id,
            str(user_id),
        )
    return updated

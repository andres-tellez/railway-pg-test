"""
Training KPI Service

Queries ``activities`` execution columns and aggregates per-run KPIs into weekly
summaries with trend analysis. Coach tools read persisted Tier 2 facts only —
the LLM never computes KPIs itself.
"""

from __future__ import annotations

import logging
from datetime import date as date_cls, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Date, Integer, bindparam, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.db_helpers import get_primary_athlete_id
from src.smartcoach_mobile_coach.display_format import (
    format_distance_mi,
    format_pace_sec_per_mi,
)
from src.smartcoach_mobile_coach.runner_profile.service import get_runner_profile
from src.utils.hr_zone_constants import (
    hr_drift_band_from_pct,
    hr_drift_band_zones_chart,
)

logger = logging.getLogger("smartcoach_mobile_coach")

_ACTIVITY_DATE_SQL = "activity_local_date(a.start_date, a.timezone)::date"


def _pct_fraction_to_display(frac: Optional[float]) -> Optional[str]:
    if frac is None:
        return None
    try:
        v = float(frac)
    except (TypeError, ValueError):
        return None
    return f"{int(round(v * 100.0))}%"


_WEEKLY_RUNS_CTE = f"""
WITH user_runs AS (
    SELECT
        a.activity_id,
        a.name AS activity_name,
        to_char({_ACTIVITY_DATE_SQL}, 'YYYY-MM-DD') AS activity_date,
        a.type AS activity_type,
        a.conv_distance AS distance_miles,
        a.moving_time AS moving_time_seconds,
        a.average_heartrate AS avg_hr,
        a.conv_avg_speed AS avg_pace,
        a.insights_system,
        a.easy_pct,
        a.z2_band_pct,
        a.hr_drift_pct,
        a.pace_spread,
        a.start_date,
        {_ACTIVITY_DATE_SQL} AS activity_local_date
    FROM public.activities a
    WHERE a.user_id = CAST(:uid AS uuid)
      AND a.athlete_id = :athlete_id
      AND a.type = 'Run'
"""

_WEEKLY_SUMMARY_SQL = (
    _WEEKLY_RUNS_CTE
    + """
      AND a.start_date >= (now() - make_interval(weeks => :weeks))
),
weekly AS (
    SELECT
        to_char(start_date, 'IYYY-IW') AS iso_week,
        (date_trunc('week', MIN(start_date::timestamp))::date) AS week_monday,
        MIN(activity_date)              AS week_start_date,
        COUNT(*)                        AS total_runs,
        COUNT(*) FILTER (WHERE insights_system = 'easy') AS easy_runs,
        ROUND(SUM(distance_miles)::numeric, 1)              AS total_miles,
        MAX(distance_miles)                                  AS longest_run_miles,
        MAX(moving_time_seconds)                             AS longest_run_seconds,
        ROUND(AVG(avg_pace) FILTER (WHERE insights_system = 'easy')::numeric, 2) AS avg_z2_pace,
        ROUND(AVG(hr_drift_pct) FILTER (WHERE insights_system = 'easy')::numeric, 2) AS avg_drift,
        ROUND(AVG(z2_band_pct) FILTER (WHERE insights_system = 'easy')::numeric, 2)  AS avg_z2_adherence,
        ROUND(AVG(pace_spread) FILTER (WHERE insights_system = 'easy')::numeric, 2)  AS avg_pace_spread,
        ROUND(
            MIN(hr_drift_pct) FILTER (
                WHERE insights_system = 'easy' AND moving_time_seconds >= 5400
            )::numeric, 2
        ) AS long_run_best_drift
    FROM user_runs
    GROUP BY to_char(start_date, 'IYYY-IW')
    ORDER BY iso_week DESC
)
SELECT * FROM weekly
"""
)

_WEEKLY_SUMMARY_RANGE_SQL = (
    _WEEKLY_RUNS_CTE
    + """
      AND activity_local_date >= :start_date_from
      AND activity_local_date <= :start_date_to
),
weekly AS (
    SELECT
        to_char(activity_local_date, 'IYYY-IW') AS iso_week,
        (date_trunc('week', MIN(activity_local_date)::timestamp))::date AS week_monday,
        MIN(activity_date)                    AS week_start_date,
        COUNT(*)                        AS total_runs,
        COUNT(*) FILTER (WHERE insights_system = 'easy') AS easy_runs,
        ROUND(SUM(distance_miles)::numeric, 1)              AS total_miles,
        MAX(distance_miles)                                  AS longest_run_miles,
        MAX(moving_time_seconds)                             AS longest_run_seconds,
        ROUND(AVG(avg_pace) FILTER (WHERE insights_system = 'easy')::numeric, 2) AS avg_z2_pace,
        ROUND(AVG(hr_drift_pct) FILTER (WHERE insights_system = 'easy')::numeric, 2) AS avg_drift,
        ROUND(AVG(z2_band_pct) FILTER (WHERE insights_system = 'easy')::numeric, 2)  AS avg_z2_adherence,
        ROUND(AVG(pace_spread) FILTER (WHERE insights_system = 'easy')::numeric, 2)  AS avg_pace_spread,
        ROUND(
            MIN(hr_drift_pct) FILTER (
                WHERE insights_system = 'easy' AND moving_time_seconds >= 5400
            )::numeric, 2
        ) AS long_run_best_drift
    FROM user_runs
    GROUP BY to_char(activity_local_date, 'IYYY-IW')
    ORDER BY iso_week DESC
)
SELECT * FROM weekly
"""
)

_RUN_KPI_SQL = f"""
SELECT
    a.activity_id,
    a.name AS activity_name,
    to_char({_ACTIVITY_DATE_SQL}, 'YYYY-MM-DD') AS activity_date,
    a.type AS activity_type,
    a.conv_distance AS distance_miles,
    a.moving_time AS moving_time_seconds,
    a.average_heartrate AS avg_hr,
    a.conv_avg_speed AS avg_pace,
    a.insights_system,
    a.easy_pct,
    a.z2_band_pct,
    a.hr_drift_pct,
    a.pace_spread,
    a.execution_compute_status
FROM public.activities a
WHERE a.activity_id = :aid
  AND a.user_id = CAST(:uid AS uuid)
  AND a.athlete_id = :athlete_id
"""


def _trend_direction(values: List[Optional[float]], lower_is_better: bool) -> str:
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return "insufficient_data"
    recent = clean[-1]
    prior_avg = sum(clean[:-1]) / len(clean[:-1])
    if prior_avg == 0:
        return "stable"
    pct_change = (recent - prior_avg) / abs(prior_avg) * 100
    threshold = 3.0
    if abs(pct_change) < threshold:
        return "stable"
    if lower_is_better:
        return "improving" if pct_change < 0 else "declining"
    return "improving" if pct_change > 0 else "declining"


def _format_weekly_row(row) -> Dict[str, Any]:
    avg_pace_raw = float(row.avg_z2_pace) if row.avg_z2_pace is not None else None
    total_miles_val = float(row.total_miles) if row.total_miles else 0.0
    longest_run_miles_val = (
        float(row.longest_run_miles) if row.longest_run_miles else 0.0
    )
    week_monday = getattr(row, "week_monday", None)
    week_label = None
    week_monday_iso = None
    if week_monday is not None:
        try:
            if isinstance(week_monday, date_cls):
                d = week_monday
            else:
                d = datetime.strptime(str(week_monday)[:10], "%Y-%m-%d").date()
            week_label = f"Wk {d.month}/{d.day}"
            week_monday_iso = d.isoformat()
        except (ValueError, TypeError):
            week_label = None
            week_monday_iso = None

    return {
        "iso_week": row.iso_week,
        "week_monday": week_monday_iso,
        "week_label": week_label,
        "week_start_date": row.week_start_date,
        "total_runs": row.total_runs,
        "easy_runs": row.easy_runs,
        "total_miles": total_miles_val,
        "longest_run_miles": longest_run_miles_val,
        "total_mi_display": format_distance_mi(total_miles_val),
        "longest_mi_display": format_distance_mi(longest_run_miles_val),
        "avg_z2_pace_raw": avg_pace_raw,
        "avg_z2_pace_display": (
            format_pace_sec_per_mi(avg_pace_raw * 60) if avg_pace_raw else "—"
        ),
        "avg_drift_pct": (float(row.avg_drift) if row.avg_drift is not None else None),
        "avg_z2_adherence": (
            float(row.avg_z2_adherence) if row.avg_z2_adherence is not None else None
        ),
        "avg_z2_adherence_display": _pct_fraction_to_display(
            float(row.avg_z2_adherence) if row.avg_z2_adherence is not None else None
        ),
        "avg_pace_spread": (
            float(row.avg_pace_spread) if row.avg_pace_spread is not None else None
        ),
        "long_run_best_drift": (
            float(row.long_run_best_drift)
            if row.long_run_best_drift is not None
            else None
        ),
    }


def get_training_progress(
    session: Session,
    user_id: str,
    weeks: int = 4,
    *,
    start_date_from: Optional[date_cls] = None,
    start_date_to: Optional[date_cls] = None,
) -> Dict[str, Any]:
    weeks = max(1, min(weeks, 52))
    using_explicit_window = start_date_from is not None or start_date_to is not None
    if using_explicit_window and (start_date_from is None or start_date_to is None):
        return {
            "error": "missing_dates",
            "message": (
                "start_date_from and start_date_to must both be provided as YYYY-MM-DD "
                "when using an explicit calendar window."
            ),
        }
    if (
        start_date_from is not None
        and start_date_to is not None
        and start_date_from > start_date_to
    ):
        return {
            "error": "invalid_date_range",
            "message": "start_date_from must be on or before start_date_to.",
        }

    athlete_id = get_primary_athlete_id(session, str(user_id))
    if athlete_id is None:
        return {
            "error": "no_athlete",
            "message": "No linked Strava athlete for KPI summaries.",
            "weekly_summaries": [],
            "trends": {},
            "hr_drift_band_zones": hr_drift_band_zones_chart(),
        }

    if start_date_from is not None and start_date_to is not None:
        stmt = text(_WEEKLY_SUMMARY_RANGE_SQL).bindparams(
            bindparam("uid", type_=PGUUID),
            bindparam("athlete_id", type_=Integer),
            bindparam("start_date_from", type_=Date()),
            bindparam("start_date_to", type_=Date()),
        )
        rows = session.execute(
            stmt,
            {
                "uid": user_id,
                "athlete_id": athlete_id,
                "start_date_from": start_date_from,
                "start_date_to": start_date_to,
            },
        ).fetchall()
    else:
        stmt = text(_WEEKLY_SUMMARY_SQL).bindparams(
            bindparam("uid", type_=PGUUID),
            bindparam("athlete_id", type_=Integer),
        )
        rows = session.execute(
            stmt, {"uid": user_id, "athlete_id": athlete_id, "weeks": weeks}
        ).fetchall()

    if not rows:
        out = {
            "weeks_requested": weeks,
            "weekly_summaries": [],
            "trends": {},
            "message": "No run data found for this period.",
            "hr_drift_band_zones": hr_drift_band_zones_chart(),
        }
        if start_date_from is not None and start_date_to is not None:
            out["window"] = {
                "start_date_inclusive": start_date_from.isoformat(),
                "end_date_inclusive": start_date_to.isoformat(),
                "basis": "activity_local_date",
            }
        return out

    summaries = [_format_weekly_row(r) for r in rows]
    summaries_chrono = list(reversed(summaries))

    trends = {
        "z2_pace": _trend_direction(
            [w["avg_z2_pace_raw"] for w in summaries_chrono],
            lower_is_better=True,
        ),
        "hr_drift": _trend_direction(
            [w["avg_drift_pct"] for w in summaries_chrono],
            lower_is_better=True,
        ),
        "z2_adherence": _trend_direction(
            [w["avg_z2_adherence"] for w in summaries_chrono],
            lower_is_better=False,
        ),
        "weekly_miles": _trend_direction(
            [w["total_miles"] for w in summaries_chrono],
            lower_is_better=False,
        ),
    }

    total_easy = sum(w["easy_runs"] for w in summaries)
    total_runs = sum(w["total_runs"] for w in summaries)
    total_weekly_miles = round(sum(w["total_miles"] for w in summaries), 2)

    out = {
        "weeks_requested": weeks,
        "weeks_with_data": len(summaries),
        "total_runs": total_runs,
        "total_easy_runs": total_easy,
        "weekly_summaries": summaries,
        "sum_weekly_total_miles": total_weekly_miles,
        "sum_weekly_total_mi_display": format_distance_mi(total_weekly_miles),
        "weekly_summaries_scope": (
            "Each row is one ISO week (Monday–Sunday). Use **week_label** (Monday M/D) when listing a week. "
            "**iso_week** is the canonical id. **week_start_date** is the first run in that week, not the Monday. "
            "Counts and miles use **activities** execution columns for the user's **primary linked Strava athlete only** "
            "(same athlete_id as aggregate_runs_in_range), not other Strava accounts that may share this login. "
            "Not every Strava activity. Compare against aggregate_runs_in_range when the same calendar window is provided."
        ),
        "trends": trends,
        "hr_drift_band_zones": hr_drift_band_zones_chart(),
    }
    if start_date_from is not None and start_date_to is not None:
        out["window"] = {
            "start_date_inclusive": start_date_from.isoformat(),
            "end_date_inclusive": start_date_to.isoformat(),
            "basis": "activity_local_date",
        }
    return out


def get_run_kpi_detail(
    session: Session, user_id: str, activity_id: int
) -> Dict[str, Any]:
    athlete_id = get_primary_athlete_id(session, str(user_id))
    if athlete_id is None:
        return {"error": "no_athlete", "message": "No linked Strava athlete."}

    stmt = text(_RUN_KPI_SQL).bindparams(
        bindparam("uid", type_=PGUUID),
        bindparam("athlete_id", type_=Integer),
    )
    row = session.execute(
        stmt, {"uid": user_id, "aid": activity_id, "athlete_id": athlete_id}
    ).fetchone()

    if not row:
        return {"error": "not_found", "message": "Run not found."}

    profile = get_runner_profile(session, user_id)
    z2_low = float(profile.hr_z2.low) if profile and profile.hr_z2 else None
    z2_high = float(profile.hr_z2.high) if profile and profile.hr_z2 else None
    zone_method = profile.zone_method if profile else None

    avg_pace_raw = float(row.avg_pace) if row.avg_pace is not None else None
    drift_pct = (
        round(float(row.hr_drift_pct), 2) if row.hr_drift_pct is not None else None
    )
    drift_band = hr_drift_band_from_pct(
        float(row.hr_drift_pct) if row.hr_drift_pct is not None else None
    )
    drift_summary = (
        f"![HR drift: {drift_pct}%](kpi-band://{drift_band})"
        if drift_pct is not None and drift_band
        else None
    )

    return {
        "activity_id": int(row.activity_id),
        "activity_name": row.activity_name,
        "activity_date": row.activity_date,
        "distance_display": format_distance_mi(
            float(row.distance_miles) if row.distance_miles else 0
        ),
        "avg_hr": float(row.avg_hr) if row.avg_hr is not None else None,
        "avg_pace_display": (
            format_pace_sec_per_mi(avg_pace_raw * 60) if avg_pace_raw else "—"
        ),
        "zone_bounds": {
            "z2_low": z2_low,
            "z2_high": z2_high,
            "method": zone_method,
        },
        "kpis": {
            "easy_pct": (
                round(float(row.easy_pct), 2) if row.easy_pct is not None else None
            ),
            "z2_band_pct": (
                round(float(row.z2_band_pct), 2)
                if row.z2_band_pct is not None
                else None
            ),
            "easy_pct_display": _pct_fraction_to_display(
                float(row.easy_pct) if row.easy_pct is not None else None
            ),
            "z2_band_pct_display": _pct_fraction_to_display(
                float(row.z2_band_pct) if row.z2_band_pct is not None else None
            ),
            "hr_drift_pct": drift_pct,
            "hr_drift_band": drift_band,
            "hr_drift_summary_display": drift_summary,
            "pace_spread": (
                round(float(row.pace_spread), 2)
                if row.pace_spread is not None
                else None
            ),
        },
        "insights_system": row.insights_system,
        "is_easy_run": row.insights_system == "easy",
        "execution_compute_status": row.execution_compute_status,
    }

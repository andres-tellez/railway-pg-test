"""
Training KPI Service

Queries v_easy_runs view and aggregates per-run KPIs into weekly summaries
with trend analysis. This service is the ONLY source of training KPI data
for coach tools — the LLM never computes KPIs itself.

All numeric thresholds come from hr_zone_constants.py.
"""

from __future__ import annotations

import logging
from datetime import date as date_cls, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.display_format import (
    format_distance_mi,
    format_pace_sec_per_mi,
)
from src.utils.hr_zone_constants import (
    hr_drift_band_from_pct,
    hr_drift_band_zones_chart,
)

logger = logging.getLogger("smartcoach_mobile_coach")


def _pct_fraction_to_display(frac: Optional[float]) -> Optional[str]:
    """Format v_easy_runs fraction columns (0..1) as a whole-percent string."""
    if frac is None:
        return None
    try:
        v = float(frac)
    except (TypeError, ValueError):
        return None
    return f"{int(round(v * 100.0))}%"


_WEEKLY_SUMMARY_SQL = """
WITH user_easy AS (
    SELECT *
    FROM v_easy_runs
    WHERE user_id = :uid
      AND activity_type = 'Run'
      AND start_date >= (now() - make_interval(weeks => :weeks))
),
weekly AS (
    SELECT
        to_char(start_date, 'IYYY-IW') AS iso_week,
        (date_trunc('week', MIN(start_date::timestamp))::date) AS week_monday,
        MIN(activity_date)              AS week_start_date,
        COUNT(*)                        AS total_runs,
        COUNT(*) FILTER (WHERE is_easy_run) AS easy_runs,
        ROUND(SUM(distance_miles)::numeric, 1)              AS total_miles,
        MAX(distance_miles)                                  AS longest_run_miles,
        MAX(moving_time_seconds)                             AS longest_run_seconds,
        ROUND(AVG(avg_pace) FILTER (WHERE is_easy_run)::numeric, 2) AS avg_z2_pace,
        ROUND(AVG(hr_drift_pct) FILTER (WHERE is_easy_run)::numeric, 2) AS avg_drift,
        ROUND(AVG(z2_band_pct) FILTER (WHERE is_easy_run)::numeric, 2)  AS avg_z2_adherence,
        ROUND(AVG(pace_spread) FILTER (WHERE is_easy_run)::numeric, 2)  AS avg_pace_spread,
        ROUND(
            MIN(hr_drift_pct) FILTER (
                WHERE is_easy_run AND moving_time_seconds >= 5400
            )::numeric, 2
        ) AS long_run_best_drift
    FROM user_easy
    GROUP BY to_char(start_date, 'IYYY-IW')
    ORDER BY iso_week DESC
)
SELECT * FROM weekly
"""

_RUN_KPI_SQL = """
SELECT
    activity_id,
    activity_name,
    activity_date,
    activity_type,
    distance_miles,
    moving_time_seconds,
    avg_hr,
    avg_pace,
    z2_low,
    z2_high,
    zone_method,
    total_splits,
    easy_pct,
    z2_band_pct,
    hr_drift_pct,
    early_hr,
    late_hr,
    peak_split_hr,
    fastest_split_pace,
    slowest_split_pace,
    pace_spread,
    is_easy_run
FROM v_easy_runs
WHERE activity_id = :aid
  AND user_id = :uid
"""


def _trend_direction(values: List[Optional[float]], lower_is_better: bool) -> str:
    """Determine trend from a time-ordered list (oldest first)."""
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
    session: Session, user_id: str, weeks: int = 4
) -> Dict[str, Any]:
    """
    Weekly KPI summaries + trend analysis for the coach tool.

    Returns structured data the LLM interprets, including `*_display` fields
    for pace, weekly distance (mi), and Z2 adherence where available.
    """
    weeks = max(1, min(weeks, 52))

    stmt = text(_WEEKLY_SUMMARY_SQL).bindparams(bindparam("uid", type_=PGUUID))
    rows = session.execute(stmt, {"uid": user_id, "weeks": weeks}).fetchall()

    if not rows:
        return {
            "weeks_requested": weeks,
            "weekly_summaries": [],
            "trends": {},
            "message": "No run data found for this period.",
            "hr_drift_band_zones": hr_drift_band_zones_chart(),
        }

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

    return {
        "weeks_requested": weeks,
        "weeks_with_data": len(summaries),
        "total_runs": total_runs,
        "total_easy_runs": total_easy,
        "weekly_summaries": summaries,
        "weekly_summaries_scope": (
            "Each row is one ISO week (Monday–Sunday). Use **week_label** (Monday M/D) when listing a week. "
            "**iso_week** is the canonical id. **week_start_date** is the first run in that week, not the Monday. "
            "Counts and miles are from **v_easy_runs** only (easy-classified runs), not every Strava activity."
        ),
        "trends": trends,
        "hr_drift_band_zones": hr_drift_band_zones_chart(),
    }


def get_run_kpi_detail(
    session: Session, user_id: str, activity_id: int
) -> Dict[str, Any]:
    """
    Z2 KPI detail for a single run. Complements run_insight facts
    with training-specific metrics. Includes HR drift %, band (green/yellow/orange/red),
    and hr_drift_summary_display aligned with Weekly Insights thresholds.
    """
    stmt = text(_RUN_KPI_SQL).bindparams(bindparam("uid", type_=PGUUID))
    row = session.execute(stmt, {"uid": user_id, "aid": activity_id}).fetchone()

    if not row:
        return {"error": "not_found", "message": "Run not found in KPI view."}

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
            "z2_low": float(row.z2_low) if row.z2_low is not None else None,
            "z2_high": float(row.z2_high) if row.z2_high is not None else None,
            "method": row.zone_method,
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
            "early_hr": (
                round(float(row.early_hr), 1) if row.early_hr is not None else None
            ),
            "late_hr": (
                round(float(row.late_hr), 1) if row.late_hr is not None else None
            ),
            "peak_split_hr": (
                round(float(row.peak_split_hr), 1)
                if row.peak_split_hr is not None
                else None
            ),
            "pace_spread": (
                round(float(row.pace_spread), 2)
                if row.pace_spread is not None
                else None
            ),
        },
        "is_easy_run": bool(row.is_easy_run),
    }

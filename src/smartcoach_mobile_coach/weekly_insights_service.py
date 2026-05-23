"""
Weekly Training Insights Service

Computes deterministic KPI bands, overall score, and deltas. Numeric truth
is computed in SQL + Python; weekly rows store metrics for the mobile
Insights charts (no LLM copy).

Tempo / ``threshold`` run detection uses the same week window as easy runs
but classifies ``threshold`` when easy_pct is low (not an easy day) and
either (a) activity avg HR is above Z2 high, or (b) split-majority or
post-warmup median split HR is above Z2 high — so mixed warmup + quality
miles still count.

``get_latest_weekly_insight(..., slim=True)`` returns an orientation-only dict
for the coach tool (week + ``overall_band``); REST uses ``slim=False`` (full).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from sqlalchemy import Integer, bindparam, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.db_helpers import get_primary_athlete_id
from src.smartcoach_mobile_coach.display_format import format_pace_sec_per_mi
from src.utils.hr_zone_constants import (
    aerobic_efficiency_band_from_value,
    aerobic_efficiency_band_zones_chart,
    hr_drift_band_zones_chart,
    OVERALL_SCORE_RULES,
    TREND_BAND_THRESHOLDS,
    hr_drift_band_from_pct,
)

logger = logging.getLogger("smartcoach_mobile_coach")

# Coach tool default: orientation-only payload (week + overall_band) unless
# include_kpi_detail=true. REST `/api/training-insights/weekly` always uses slim=False.
WEEKLY_INSIGHT_ORIENTATION_NOTE = (
    "Orientation-only: week range + overall_band. Do not invent HR drift %, Z2 pace, "
    "easy average HR, efficiency, deltas, or zone thresholds. Call get_weekly_training_insight again with "
    "include_kpi_detail=true (or use get_training_kpis) when the user asks for KPI numbers "
    "or band definitions."
)


def weekly_insight_tool_slim_default_from_env() -> bool:
    raw = (os.getenv("SMARTCOACH_WEEKLY_INSIGHT_TOOL_SLIM") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


# Threshold / tempo classification (see _WEEK_KPIS_SQL):
# - Legacy: activity avg HR strictly above Z2 ceiling (Strava aggregate).
# - Primary fix: split-majority — enough laps with HR, and ≥ half of those laps
#   above Z2 high, OR median HR on laps after split 1 above Z2 high (warmup lap).
THRESHOLD_MIN_SPLITS_WITH_HR = 3
THRESHOLD_MIN_FRACTION_SPLITS_ABOVE_Z2_HIGH = 0.5

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_WEEK_KPIS_SQL = """
WITH week_runs AS (
    SELECT
        v.*
    FROM v_easy_runs v
    INNER JOIN public.activities a ON a.activity_id = v.activity_id
    WHERE v.user_id = :uid
      AND a.athlete_id = :athlete_id
      AND v.activity_date >= :ws
      AND v.activity_date <= :we
      AND v.activity_type = 'Run'
),
split_stats AS (
    SELECT
        wr.activity_id,
        COUNT(s.split) FILTER (WHERE s.average_heartrate IS NOT NULL) AS n_hr_splits,
        COUNT(s.split) FILTER (
            WHERE wr.z2_high IS NOT NULL
              AND s.average_heartrate IS NOT NULL
              AND s.average_heartrate > wr.z2_high
        ) AS n_above_ceiling
    FROM week_runs wr
    INNER JOIN splits s ON s.activity_id = wr.activity_id
    GROUP BY wr.activity_id
),
split_median_after_warmup AS (
    SELECT
        wr.activity_id,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY s.average_heartrate) AS median_hr_after_split_1
    FROM week_runs wr
    INNER JOIN splits s ON s.activity_id = wr.activity_id
    WHERE s.split > 1
      AND s.average_heartrate IS NOT NULL
    GROUP BY wr.activity_id
),
classified_runs AS (
    SELECT
        wr.*,
        CASE
            WHEN wr.is_easy_run THEN 'easy'
            WHEN (
                wr.moving_time_seconds >= 1800
                AND wr.z2_high IS NOT NULL
                AND wr.easy_pct IS NOT NULL
                AND wr.easy_pct < 0.70
                AND (
                    (wr.avg_hr IS NOT NULL AND wr.avg_hr > wr.z2_high)
                    OR (
                        COALESCE(ss.n_hr_splits, 0) >= {min_splits_hr}
                        AND (
                            (ss.n_above_ceiling::numeric
                                / NULLIF(ss.n_hr_splits, 0))
                                >= {min_frac_above_z2}
                            OR (
                                mw.median_hr_after_split_1 IS NOT NULL
                                AND mw.median_hr_after_split_1 > wr.z2_high
                            )
                        )
                    )
                )
            ) THEN 'threshold'
            ELSE NULL
        END AS training_system
    FROM week_runs wr
    LEFT JOIN split_stats ss ON ss.activity_id = wr.activity_id
    LEFT JOIN split_median_after_warmup mw ON mw.activity_id = wr.activity_id
)
SELECT
    COUNT(*) AS total_runs,
    COUNT(*) FILTER (WHERE training_system = 'easy')                   AS easy_runs,
    COUNT(*) FILTER (WHERE training_system = 'threshold')              AS threshold_runs,
    ROUND(AVG(hr_drift_pct) FILTER (WHERE training_system = 'easy')::numeric, 2)  AS avg_drift,
    ROUND(AVG(avg_pace)     FILTER (WHERE training_system = 'easy')::numeric, 4)  AS avg_pace,
    ROUND(AVG(avg_pace)     FILTER (WHERE training_system = 'threshold')::numeric, 4) AS avg_threshold_pace,
    ROUND(AVG(avg_hr)       FILTER (WHERE training_system = 'easy')::numeric, 1)  AS avg_hr,
    ROUND(AVG(easy_pct)     FILTER (WHERE training_system = 'easy')::numeric, 2)  AS avg_easy_pct,
    ROUND(AVG(z2_band_pct)  FILTER (WHERE training_system = 'easy')::numeric, 2)  AS avg_z2_adherence,
    ROUND(
        (
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (late_hr - early_hr))
            FILTER (
                WHERE training_system = 'threshold'
                  AND early_hr IS NOT NULL
                  AND late_hr IS NOT NULL
            )
        )::numeric,
        2
    ) AS avg_threshold_effort_stability
FROM classified_runs
""".format(
    min_splits_hr=THRESHOLD_MIN_SPLITS_WITH_HR,
    min_frac_above_z2=THRESHOLD_MIN_FRACTION_SPLITS_ABOVE_Z2_HIGH,
)

_USERS_WITH_EASY_RUNS_SQL = """
WITH classified_runs AS (
    SELECT
        v.user_id,
        v.activity_date,
        CASE
            WHEN v.is_easy_run THEN 'easy'
            ELSE NULL
        END AS training_system
    FROM v_easy_runs v
    INNER JOIN public.activities a ON a.activity_id = v.activity_id
    INNER JOIN public.user_athletes ua
        ON ua.user_id = v.user_id AND a.athlete_id = ua.athlete_id
)
SELECT DISTINCT user_id
FROM classified_runs
WHERE training_system = 'easy'
  AND activity_date >= :ws
  AND activity_date <= :we
"""


class TrainingSystem(str, Enum):
    EASY = "easy"
    THRESHOLD = "threshold"
    SPEED = "speed"


# ---------------------------------------------------------------------------
# Band computations (deterministic — no LLM involvement)
# ---------------------------------------------------------------------------


def _hr_drift_band(value: Optional[float]) -> Optional[str]:
    return hr_drift_band_from_pct(value)


def _trend_band(
    current: Optional[float], prior: Optional[float], lower_is_better: bool
) -> Optional[str]:
    """Band based on % change vs prior week. Returns None if insufficient data."""
    if current is None or prior is None or prior == 0:
        return None
    pct_change = ((current - prior) / abs(prior)) * 100
    if lower_is_better:
        worse_pct = pct_change
    else:
        worse_pct = -pct_change

    if worse_pct <= TREND_BAND_THRESHOLDS["green_max_worse_pct"]:
        return "green"
    if worse_pct <= TREND_BAND_THRESHOLDS["yellow_max_worse_pct"]:
        return "yellow"
    if worse_pct <= TREND_BAND_THRESHOLDS["orange_max_worse_pct"]:
        return "orange"
    return "red"


def _compute_efficiency(
    avg_pace_min_per_mi: Optional[float], avg_hr: Optional[float]
) -> Optional[float]:
    """Aerobic efficiency = speed_mph / avg_hr * 100 (mi/hr per 100 heartbeats)."""
    if not avg_pace_min_per_mi or avg_pace_min_per_mi <= 0 or not avg_hr or avg_hr <= 0:
        return None
    speed_mph = 60.0 / avg_pace_min_per_mi
    return round(speed_mph / avg_hr * 100, 2)


def _compute_delta(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    if current is None or prior is None:
        return None
    return round(current - prior, 2)


_BAND_SEVERITY = {"green": 0, "yellow": 1, "orange": 2, "red": 3}


def _compute_overall_band(
    bands: List[Optional[str]],
    prior_bands: Optional[Dict[str, Optional[str]]],
    prior_overall: Optional[str],
) -> str:
    """
    Worst-of KPI trend / absolute bands with 2-week persistence:
    - all green → green
    - any red (single week) → yellow (softened)
    - same KPI red for 2+ consecutive weeks → red
    """
    active = [b for b in bands if b is not None]
    if not active:
        return "green"

    worst = max(active, key=lambda b: _BAND_SEVERITY.get(b, 0))

    if worst != "red":
        return worst

    threshold = OVERALL_SCORE_RULES["consecutive_red_weeks_for_overall_red"]
    if threshold <= 1:
        return "red"

    if prior_bands:
        prior_values = [v for v in prior_bands.values() if v is not None]
        if any(v == "red" for v in prior_values):
            return "red"

    return "yellow"


# ---------------------------------------------------------------------------
# Weekly KPI query
# ---------------------------------------------------------------------------


def _week_bounds(ref_date: date) -> Tuple[date, date]:
    """Monday–Sunday week containing ref_date, or the most recent completed week."""
    dow = ref_date.weekday()
    monday = ref_date - timedelta(days=dow)
    sunday = monday + timedelta(days=6)
    if sunday >= ref_date:
        monday -= timedelta(weeks=1)
        sunday -= timedelta(weeks=1)
    return monday, sunday


def calendar_week_containing(d: date) -> Tuple[date, date]:
    """Monday–Sunday **calendar** week that contains ``d`` (both ends inclusive)."""
    dow = d.weekday()
    monday = d - timedelta(days=dow)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def last_completed_week_bounds(today: Optional[date] = None) -> Tuple[date, date]:
    """
    Monday–Sunday training week to report for Sunday-evening cron / batch jobs.

    On Sunday, that is the Mon–Sun window ending today. On Monday–Saturday,
    the most recently finished Mon–Sun week (ended last Sunday).
    """
    if today is None:
        today = date.today()
    dow = today.weekday()
    if dow == 6:  # Sunday — week closes today
        week_end = today
        week_start = today - timedelta(days=6)
        return week_start, week_end
    this_monday = today - timedelta(days=dow)
    week_end = this_monday - timedelta(days=1)
    week_start = week_end - timedelta(days=6)
    return week_start, week_end


def _fetch_week_kpis(
    session: Session,
    user_id: str,
    week_start: date,
    week_end: date,
    athlete_id: int,
) -> Dict[str, Any]:
    stmt = text(_WEEK_KPIS_SQL).bindparams(
        bindparam("uid", type_=PGUUID),
        bindparam("athlete_id", type_=Integer),
    )
    row = session.execute(
        stmt,
        {
            "uid": user_id,
            "athlete_id": athlete_id,
            "ws": str(week_start),
            "we": str(week_end),
        },
    ).fetchone()

    if not row:
        return {
            "easy_run_count": 0,
            "threshold_run_count": 0,
            "total_run_count": 0,
            "effort_stability_min_per_mi": None,
            "threshold_pace_min_per_mi": None,
        }

    avg_pace = float(row.avg_pace) if row.avg_pace is not None else None
    avg_hr = float(row.avg_hr) if row.avg_hr is not None else None
    threshold_effort_stability = (
        float(row.avg_threshold_effort_stability)
        if row.avg_threshold_effort_stability is not None
        else None
    )
    threshold_pace = (
        float(row.avg_threshold_pace) if row.avg_threshold_pace is not None else None
    )

    return {
        "easy_run_count": int(row.easy_runs or 0),
        "threshold_run_count": int(row.threshold_runs or 0),
        "total_run_count": int(row.total_runs),
        "hr_drift_pct": float(row.avg_drift) if row.avg_drift is not None else None,
        "z2_pace_min_per_mi": avg_pace,
        "avg_hr": avg_hr,
        "efficiency": _compute_efficiency(avg_pace, avg_hr),
        "effort_stability_min_per_mi": threshold_effort_stability,
        "threshold_pace_min_per_mi": threshold_pace,
        "avg_easy_pct": (
            float(row.avg_easy_pct) if row.avg_easy_pct is not None else None
        ),
        "avg_z2_adherence": (
            float(row.avg_z2_adherence) if row.avg_z2_adherence is not None else None
        ),
    }


def _fetch_week_kpis_by_system(
    session: Session,
    user_id: str,
    week_start: date,
    week_end: date,
    athlete_id: int,
) -> Dict[TrainingSystem, Dict[str, Any]]:
    """Fetch weekly KPI inputs for all systems. EASY + THRESHOLD are implemented."""
    weekly = _fetch_week_kpis(session, user_id, week_start, week_end, athlete_id)
    return {
        TrainingSystem.EASY: {
            "easy_run_count": weekly.get("easy_run_count", 0),
            "total_run_count": weekly.get("total_run_count", 0),
            "hr_drift_pct": weekly.get("hr_drift_pct"),
            "z2_pace_min_per_mi": weekly.get("z2_pace_min_per_mi"),
            "avg_hr": weekly.get("avg_hr"),
            "efficiency": weekly.get("efficiency"),
            "avg_easy_pct": weekly.get("avg_easy_pct"),
            "avg_z2_adherence": weekly.get("avg_z2_adherence"),
        },
        TrainingSystem.THRESHOLD: {
            "threshold_run_count": weekly.get("threshold_run_count", 0),
            "total_run_count": weekly.get("total_run_count", 0),
            "effort_stability_min_per_mi": weekly.get("effort_stability_min_per_mi"),
            "threshold_pace_min_per_mi": weekly.get("threshold_pace_min_per_mi"),
        },
    }


def _fetch_prior_insight(
    session: Session, user_id: str, week_start: date
) -> Optional[Dict[str, Any]]:
    row = session.execute(
        text(
            "SELECT hr_drift_pct, z2_pace_min_per_mi, efficiency, easy_avg_hr, "
            "hr_drift_band, z2_pace_band, efficiency_band, easy_avg_hr_band, overall_band, "
            "kpi_snapshot "
            "FROM weekly_training_insights "
            "WHERE user_id = CAST(:uid AS uuid) AND week_start < :ws "
            "ORDER BY week_start DESC LIMIT 1"
        ),
        {"uid": user_id, "ws": str(week_start)},
    ).fetchone()
    if not row:
        return None
    snapshot = row.kpi_snapshot if isinstance(row.kpi_snapshot, dict) else None
    threshold_prior = None
    threshold_prior_band = None
    threshold_prior_pace = None
    threshold_prior_pace_band = None
    threshold_prior_overall = None
    if snapshot:
        systems = snapshot.get("systems", {})
        th = systems.get(TrainingSystem.THRESHOLD.value, {})
        th_kpis = th.get("kpis", {})
        th_bands = th.get("bands", {})
        threshold_prior = th_kpis.get("effort_stability_min_per_mi")
        threshold_prior_band = th_bands.get("effort_stability")
        threshold_prior_pace = th_kpis.get("threshold_pace_min_per_mi")
        threshold_prior_pace_band = th_bands.get("threshold_pace")
        threshold_prior_overall = th.get("overall_band")

    return {
        "hr_drift_pct": row.hr_drift_pct,
        "z2_pace_min_per_mi": row.z2_pace_min_per_mi,
        "efficiency": row.efficiency,
        "easy_avg_hr": getattr(row, "easy_avg_hr", None),
        "hr_drift_band": row.hr_drift_band,
        "z2_pace_band": row.z2_pace_band,
        "efficiency_band": row.efficiency_band,
        "easy_avg_hr_band": getattr(row, "easy_avg_hr_band", None),
        "overall_band": row.overall_band,
        "threshold_effort_stability": threshold_prior,
        "threshold_effort_stability_band": threshold_prior_band,
        "threshold_prior_pace": threshold_prior_pace,
        "threshold_prior_pace_band": threshold_prior_pace_band,
        "threshold_prior_overall": threshold_prior_overall,
    }


def _compute_easy_system_pipeline(
    kpis: Dict[str, Any], prior: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    prior_drift = prior["hr_drift_pct"] if prior else None
    prior_pace = prior["z2_pace_min_per_mi"] if prior else None
    prior_eff = prior["efficiency"] if prior else None
    prior_easy_hr = prior.get("easy_avg_hr") if prior else None

    drift_band = _hr_drift_band(kpis.get("hr_drift_pct"))
    pace_band = _trend_band(
        kpis.get("z2_pace_min_per_mi"), prior_pace, lower_is_better=True
    )
    easy_hr_band = _trend_band(kpis.get("avg_hr"), prior_easy_hr, lower_is_better=True)
    eff_band = aerobic_efficiency_band_from_value(kpis.get("efficiency"))

    prior_bands = None
    if prior:
        prior_bands = {
            "hr_drift": prior.get("hr_drift_band"),
            "z2_pace": prior.get("z2_pace_band"),
            "easy_avg_hr": prior.get("easy_avg_hr_band"),
            "efficiency": prior.get("efficiency_band"),
        }

    overall = _compute_overall_band(
        [drift_band, pace_band, easy_hr_band, eff_band],
        prior_bands,
        prior.get("overall_band") if prior else None,
    )

    deltas = {
        "hr_drift_delta": _compute_delta(kpis.get("hr_drift_pct"), prior_drift),
        "z2_pace_delta": _compute_delta(kpis.get("z2_pace_min_per_mi"), prior_pace),
        "easy_avg_hr_delta": _compute_delta(kpis.get("avg_hr"), prior_easy_hr),
        "efficiency_delta": _compute_delta(kpis.get("efficiency"), prior_eff),
    }

    bands = {
        "hr_drift": drift_band,
        "z2_pace": pace_band,
        "easy_avg_hr": easy_hr_band,
        "efficiency": eff_band,
    }

    return {
        "system": TrainingSystem.EASY.value,
        "status": "ready",
        "kpis": kpis,
        "bands": bands,
        "deltas": deltas,
        "overall_band": overall,
    }


def _compute_threshold_system_pipeline(
    kpis: Dict[str, Any], prior: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    prior_stability = prior.get("threshold_effort_stability") if prior else None
    prior_pace = prior.get("threshold_prior_pace") if prior else None
    effort_stability = kpis.get("effort_stability_min_per_mi")
    threshold_pace = kpis.get("threshold_pace_min_per_mi")
    effort_band = _trend_band(effort_stability, prior_stability, lower_is_better=True)
    pace_band = _trend_band(threshold_pace, prior_pace, lower_is_better=True)
    effort_delta = _compute_delta(effort_stability, prior_stability)
    pace_delta = _compute_delta(threshold_pace, prior_pace)

    prior_bands_threshold = None
    if prior:
        prior_bands_threshold = {
            "effort_stability": prior.get("threshold_effort_stability_band"),
            "threshold_pace": prior.get("threshold_prior_pace_band"),
        }

    overall = _compute_overall_band(
        [effort_band, pace_band],
        prior_bands_threshold,
        prior.get("threshold_prior_overall") if prior else None,
    )

    return {
        "system": TrainingSystem.THRESHOLD.value,
        "status": "ready",
        "kpis": kpis,
        "bands": {"effort_stability": effort_band, "threshold_pace": pace_band},
        "deltas": {
            "effort_stability_delta": effort_delta,
            "threshold_pace_delta": pace_delta,
        },
        "overall_band": overall,
    }


def _compute_system_pipeline(
    kpis_by_system: Dict[TrainingSystem, Dict[str, Any]],
    prior: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Central signal computation pipeline keyed by training system.
    Only EASY is implemented for now; structure is future-proof for THRESHOLD/SPEED.
    """
    systems: Dict[str, Dict[str, Any]] = {}
    easy_kpis = kpis_by_system[TrainingSystem.EASY]
    if easy_kpis.get("easy_run_count", 0) > 0:
        systems[TrainingSystem.EASY.value] = _compute_easy_system_pipeline(
            easy_kpis, prior
        )
    else:
        systems[TrainingSystem.EASY.value] = {
            "system": TrainingSystem.EASY.value,
            "status": "insufficient_data",
            "reason": "no_easy_runs",
            "kpis": easy_kpis,
            "bands": {
                "hr_drift": None,
                "z2_pace": None,
                "easy_avg_hr": None,
                "efficiency": None,
            },
            "deltas": {
                "hr_drift_delta": None,
                "z2_pace_delta": None,
                "easy_avg_hr_delta": None,
                "efficiency_delta": None,
            },
            "overall_band": None,
        }

    threshold_kpis = kpis_by_system[TrainingSystem.THRESHOLD]
    if threshold_kpis.get("threshold_run_count", 0) > 0:
        systems[TrainingSystem.THRESHOLD.value] = _compute_threshold_system_pipeline(
            threshold_kpis, prior
        )
    else:
        systems[TrainingSystem.THRESHOLD.value] = {
            "system": TrainingSystem.THRESHOLD.value,
            "status": "insufficient_data",
            "reason": "no_threshold_runs",
            "kpis": threshold_kpis,
            "bands": {"effort_stability": None, "threshold_pace": None},
            "deltas": {"effort_stability_delta": None, "threshold_pace_delta": None},
            "overall_band": None,
        }
    return {"systems": systems}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_weekly_insight(
    session: Session,
    user_id: str,
    ref_date: Optional[date] = None,
    insight_week: Literal["completed", "in_progress"] = "completed",
) -> Dict[str, Any]:
    """
    Compute and store a weekly training insight for a user.
    Idempotent: re-running for the same week updates the existing row.

    ``insight_week``:
    - ``completed`` (default): last fully completed Mon–Sun week (cron / batch).
    - ``in_progress``: calendar week containing ``ref_date``; KPIs use
      Monday through ``min(ref_date, Sunday)`` so mid-week activity updates
      the same ``week_start`` row.
    """
    if ref_date is None:
        ref_date = date.today()

    athlete_id = get_primary_athlete_id(session, str(user_id))
    if athlete_id is None:
        return {
            "user_id": user_id,
            "skipped": True,
            "reason": "no_athlete",
            "message": "No linked Strava athlete; weekly insight not generated.",
        }

    if insight_week == "in_progress":
        week_start, week_end = calendar_week_containing(ref_date)
        kpi_end = min(ref_date, week_end)
    else:
        week_start, week_end = _week_bounds(ref_date)
        kpi_end = week_end

    kpis_by_system = _fetch_week_kpis_by_system(
        session, user_id, week_start, kpi_end, athlete_id
    )
    easy_kpis = kpis_by_system[TrainingSystem.EASY]

    if easy_kpis["easy_run_count"] == 0:
        return {
            "user_id": user_id,
            "week_start": str(week_start),
            "week_end": str(week_end),
            "skipped": True,
            "reason": "no_easy_runs",
            "systems": {
                TrainingSystem.EASY.value: {
                    "system": TrainingSystem.EASY.value,
                    "status": "insufficient_data",
                    "reason": "no_easy_runs",
                },
                TrainingSystem.THRESHOLD.value: {
                    "system": TrainingSystem.THRESHOLD.value,
                    "status": "insufficient_data",
                    "reason": "no_threshold_runs",
                },
            },
        }

    prior = _fetch_prior_insight(session, user_id, week_start)
    pipeline = _compute_system_pipeline(kpis_by_system, prior)
    easy_system = pipeline["systems"][TrainingSystem.EASY.value]
    kpis = easy_system["kpis"]
    bands = easy_system["bands"]
    deltas = easy_system["deltas"]
    overall = easy_system["overall_band"]
    drift_band = bands["hr_drift"]
    pace_band = bands["z2_pace"]
    easy_hr_band = bands["easy_avg_hr"]
    eff_band = bands["efficiency"]

    summary_text: Optional[str] = None
    action_text: Optional[str] = None

    snapshot = {
        "kpis": kpis,
        "bands": bands,
        "deltas": deltas,
        "overall_band": overall,
        "training_system": TrainingSystem.EASY.value,
        "systems": pipeline["systems"],
    }

    session.execute(
        text(
            """
            INSERT INTO weekly_training_insights (
                user_id, week_start, week_end,
                hr_drift_pct, z2_pace_min_per_mi, efficiency, easy_avg_hr,
                hr_drift_band, z2_pace_band, efficiency_band, easy_avg_hr_band,
                overall_band,
                hr_drift_delta, z2_pace_delta, efficiency_delta, easy_avg_hr_delta,
                easy_run_count, total_run_count,
                summary_text, action_text,
                kpi_snapshot, generated_at
            ) VALUES (
                CAST(:uid AS uuid), :ws, :we,
                :drift, :pace, :eff, :easy_hr,
                :drift_band, :pace_band, :eff_band, :easy_hr_band,
                :overall,
                :d_drift, :d_pace, :d_eff, :d_easy_hr,
                :easy_cnt, :total_cnt,
                :summary, :action,
                :snapshot, now()
            )
            ON CONFLICT (user_id, week_start) DO UPDATE SET
                week_end = EXCLUDED.week_end,
                hr_drift_pct = EXCLUDED.hr_drift_pct,
                z2_pace_min_per_mi = EXCLUDED.z2_pace_min_per_mi,
                efficiency = EXCLUDED.efficiency,
                easy_avg_hr = EXCLUDED.easy_avg_hr,
                hr_drift_band = EXCLUDED.hr_drift_band,
                z2_pace_band = EXCLUDED.z2_pace_band,
                efficiency_band = EXCLUDED.efficiency_band,
                easy_avg_hr_band = EXCLUDED.easy_avg_hr_band,
                overall_band = EXCLUDED.overall_band,
                hr_drift_delta = EXCLUDED.hr_drift_delta,
                z2_pace_delta = EXCLUDED.z2_pace_delta,
                efficiency_delta = EXCLUDED.efficiency_delta,
                easy_avg_hr_delta = EXCLUDED.easy_avg_hr_delta,
                easy_run_count = EXCLUDED.easy_run_count,
                total_run_count = EXCLUDED.total_run_count,
                summary_text = EXCLUDED.summary_text,
                action_text = EXCLUDED.action_text,
                kpi_snapshot = EXCLUDED.kpi_snapshot,
                generated_at = now()
            """
        ),
        {
            "uid": user_id,
            "ws": str(week_start),
            "we": str(week_end),
            "drift": kpis.get("hr_drift_pct"),
            "pace": kpis.get("z2_pace_min_per_mi"),
            "eff": kpis.get("efficiency"),
            "easy_hr": kpis.get("avg_hr"),
            "drift_band": drift_band,
            "pace_band": pace_band,
            "eff_band": eff_band,
            "easy_hr_band": easy_hr_band,
            "overall": overall,
            "d_drift": deltas["hr_drift_delta"],
            "d_pace": deltas["z2_pace_delta"],
            "d_eff": deltas["efficiency_delta"],
            "d_easy_hr": deltas["easy_avg_hr_delta"],
            "easy_cnt": kpis["easy_run_count"],
            "total_cnt": kpis["total_run_count"],
            "summary": summary_text,
            "action": action_text,
            "snapshot": json.dumps(snapshot),
        },
    )
    session.commit()

    return {
        "user_id": user_id,
        "week_start": str(week_start),
        "week_end": str(week_end),
        "overall_band": overall,
        "easy_run_count": kpis["easy_run_count"],
        "generated": True,
        "systems": pipeline["systems"],
    }


def get_latest_weekly_insight(
    session: Session, user_id: str, *, slim: bool = False
) -> Dict[str, Any]:
    """Return the most recent weekly insight.

    ``slim=False`` (default): full scoreboard for REST / mobile Insights API.
    ``slim=True``: coach orientation payload only (``week_start``, ``week_end``,
    ``overall_band``) — no per-KPI values, zone charts, or run counts.
    """
    row = session.execute(
        text(
            "SELECT * FROM weekly_training_insights "
            "WHERE user_id = CAST(:uid AS uuid) "
            "ORDER BY week_start DESC LIMIT 1"
        ),
        {"uid": user_id},
    ).fetchone()

    if not row:
        if slim:
            return {
                "has_insight": False,
                "insight_detail_level": "orientation",
                "message": (
                    "No weekly insight rows yet. Trend charts can still appear from your "
                    "history once we have enough weeks of stored metrics (including easy runs)."
                ),
                "orientation_note": WEEKLY_INSIGHT_ORIENTATION_NOTE,
            }
        return {
            "has_insight": False,
            "message": (
                "No weekly insight rows yet. Trend charts can still appear from your "
                "history once we have enough weeks of stored metrics (including easy runs)."
            ),
            "systems": {},
            "hr_drift_band_zones": hr_drift_band_zones_chart(),
            "aerobic_efficiency_band_zones": aerobic_efficiency_band_zones_chart(),
        }

    if slim:
        return {
            "has_insight": True,
            "insight_detail_level": "orientation",
            "week_start": str(row.week_start),
            "week_end": str(row.week_end),
            "overall_band": row.overall_band,
            "orientation_note": WEEKLY_INSIGHT_ORIENTATION_NOTE,
        }

    pace_display = "—"
    if row.z2_pace_min_per_mi:
        pace_display = format_pace_sec_per_mi(row.z2_pace_min_per_mi * 60)

    pace_delta_display = None
    if row.z2_pace_delta is not None:
        delta_sec = round(row.z2_pace_delta * 60)
        sign = "+" if delta_sec > 0 else ""
        pace_delta_display = f"{sign}{delta_sec} sec/mi"

    drift_delta_display = None
    if row.hr_drift_delta is not None:
        sign = "+" if row.hr_drift_delta > 0 else ""
        drift_delta_display = f"{sign}{row.hr_drift_delta}%"

    eff_delta_display = None
    if row.efficiency_delta is not None:
        sign = "+" if row.efficiency_delta > 0 else ""
        eff_delta_display = f"{sign}{row.efficiency_delta}"

    easy_hr_display = "—"
    easy_hr = getattr(row, "easy_avg_hr", None)
    if easy_hr is not None:
        easy_hr_display = str(round(float(easy_hr)))

    easy_hr_delta_display = None
    easy_hr_d = getattr(row, "easy_avg_hr_delta", None)
    if easy_hr_d is not None:
        d = round(float(easy_hr_d))
        sign = "+" if d > 0 else ""
        easy_hr_delta_display = f"{sign}{d} bpm"

    easy_hr_band = getattr(row, "easy_avg_hr_band", None)

    kpis_payload = [
        {
            "name": "hr_drift",
            "label": "HR drift",
            "value": row.hr_drift_pct,
            "value_display": (
                f"{row.hr_drift_pct}%" if row.hr_drift_pct is not None else "—"
            ),
            "band": row.hr_drift_band,
            "delta_display": drift_delta_display,
        },
        {
            "name": "z2_pace",
            "label": "Avg. Z2 pace",
            "value": row.z2_pace_min_per_mi,
            "value_display": pace_display,
            "band": row.z2_pace_band,
            "delta_display": pace_delta_display,
        },
        {
            "name": "easy_avg_hr",
            "label": "Avg HR",
            "value": float(easy_hr) if easy_hr is not None else None,
            "value_display": easy_hr_display,
            "band": easy_hr_band,
            "delta_display": easy_hr_delta_display,
        },
        {
            "name": "efficiency",
            "label": "Efficiency",
            "value": row.efficiency,
            "value_display": str(row.efficiency) if row.efficiency is not None else "—",
            "band": aerobic_efficiency_band_from_value(
                float(row.efficiency) if row.efficiency is not None else None
            ),
            "delta_display": eff_delta_display,
        },
    ]

    systems_payload: Dict[str, Dict[str, Any]] = {
        TrainingSystem.EASY.value: {
            "system": TrainingSystem.EASY.value,
            "status": "ready",
            "overall_band": row.overall_band,
            "kpis": kpis_payload,
            "easy_run_count": row.easy_run_count,
            "total_run_count": row.total_run_count,
            "summary_text": row.summary_text,
            "action_text": row.action_text,
            "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        }
    }
    if isinstance(row.kpi_snapshot, dict):
        prior_systems = row.kpi_snapshot.get("systems", {})
        threshold_system = prior_systems.get(TrainingSystem.THRESHOLD.value)
        if isinstance(threshold_system, dict):
            systems_payload[TrainingSystem.THRESHOLD.value] = threshold_system

    return {
        "has_insight": True,
        "insight_detail_level": "full",
        "week_start": str(row.week_start),
        "week_end": str(row.week_end),
        "overall_band": row.overall_band,
        "kpis": kpis_payload,
        "easy_run_count": row.easy_run_count,
        "total_run_count": row.total_run_count,
        "summary_text": row.summary_text,
        "action_text": row.action_text,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "systems": systems_payload,
        "hr_drift_band_zones": hr_drift_band_zones_chart(),
        "aerobic_efficiency_band_zones": aerobic_efficiency_band_zones_chart(),
    }


def get_weekly_insight_history(
    session: Session, user_id: str, weeks: int = 6
) -> Dict[str, Any]:
    """Return the last *weeks* calendar weeks of easy-run KPIs plus zone definitions.

    EASY: one point per calendar week (oldest → newest), aligned with the X axis even when
    a week has no stored insight (null metrics for that week).

    The newest column is the **calendar week containing today** (including in-progress
    rows keyed by that week's Monday), not the prior completed week only.
    """
    weeks = max(1, min(weeks, 12))

    athlete_id = get_primary_athlete_id(session, str(user_id))
    if athlete_id is None:
        return {
            "has_history": False,
            "message": "No linked Strava athlete.",
            "systems": {},
        }

    cal_week_start, _ = calendar_week_containing(date.today())
    week_windows = [
        (
            cal_week_start - timedelta(weeks=offset),
            cal_week_start - timedelta(weeks=offset) + timedelta(days=6),
        )
        for offset in reversed(range(weeks))
    ]
    oldest_monday = cal_week_start - timedelta(weeks=weeks - 1)

    rows = session.execute(
        text(
            "SELECT week_start, hr_drift_pct, hr_drift_band, "
            "z2_pace_min_per_mi, z2_pace_band, "
            "efficiency, efficiency_band, "
            "easy_avg_hr, easy_avg_hr_band "
            "FROM weekly_training_insights "
            "WHERE user_id = CAST(:uid AS uuid) "
            "  AND week_start >= :ws_min "
            "  AND week_start <= :ws_max "
        ),
        {
            "uid": user_id,
            "ws_min": str(oldest_monday),
            "ws_max": str(cal_week_start),
        },
    ).fetchall()

    by_week_start: Dict[date, Any] = {}
    for r in rows:
        by_week_start[r.week_start] = r

    data_points: List[Dict[str, Any]] = []
    for ws, _we in week_windows:
        r = by_week_start.get(ws)
        if r is None or r.hr_drift_pct is None:
            data_points.append(
                {
                    "label": f"{ws.month}/{ws.day}",
                    "value": None,
                    "band": None,
                    "z2_pace_min_per_mi": None,
                    "z2_pace_band": None,
                    "easy_avg_hr": None,
                    "easy_avg_hr_band": None,
                    "efficiency": None,
                    "efficiency_band": None,
                }
            )
            continue
        val = float(r.hr_drift_pct)
        band = r.hr_drift_band or _hr_drift_band(val)
        pace = r.z2_pace_min_per_mi
        efficiency = r.efficiency
        eh = getattr(r, "easy_avg_hr", None)
        eff_float = float(efficiency) if efficiency is not None else None
        eff_band = (
            aerobic_efficiency_band_from_value(eff_float)
            if eff_float is not None
            else None
        )
        data_points.append(
            {
                "label": f"{ws.month}/{ws.day}",
                "value": val,
                "band": band,
                "z2_pace_min_per_mi": float(pace) if pace is not None else None,
                "z2_pace_band": r.z2_pace_band,
                "easy_avg_hr": float(eh) if eh is not None else None,
                "easy_avg_hr_band": getattr(r, "easy_avg_hr_band", None),
                "efficiency": eff_float,
                "efficiency_band": eff_band,
            }
        )

    if not any(p.get("value") is not None for p in data_points):
        return {
            "has_history": False,
            "message": "Not enough data for a trend chart yet.",
            "systems": {},
        }

    zones = hr_drift_band_zones_chart()
    eff_zones = aerobic_efficiency_band_zones_chart()

    # THRESHOLD: same calendar week_windows as EASY — one point per week, gaps as nulls.
    prev_threshold_stability: Optional[float] = None
    prev_threshold_pace: Optional[float] = None
    threshold_points: List[Dict[str, Any]] = []
    for ws, we in week_windows:
        wk = _fetch_week_kpis(session, user_id, ws, we, athlete_id)
        stab: Optional[float] = None
        if int(wk.get("threshold_run_count") or 0) > 0:
            raw_s = wk.get("effort_stability_min_per_mi")
            if raw_s is not None:
                stab = float(raw_s)
        if stab is None:
            threshold_points.append(
                {
                    "label": f"{ws.month}/{ws.day}",
                    "value": None,
                    "band": None,
                    "z2_pace_min_per_mi": None,
                    "z2_pace_band": None,
                    "easy_avg_hr": None,
                    "easy_avg_hr_band": None,
                    "efficiency": None,
                    "efficiency_band": None,
                }
            )
            continue
        pace: Optional[float] = None
        raw_p = wk.get("threshold_pace_min_per_mi")
        if raw_p is not None:
            pace = float(raw_p)
        th_band = _trend_band(stab, prev_threshold_stability, lower_is_better=True)
        pace_band = (
            _trend_band(pace, prev_threshold_pace, lower_is_better=True)
            if pace is not None
            else None
        )
        threshold_points.append(
            {
                "label": f"{ws.month}/{ws.day}",
                "value": stab,
                "band": th_band,
                "z2_pace_min_per_mi": pace,
                "z2_pace_band": pace_band,
                "easy_avg_hr": None,
                "easy_avg_hr_band": None,
                "efficiency": None,
                "efficiency_band": None,
            }
        )
        prev_threshold_stability = stab
        if pace is not None:
            prev_threshold_pace = pace

    return {
        "has_history": True,
        "weekly_data": data_points,
        "zones": zones,
        "efficiency_zones": eff_zones,
        "systems": {
            TrainingSystem.EASY.value: {
                "weekly_data": data_points,
                "zones": zones,
                "efficiency_zones": eff_zones,
            },
            TrainingSystem.THRESHOLD.value: {"weekly_data": threshold_points},
        },
    }


def get_users_with_easy_runs(
    session: Session, week_start: date, week_end: date
) -> List[str]:
    """Return user_ids that had at least one easy run in the given week."""
    rows = session.execute(
        text(_USERS_WITH_EASY_RUNS_SQL),
        {"ws": str(week_start), "we": str(week_end)},
    ).fetchall()
    return [str(r.user_id) for r in rows]

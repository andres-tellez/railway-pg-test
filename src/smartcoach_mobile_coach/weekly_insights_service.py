"""
Weekly Training Insights Service

Computes deterministic KPI bands, overall score, and deltas from persisted
``activities`` execution columns (Tier 2). Numeric truth is computed in SQL +
Python rollups; weekly rows store metrics for the mobile Insights charts.

``get_latest_weekly_insight(..., slim=True)`` returns an orientation-only dict
for the coach tool (week + ``overall_band``); REST uses ``slim=False`` (full).
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple

from sqlalchemy import Integer, bindparam, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.db.dao.plans_dao import get_active_or_most_recent_plan
from src.smartcoach_mobile_coach.runner_profile.models import (
    HrZoneBand,
    PaceZoneBand,
    RunnerZoneProfileData,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_easy import (
    HrProgressChartZone,
    classify_easy_hr_progress,
    hr_progress_zones_chart_api_payload,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    classify_easy_pace_progress,
)
from src.smartcoach_mobile_coach.execution_analytics.combine import (
    StoredTempoRunFact,
    combine_weekly_from_stored_run_facts,
)
from src.smartcoach_mobile_coach.insights_chart_authority import (
    attach_pace_progress_band,
    attach_tempo_hr_progress_band,
    resolve_easy_hr_progress,
    resolve_pace_progress,
    resolve_tempo_hr_progress,
)
from src.smartcoach_mobile_coach.insights_systems import (
    TEMPO_SYSTEM_SPEC,
    InsightsSystem,
    read_kpi_field,
    read_trend_band,
    resolve_system_snapshot,
)
from src.smartcoach_mobile_coach.tempo_kpi.tempo_segment_pace import (
    TempoSegmentPaceResult,
)
from src.smartcoach_mobile_coach.runner_profile.service import (
    get_runner_profile,
)
from src.smartcoach_mobile_coach.display_format import format_pace_sec_per_mi
from src.smartcoach_mobile_coach.db_helpers import get_primary_athlete_id
from src.smartcoach_mobile_coach.easy_kpi.efficiency_easy import (
    efficiency_zones_chart_api_payload,
)
from src.smartcoach_mobile_coach.easy_kpi.hr_drift_easy import (
    hr_drift_zones_chart_api_payload,
)
from src.smartcoach_mobile_coach.easy_kpi.resolve import (
    resolve_easy_efficiency,
    resolve_easy_hr_drift,
)
from src.utils.hr_zone_constants import (
    aerobic_efficiency_band_from_value,
    aerobic_efficiency_band_zones_chart,
    hr_drift_band_zones_chart,
    OVERALL_SCORE_RULES,
    TREND_BAND_THRESHOLDS,
    hr_drift_band_from_pct,
)

logger = logging.getLogger("smartcoach_mobile_coach")


def _coerce_finite_float(value: Any) -> float | None:
    """JSON cannot represent NaN/Inf; drop non-finite values for API payloads."""
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):
        return None
    return x


def _empty_easy_history_point(label: str) -> Dict[str, Any]:
    return {
        "label": label,
        "value": None,
        "band": None,
        "z2_pace_min_per_mi": None,
        "easy_avg_hr": None,
        "easy_pace_progress_band": None,
        "easy_hr_progress_band": None,
        "efficiency": None,
        "efficiency_band": None,
    }


def _empty_tempo_history_point(label: str) -> Dict[str, Any]:
    """Gap week on Tempo Avg Pace chart (explicit tempo fields; no trend bands)."""
    return {
        "label": label,
        "value": None,
        "band": None,
        "tempo_segment_pace_min_per_mi": None,
        "tempo_segment_avg_hr_bpm": None,
        "tempo_segment_pace_source": None,
        "tempo_segment_split_count": 0,
        "tempo_segment_confidence": None,
        "tempo_pace_progress_band": None,
        "tempo_hr_progress_band": None,
        "effort_stability_min_per_mi": None,
        "easy_avg_hr": None,
        "easy_pace_progress_band": None,
        "easy_hr_progress_band": None,
        "efficiency": None,
        "efficiency_band": None,
    }


def _hr_zones_chart_payload(
    zones_chart: tuple[HrProgressChartZone, ...],
) -> List[Dict[str, Any]]:
    zones: List[Dict[str, Any]] = []
    for zone in hr_progress_zones_chart_api_payload(zones_chart):
        lo = _coerce_finite_float(zone.get("min"))
        hi = _coerce_finite_float(zone.get("max"))
        if lo is None or hi is None:
            continue
        zones.append({"color": str(zone["color"]), "min": lo, "max": hi})
    return zones


def _easy_kpi_zones_chart_payload(
    zones_chart: tuple[dict[str, float | str], ...],
    *,
    api_payload_fn,
) -> List[Dict[str, Any]]:
    zones: List[Dict[str, Any]] = []
    for zone in api_payload_fn(zones_chart):
        lo = _coerce_finite_float(zone.get("min"))
        hi = _coerce_finite_float(zone.get("max"))
        if lo is None or hi is None:
            continue
        zones.append({"color": str(zone["color"]), "min": lo, "max": hi})
    return zones


def _resolve_easy_hr_drift(
    session: Session, user_id: str
) -> Tuple[str, List[Dict[str, Any]]]:
    """HR drift target copy and chart zones (global bands v1; resolver may personalize later)."""
    ref = resolve_easy_hr_drift(session, user_id)
    return ref.target_display, _easy_kpi_zones_chart_payload(
        ref.drift_zones_chart,
        api_payload_fn=hr_drift_zones_chart_api_payload,
    )


def _resolve_easy_efficiency(
    session: Session, user_id: str
) -> Tuple[str, List[Dict[str, Any]]]:
    """Efficiency goal copy and chart zones (global bands v1)."""
    ref = resolve_easy_efficiency(session, user_id)
    return ref.goal_display, _easy_kpi_zones_chart_payload(
        ref.efficiency_zones_chart,
        api_payload_fn=efficiency_zones_chart_api_payload,
    )


def _resolve_easy_hr_progress(
    session: Session, user_id: str
) -> Tuple[Optional[HrZoneBand], List[Dict[str, Any]]]:
    """HR-progress target and chart zones from training pace recommendations."""
    return resolve_easy_hr_progress(session, user_id)


def _resolve_easy_pace_progress(
    session: Session, user_id: str
) -> Tuple[Optional[PaceZoneBand], List[Dict[str, Any]]]:
    """Pace-progress target and chart zones from training pace recommendations."""
    target, zones, _display = resolve_pace_progress(
        session, user_id, InsightsSystem.EASY
    )
    return target, zones


def _attach_easy_pace_progress_band(
    point: Dict[str, Any],
    *,
    target_easy_pace: Optional[PaceZoneBand],
) -> Dict[str, Any]:
    """Set pace-progress band on a weekly history point (HR-free)."""
    return attach_pace_progress_band(
        point,
        system=InsightsSystem.EASY,
        target_pace=target_easy_pace,
    )


def _resolve_tempo_pace_progress(
    session: Session, user_id: str
) -> Tuple[Optional[PaceZoneBand], List[Dict[str, Any]], Optional[str]]:
    """Tempo pace-progress corridor, chart zones, and display from recommendations."""
    return resolve_pace_progress(session, user_id, InsightsSystem.TEMPO)


def _attach_tempo_pace_progress_band(
    point: Dict[str, Any],
    *,
    target_tempo_pace: Optional[PaceZoneBand],
) -> Dict[str, Any]:
    """Set tempo pace-progress band on a weekly history point (Z3 corridor; HR-free)."""
    return attach_pace_progress_band(
        point,
        system=InsightsSystem.TEMPO,
        target_pace=target_tempo_pace,
    )


def _resolve_tempo_hr_progress(
    session: Session, user_id: str
) -> Tuple[Optional[HrZoneBand], List[Dict[str, Any]], Optional[str]]:
    """Tempo HR-progress corridor, chart zones, and display from recommendations."""
    return resolve_tempo_hr_progress(session, user_id)


def _tempo_segment_result_to_kpi_fields(
    result: TempoSegmentPaceResult,
) -> Dict[str, Any]:
    fields: Dict[str, Any] = {
        "tempo_segment_pace_min_per_mi": result.tempo_segment_pace_min_per_mi,
        "tempo_segment_avg_hr_bpm": result.tempo_segment_avg_hr_bpm,
        "tempo_segment_pace_source": result.tempo_segment_pace_source,
        "tempo_segment_split_count": result.tempo_segment_split_count,
        "tempo_segment_confidence": result.tempo_segment_confidence,
    }
    if result.activity_avg_pace_min_per_mi is not None:
        fields["activity_avg_pace_min_per_mi"] = result.activity_avg_pace_min_per_mi
    return fields


def _attach_tempo_segment_history_point(
    point: Dict[str, Any],
    *,
    target_tempo_pace: Optional[PaceZoneBand],
    target_hr_z3: Optional[HrZoneBand],
    segment: TempoSegmentPaceResult,
) -> Dict[str, Any]:
    """Merge segment provenance and optionally attach pace/HR GYOR bands."""
    point.update(_tempo_segment_result_to_kpi_fields(segment))
    if segment.tempo_segment_pace_min_per_mi is not None and segment.allows_full_gyor():
        point = _attach_tempo_pace_progress_band(
            point,
            target_tempo_pace=target_tempo_pace,
        )
        return attach_tempo_hr_progress_band(
            point,
            target_hr_z3=target_hr_z3,
        )
    point["tempo_pace_progress_band"] = None
    point["tempo_hr_progress_band"] = None
    return point


def _attach_easy_hr_progress_band(
    point: Dict[str, Any],
    *,
    target_hr_z2: Optional[HrZoneBand],
) -> Dict[str, Any]:
    """Set hr-progress band on a weekly history point (vs calibrated Z2)."""
    avg_hr = _coerce_finite_float(point.get("easy_avg_hr"))
    point["easy_hr_progress_band"] = classify_easy_hr_progress(
        avg_hr_bpm=avg_hr,
        target_hr_z2=target_hr_z2,
    )
    return point


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


# Classification + tempo segment pace are Tier 2 facts on ``activities``
# (``execution_analytics`` producer). Weekly rollups read persisted columns only.

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_ACTIVITY_DATE_SQL = "activity_local_date(a.start_date, a.timezone)::date"

_WEEK_KPIS_SQL = f"""
WITH week_runs AS (
    SELECT
        a.insights_system,
        a.hr_drift_pct,
        a.easy_pct,
        a.z2_band_pct,
        a.conv_avg_speed AS avg_pace,
        a.average_heartrate AS avg_hr
    FROM public.activities a
    INNER JOIN public.user_athletes ua
        ON ua.user_id = a.user_id AND a.athlete_id = ua.athlete_id
    WHERE a.user_id = CAST(:uid AS uuid)
      AND a.athlete_id = :athlete_id
      AND a.type = 'Run'
      AND {_ACTIVITY_DATE_SQL} >= CAST(:ws AS date)
      AND {_ACTIVITY_DATE_SQL} <= CAST(:we AS date)
)
SELECT
    COUNT(*) AS total_runs,
    COUNT(*) FILTER (WHERE insights_system = 'easy') AS easy_runs,
    COUNT(*) FILTER (WHERE insights_system = 'tempo') AS tempo_runs,
    ROUND(AVG(hr_drift_pct) FILTER (WHERE insights_system = 'easy')::numeric, 2) AS avg_drift,
    ROUND(AVG(avg_pace) FILTER (WHERE insights_system = 'easy')::numeric, 4) AS avg_pace,
    ROUND(AVG(avg_hr) FILTER (WHERE insights_system = 'easy')::numeric, 1) AS avg_hr,
    ROUND(AVG(easy_pct) FILTER (WHERE insights_system = 'easy')::numeric, 2) AS avg_easy_pct,
    ROUND(AVG(z2_band_pct) FILTER (WHERE insights_system = 'easy')::numeric, 2) AS avg_z2_adherence
FROM week_runs
"""

_WEEK_TEMPO_SEGMENT_FACTS_SQL = f"""
SELECT
    a.tempo_segment_pace_min_per_mi,
    a.tempo_segment_avg_hr_bpm,
    a.tempo_segment_pace_source,
    a.tempo_segment_confidence,
    a.tempo_segment_split_count,
    a.tempo_qualifying_distance_mi
FROM public.activities a
INNER JOIN public.user_athletes ua
    ON ua.user_id = a.user_id AND a.athlete_id = ua.athlete_id
WHERE a.user_id = CAST(:uid AS uuid)
  AND a.athlete_id = :athlete_id
  AND a.type = 'Run'
  AND a.insights_system = 'tempo'
  AND {_ACTIVITY_DATE_SQL} >= CAST(:ws AS date)
  AND {_ACTIVITY_DATE_SQL} <= CAST(:we AS date)
"""

_USERS_WITH_EASY_RUNS_SQL = f"""
SELECT DISTINCT a.user_id
FROM public.activities a
INNER JOIN public.user_athletes ua
    ON ua.user_id = a.user_id AND a.athlete_id = ua.athlete_id
WHERE a.insights_system = 'easy'
  AND {_ACTIVITY_DATE_SQL} >= CAST(:ws AS date)
  AND {_ACTIVITY_DATE_SQL} <= CAST(:we AS date)
"""

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


def _compute_week_tempo_segment_pace(
    session: Session,
    user_id: str,
    week_start: date,
    week_end: date,
    athlete_id: int,
) -> TempoSegmentPaceResult:
    """Roll up stored per-run tempo segment facts (no split re-fetch)."""
    stmt = text(_WEEK_TEMPO_SEGMENT_FACTS_SQL).bindparams(
        bindparam("uid", type_=PGUUID),
        bindparam("athlete_id", type_=Integer),
    )
    rows = session.execute(
        stmt,
        {
            "uid": user_id,
            "athlete_id": athlete_id,
            "ws": str(week_start),
            "we": str(week_end),
        },
    ).fetchall()

    facts = [
        StoredTempoRunFact(
            tempo_segment_pace_min_per_mi=_coerce_finite_float(
                getattr(row, "tempo_segment_pace_min_per_mi", None)
            ),
            tempo_segment_avg_hr_bpm=_coerce_finite_float(
                getattr(row, "tempo_segment_avg_hr_bpm", None)
            ),
            tempo_segment_pace_source=getattr(row, "tempo_segment_pace_source", None),
            tempo_segment_confidence=getattr(row, "tempo_segment_confidence", None),
            tempo_segment_split_count=getattr(row, "tempo_segment_split_count", None),
            tempo_qualifying_distance_mi=_coerce_finite_float(
                getattr(row, "tempo_qualifying_distance_mi", None)
            ),
        )
        for row in rows
    ]
    return combine_weekly_from_stored_run_facts(facts)


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
            "tempo_run_count": 0,
            "total_run_count": 0,
            "effort_stability_min_per_mi": None,
            "tempo_segment_pace_min_per_mi": None,
            "tempo_segment_avg_hr_bpm": None,
            "tempo_segment_pace_source": None,
            "tempo_segment_split_count": 0,
            "tempo_segment_confidence": None,
        }

    avg_pace = float(row.avg_pace) if row.avg_pace is not None else None
    avg_hr = float(row.avg_hr) if row.avg_hr is not None else None
    tempo_segment = _compute_week_tempo_segment_pace(
        session, user_id, week_start, week_end, athlete_id
    )

    return {
        "easy_run_count": int(row.easy_runs or 0),
        "tempo_run_count": int(row.tempo_runs or 0),
        "total_run_count": int(row.total_runs),
        "hr_drift_pct": float(row.avg_drift) if row.avg_drift is not None else None,
        "z2_pace_min_per_mi": avg_pace,
        "avg_hr": avg_hr,
        "efficiency": _compute_efficiency(avg_pace, avg_hr),
        "effort_stability_min_per_mi": None,
        **_tempo_segment_result_to_kpi_fields(tempo_segment),
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
) -> Dict[InsightsSystem, Dict[str, Any]]:
    """Fetch weekly KPI inputs for all systems. EASY + TEMPO are implemented."""
    weekly = _fetch_week_kpis(session, user_id, week_start, week_end, athlete_id)
    return {
        InsightsSystem.EASY: {
            "easy_run_count": weekly.get("easy_run_count", 0),
            "total_run_count": weekly.get("total_run_count", 0),
            "hr_drift_pct": weekly.get("hr_drift_pct"),
            "z2_pace_min_per_mi": weekly.get("z2_pace_min_per_mi"),
            "avg_hr": weekly.get("avg_hr"),
            "efficiency": weekly.get("efficiency"),
            "avg_easy_pct": weekly.get("avg_easy_pct"),
            "avg_z2_adherence": weekly.get("avg_z2_adherence"),
        },
        InsightsSystem.TEMPO: {
            "tempo_run_count": weekly.get("tempo_run_count", 0),
            "total_run_count": weekly.get("total_run_count", 0),
            "effort_stability_min_per_mi": weekly.get("effort_stability_min_per_mi"),
            "tempo_segment_pace_min_per_mi": weekly.get(
                "tempo_segment_pace_min_per_mi"
            ),
            "tempo_segment_avg_hr_bpm": weekly.get("tempo_segment_avg_hr_bpm"),
            "tempo_segment_pace_source": weekly.get("tempo_segment_pace_source"),
            "tempo_segment_split_count": weekly.get("tempo_segment_split_count", 0),
            "tempo_segment_confidence": weekly.get("tempo_segment_confidence"),
            "activity_avg_pace_min_per_mi": weekly.get("activity_avg_pace_min_per_mi"),
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
    tempo_prior = None
    tempo_prior_band = None
    tempo_prior_pace = None
    tempo_prior_pace_band = None
    tempo_prior_overall = None
    if snapshot:
        systems = snapshot.get("systems", {})
        th = resolve_system_snapshot(systems, TEMPO_SYSTEM_SPEC)
        th_kpis = th.get("kpis", {})
        th_bands = th.get("bands", {})
        tempo_prior = th_kpis.get("effort_stability_min_per_mi")
        tempo_prior_band = th_bands.get("effort_stability")
        tempo_prior_pace = read_kpi_field(
            th_kpis, TEMPO_SYSTEM_SPEC, TEMPO_SYSTEM_SPEC.kpi_pace_field
        )
        tempo_prior_pace_band = read_trend_band(th_bands, TEMPO_SYSTEM_SPEC)
        tempo_prior_overall = th.get("overall_band")

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
        "tempo_effort_stability": tempo_prior,
        "tempo_effort_stability_band": tempo_prior_band,
        "tempo_prior_pace": tempo_prior_pace,
        "tempo_prior_pace_band": tempo_prior_pace_band,
        "tempo_prior_overall": tempo_prior_overall,
    }


def _compute_easy_system_pipeline(
    kpis: Dict[str, Any],
    prior: Optional[Dict[str, Any]],
    *,
    target_hr_z2: Optional[HrZoneBand] = None,
    target_easy_pace: Optional[PaceZoneBand] = None,
) -> Dict[str, Any]:
    prior_drift = prior["hr_drift_pct"] if prior else None
    prior_pace = prior["z2_pace_min_per_mi"] if prior else None
    prior_eff = prior["efficiency"] if prior else None
    prior_easy_hr = prior.get("easy_avg_hr") if prior else None

    drift_band = _hr_drift_band(kpis.get("hr_drift_pct"))
    pace_min_raw = kpis.get("z2_pace_min_per_mi")
    pace_pm = _coerce_finite_float(pace_min_raw) if pace_min_raw is not None else None
    pace_sec = pace_pm * 60.0 if pace_pm is not None else None
    pace_band = classify_easy_pace_progress(
        pace_sec_per_mi=pace_sec,
        target_easy_pace=target_easy_pace,
    )
    avg_hr_raw = kpis.get("avg_hr")
    avg_hr_bpm = _coerce_finite_float(avg_hr_raw) if avg_hr_raw is not None else None
    easy_hr_band = classify_easy_hr_progress(
        avg_hr_bpm=avg_hr_bpm,
        target_hr_z2=target_hr_z2,
    )
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
        "system": InsightsSystem.EASY.value,
        "status": "ready",
        "kpis": kpis,
        "bands": bands,
        "deltas": deltas,
        "overall_band": overall,
    }


def _compute_tempo_system_pipeline(
    kpis: Dict[str, Any], prior: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    prior_stability = prior.get("tempo_effort_stability") if prior else None
    prior_pace = prior.get("tempo_prior_pace") if prior else None
    effort_stability = kpis.get("effort_stability_min_per_mi")
    tempo_pace = kpis.get("tempo_segment_pace_min_per_mi")
    effort_band = _trend_band(effort_stability, prior_stability, lower_is_better=True)
    pace_band = _trend_band(tempo_pace, prior_pace, lower_is_better=True)
    effort_delta = _compute_delta(effort_stability, prior_stability)
    pace_delta = _compute_delta(tempo_pace, prior_pace)

    prior_bands_tempo = None
    if prior:
        prior_bands_tempo = {
            "effort_stability": prior.get("tempo_effort_stability_band"),
            "tempo_pace": prior.get("tempo_prior_pace_band"),
        }

    overall = _compute_overall_band(
        [effort_band, pace_band],
        prior_bands_tempo,
        prior.get("tempo_prior_overall") if prior else None,
    )

    return {
        "system": InsightsSystem.TEMPO.value,
        "status": "ready",
        "kpis": kpis,
        "bands": {"effort_stability": effort_band, "tempo_pace": pace_band},
        "deltas": {
            "effort_stability_delta": effort_delta,
            "tempo_pace_delta": pace_delta,
        },
        "overall_band": overall,
    }


def _compute_system_pipeline(
    kpis_by_system: Dict[InsightsSystem, Dict[str, Any]],
    prior: Optional[Dict[str, Any]],
    *,
    target_hr_z2: Optional[HrZoneBand] = None,
    target_easy_pace: Optional[PaceZoneBand] = None,
) -> Dict[str, Any]:
    """
    Central signal computation pipeline keyed by training system.
    Only EASY is implemented for now; structure is future-proof for TEMPO/SPEED.
    """
    systems: Dict[str, Dict[str, Any]] = {}
    easy_kpis = kpis_by_system[InsightsSystem.EASY]
    if easy_kpis.get("easy_run_count", 0) > 0:
        systems[InsightsSystem.EASY.value] = _compute_easy_system_pipeline(
            easy_kpis,
            prior,
            target_hr_z2=target_hr_z2,
            target_easy_pace=target_easy_pace,
        )
    else:
        systems[InsightsSystem.EASY.value] = {
            "system": InsightsSystem.EASY.value,
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

    tempo_kpis = kpis_by_system[InsightsSystem.TEMPO]
    if tempo_kpis.get("tempo_run_count", 0) > 0:
        systems[InsightsSystem.TEMPO.value] = _compute_tempo_system_pipeline(
            tempo_kpis, prior
        )
    else:
        systems[InsightsSystem.TEMPO.value] = {
            "system": InsightsSystem.TEMPO.value,
            "status": "insufficient_data",
            "reason": "no_tempo_runs",
            "kpis": tempo_kpis,
            "bands": {"effort_stability": None, "tempo_pace": None},
            "deltas": {"effort_stability_delta": None, "tempo_pace_delta": None},
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
    easy_kpis = kpis_by_system[InsightsSystem.EASY]

    if easy_kpis["easy_run_count"] == 0:
        return {
            "user_id": user_id,
            "week_start": str(week_start),
            "week_end": str(week_end),
            "skipped": True,
            "reason": "no_easy_runs",
            "systems": {
                InsightsSystem.EASY.value: {
                    "system": InsightsSystem.EASY.value,
                    "status": "insufficient_data",
                    "reason": "no_easy_runs",
                },
                InsightsSystem.TEMPO.value: {
                    "system": InsightsSystem.TEMPO.value,
                    "status": "insufficient_data",
                    "reason": "no_tempo_runs",
                },
            },
        }

    prior = _fetch_prior_insight(session, user_id, week_start)
    profile = get_runner_profile(session, user_id)
    target_hr_z2 = (
        profile.hr_z2 if profile.calibrated and profile.hr_z2 is not None else None
    )
    target_easy_pace, _ = _resolve_easy_pace_progress(session, user_id)
    pipeline = _compute_system_pipeline(
        kpis_by_system,
        prior,
        target_hr_z2=target_hr_z2,
        target_easy_pace=target_easy_pace,
    )
    easy_system = pipeline["systems"][InsightsSystem.EASY.value]
    kpis = easy_system["kpis"]
    bands = easy_system["bands"]
    deltas = easy_system["deltas"]
    overall = easy_system["overall_band"]
    drift_band = bands["hr_drift"]
    pace_band = bands["z2_pace"]  # pace_progress band (stored as z2_pace_band)
    easy_hr_band = bands["easy_avg_hr"]  # hr_progress band (stored as easy_avg_hr_band)
    eff_band = bands["efficiency"]

    summary_text: Optional[str] = None
    action_text: Optional[str] = None

    snapshot = {
        "kpis": kpis,
        "bands": bands,
        "deltas": deltas,
        "overall_band": overall,
        "training_system": InsightsSystem.EASY.value,
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
            **_easy_insight_kpi_displays(session, user_id),
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
        InsightsSystem.EASY.value: {
            "system": InsightsSystem.EASY.value,
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
        tempo_system = resolve_system_snapshot(prior_systems, TEMPO_SYSTEM_SPEC)
        if isinstance(tempo_system, dict) and tempo_system:
            systems_payload[InsightsSystem.TEMPO.value] = tempo_system

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
        **_easy_insight_kpi_displays(session, user_id),
    }


def _resolve_easy_drift_and_efficiency(
    session: Session, user_id: str
) -> Tuple[str, str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """HR drift + efficiency footnote copy and chart zones for Insights."""
    try:
        hr_drift_target_display, zones = _resolve_easy_hr_drift(session, user_id)
        efficiency_goal_display, eff_zones = _resolve_easy_efficiency(session, user_id)
        return hr_drift_target_display, efficiency_goal_display, zones, eff_zones
    except Exception:
        logger.exception(
            "Failed to resolve easy HR drift/efficiency refs (user_id=%s)", user_id
        )
        from src.smartcoach_mobile_coach.easy_kpi.efficiency_easy import (
            format_efficiency_goal_display,
        )
        from src.smartcoach_mobile_coach.easy_kpi.hr_drift_easy import (
            format_hr_drift_target_display,
        )

        return (
            format_hr_drift_target_display(),
            format_efficiency_goal_display(),
            hr_drift_band_zones_chart(),
            aerobic_efficiency_band_zones_chart(),
        )


def _easy_insight_kpi_displays(session: Session, user_id: str) -> Dict[str, Any]:
    """Resolved HR drift / efficiency chart zones and footnote copy for Insights."""
    (
        hr_drift_target_display,
        efficiency_goal_display,
        zones,
        eff_zones,
    ) = _resolve_easy_drift_and_efficiency(session, user_id)
    return {
        "hr_drift_target_display": hr_drift_target_display,
        "efficiency_goal_display": efficiency_goal_display,
        "hr_drift_band_zones": zones,
        "aerobic_efficiency_band_zones": eff_zones,
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

    try:
        athlete_id = get_primary_athlete_id(session, str(user_id))
    except SQLAlchemyError:
        logger.exception(
            "get_primary_athlete_id failed for weekly insight history (user_id=%s)",
            user_id,
        )
        return {
            "has_history": False,
            "message": "Could not resolve linked Strava athlete.",
            "systems": {},
        }
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

    try:
        rows = session.execute(
            text(
                "SELECT week_start, hr_drift_pct, hr_drift_band, "
                "z2_pace_min_per_mi, z2_pace_band, "
                "efficiency, efficiency_band, "
                "easy_avg_hr "
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
    except SQLAlchemyError:
        logger.exception(
            "weekly_training_insights history query failed (user_id=%s)", user_id
        )
        rows = []

    by_week_start: Dict[date, Any] = {}
    for r in rows:
        by_week_start[r.week_start] = r

    # Easy pace chart: single target pace-progress bands (HR-free).
    target_easy_pace: Optional[PaceZoneBand] = None
    pace_zones: List[Dict[str, Any]] = []
    try:
        target_easy_pace, pace_zones = _resolve_easy_pace_progress(session, user_id)
    except Exception:
        logger.exception(
            "Failed to resolve easy pace refs for weekly insight history (user_id=%s)",
            user_id,
        )
        target_easy_pace = None
        pace_zones = []

    # Easy HR chart: Z2 high cap from hr_progress authority.
    target_hr_z2: Optional[HrZoneBand] = None
    hr_zones: List[Dict[str, Any]] = []
    try:
        target_hr_z2, hr_zones = _resolve_easy_hr_progress(session, user_id)
    except Exception:
        logger.exception(
            "Failed to resolve easy HR refs for weekly insight history (user_id=%s)",
            user_id,
        )
        target_hr_z2 = None
        hr_zones = []

    data_points: List[Dict[str, Any]] = []
    for ws, _we in week_windows:
        r = by_week_start.get(ws)
        if r is None or r.hr_drift_pct is None:
            data_points.append(_empty_easy_history_point(f"{ws.month}/{ws.day}"))
            continue
        val = _coerce_finite_float(r.hr_drift_pct)
        if val is None:
            data_points.append(_empty_easy_history_point(f"{ws.month}/{ws.day}"))
            continue
        band = r.hr_drift_band or _hr_drift_band(val)
        pace = _coerce_finite_float(r.z2_pace_min_per_mi)
        efficiency = r.efficiency
        eh = getattr(r, "easy_avg_hr", None)
        eff_float = _coerce_finite_float(efficiency)
        eff_band = (
            aerobic_efficiency_band_from_value(eff_float)
            if eff_float is not None
            else None
        )
        point_payload: Dict[str, Any] = {
            "label": f"{ws.month}/{ws.day}",
            "value": val,
            "band": band,
            "z2_pace_min_per_mi": pace,
            "easy_avg_hr": _coerce_finite_float(eh),
            "efficiency": eff_float,
            "efficiency_band": eff_band,
        }
        try:
            point_payload = _attach_easy_pace_progress_band(
                point_payload,
                target_easy_pace=target_easy_pace,
            )
            data_points.append(
                _attach_easy_hr_progress_band(
                    point_payload,
                    target_hr_z2=target_hr_z2,
                )
            )
        except Exception:
            logger.exception(
                "Failed to attach easy pace/HR bands for weekly history "
                "(user_id=%s, week=%s)",
                user_id,
                ws,
            )
            point_payload["easy_pace_progress_band"] = None
            point_payload["easy_hr_progress_band"] = None
            data_points.append(point_payload)

    if not any(p.get("value") is not None for p in data_points):
        return {
            "has_history": False,
            "message": "Not enough data for a trend chart yet.",
            "systems": {},
        }

    (
        hr_drift_target_display,
        efficiency_goal_display,
        zones,
        eff_zones,
    ) = _resolve_easy_drift_and_efficiency(session, user_id)

    # TEMPO: same calendar week_windows as EASY — one point per week, gaps as nulls.
    tempo_points: List[Dict[str, Any]] = []
    tempo_pace_zones: List[Dict[str, Any]] = []
    tempo_pace_target_display: Optional[str] = None
    tempo_hr_zones: List[Dict[str, Any]] = []
    tempo_hr_target_display: Optional[str] = None
    try:
        (
            target_tempo_pace,
            tempo_pace_zones,
            tempo_pace_target_display,
        ) = _resolve_tempo_pace_progress(session, user_id)
        target_hr_z3: Optional[HrZoneBand] = None
        try:
            target_hr_z3, tempo_hr_zones, tempo_hr_target_display = (
                _resolve_tempo_hr_progress(session, user_id)
            )
        except Exception:
            logger.exception(
                "Failed to resolve tempo HR refs for weekly insight history (user_id=%s)",
                user_id,
            )
            target_hr_z3 = None
            tempo_hr_zones = []
            tempo_hr_target_display = None
        for ws, we in week_windows:
            try:
                wk = _fetch_week_kpis(session, user_id, ws, we, athlete_id)
            except Exception:
                logger.exception(
                    "Failed to fetch week KPIs for tempo history "
                    "(user_id=%s, week=%s)",
                    user_id,
                    ws,
                )
                tempo_points.append(_empty_tempo_history_point(f"{ws.month}/{ws.day}"))
                continue
            if int(wk.get("tempo_run_count") or 0) <= 0:
                tempo_points.append(_empty_tempo_history_point(f"{ws.month}/{ws.day}"))
                continue
            segment = TempoSegmentPaceResult(
                tempo_segment_pace_min_per_mi=wk.get("tempo_segment_pace_min_per_mi"),
                tempo_segment_avg_hr_bpm=wk.get("tempo_segment_avg_hr_bpm"),
                tempo_segment_pace_source=wk.get("tempo_segment_pace_source"),
                tempo_segment_split_count=int(wk.get("tempo_segment_split_count") or 0),
                tempo_segment_confidence=wk.get("tempo_segment_confidence"),
                activity_avg_pace_min_per_mi=wk.get("activity_avg_pace_min_per_mi"),
            )
            if segment.tempo_segment_pace_min_per_mi is None:
                logger.debug(
                    "Tempo history gap week: runs=%s segment_pace=null "
                    "(user_id=%s, week=%s, source=%s)",
                    wk.get("tempo_run_count"),
                    user_id,
                    ws,
                    wk.get("tempo_segment_pace_source"),
                )
                tempo_points.append(_empty_tempo_history_point(f"{ws.month}/{ws.day}"))
                continue
            stab: Optional[float] = None
            raw_s = wk.get("effort_stability_min_per_mi")
            if raw_s is not None:
                stab = _coerce_finite_float(raw_s)
            point_payload: Dict[str, Any] = {
                "label": f"{ws.month}/{ws.day}",
                "value": stab,
                "band": None,
                "effort_stability_min_per_mi": stab,
                "easy_avg_hr": None,
                "easy_pace_progress_band": None,
                "easy_hr_progress_band": None,
                "efficiency": None,
                "efficiency_band": None,
            }
            try:
                tempo_points.append(
                    _attach_tempo_segment_history_point(
                        point_payload,
                        target_tempo_pace=target_tempo_pace,
                        target_hr_z3=target_hr_z3,
                        segment=segment,
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to attach tempo pace/HR bands for weekly history "
                    "(user_id=%s, week=%s)",
                    user_id,
                    ws,
                )
                point_payload.update(_tempo_segment_result_to_kpi_fields(segment))
                point_payload["tempo_pace_progress_band"] = None
                point_payload["tempo_hr_progress_band"] = None
                tempo_points.append(point_payload)
    except Exception:
        logger.exception(
            "Failed to build tempo weekly history (user_id=%s); "
            "returning empty tempo series",
            user_id,
        )
        tempo_points = [
            _empty_tempo_history_point(f"{ws.month}/{ws.day}")
            for ws, _we in week_windows
        ]
        tempo_pace_zones = []
        tempo_pace_target_display = None
        tempo_hr_zones = []
        tempo_hr_target_display = None

    return {
        "has_history": True,
        "weekly_data": data_points,
        "zones": zones,
        "efficiency_zones": eff_zones,
        "pace_zones": pace_zones,
        "hr_zones": hr_zones,
        "hr_drift_target_display": hr_drift_target_display,
        "efficiency_goal_display": efficiency_goal_display,
        "systems": {
            InsightsSystem.EASY.value: {
                "weekly_data": data_points,
                "zones": zones,
                "efficiency_zones": eff_zones,
                "pace_zones": pace_zones,
                "hr_zones": hr_zones,
                "hr_drift_target_display": hr_drift_target_display,
                "efficiency_goal_display": efficiency_goal_display,
            },
            InsightsSystem.TEMPO.value: {
                "weekly_data": tempo_points,
                "pace_zones": tempo_pace_zones,
                "pace_target_display": tempo_pace_target_display,
                "hr_zones": tempo_hr_zones,
                "hr_target_display": tempo_hr_target_display,
            },
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

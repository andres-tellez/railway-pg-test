"""
Weekly Training Insights Service

Computes deterministic KPI bands, overall score, deltas, and generates
an LLM-powered weekly summary. All numeric truth is computed here —
the LLM only interprets; it never overrides values or bands.

Principle: System = Judge, Coach = Translator.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from src.services.security.external_apis.openai_service import get_openai_service
from src.smartcoach_mobile_coach.display_format import format_pace_sec_per_mi
from src.utils.hr_zone_constants import (
    COACHING_LEVEL_DEFAULTS,
    HR_DRIFT_BANDS,
    OVERALL_SCORE_RULES,
    TREND_BAND_THRESHOLDS,
    VERBOSITY_RULES,
)

logger = logging.getLogger("smartcoach_mobile_coach")

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_WEEK_KPIS_SQL = """
WITH classified_runs AS (
    SELECT
        *,
        CASE
            WHEN is_easy_run THEN 'easy'
            WHEN (
                moving_time_seconds >= 1800
                AND z2_high IS NOT NULL
                AND easy_pct IS NOT NULL
                AND easy_pct < 0.70
                AND avg_hr IS NOT NULL
                AND avg_hr > z2_high
            ) THEN 'threshold'
            ELSE NULL
        END AS training_system
    FROM v_easy_runs
    WHERE user_id = :uid
      AND activity_date >= :ws
      AND activity_date <= :we
      AND activity_type = 'Run'
)
SELECT
    COUNT(*) AS total_runs,
    COUNT(*) FILTER (WHERE training_system = 'easy')                   AS easy_runs,
    COUNT(*) FILTER (WHERE training_system = 'threshold')              AS threshold_runs,
    ROUND(AVG(hr_drift_pct) FILTER (WHERE training_system = 'easy')::numeric, 2)  AS avg_drift,
    ROUND(AVG(avg_pace)     FILTER (WHERE training_system = 'easy')::numeric, 4)  AS avg_pace,
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
"""

_USERS_WITH_EASY_RUNS_SQL = """
WITH classified_runs AS (
    SELECT
        user_id,
        activity_date,
        CASE
            WHEN is_easy_run THEN 'easy'
            ELSE NULL
        END AS training_system
    FROM v_easy_runs
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
    if value is None:
        return None
    if value < HR_DRIFT_BANDS["green_max"]:
        return "green"
    if value < HR_DRIFT_BANDS["yellow_max"]:
        return "yellow"
    if value < HR_DRIFT_BANDS["orange_max"]:
        return "orange"
    return "red"


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
    Worst-of-three with 2-week persistence:
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


def _fetch_week_kpis(
    session: Session, user_id: str, week_start: date, week_end: date
) -> Dict[str, Any]:
    stmt = text(_WEEK_KPIS_SQL).bindparams(bindparam("uid", type_=PGUUID))
    row = session.execute(
        stmt, {"uid": user_id, "ws": str(week_start), "we": str(week_end)}
    ).fetchone()

    if not row:
        return {
            "easy_run_count": 0,
            "threshold_run_count": 0,
            "total_run_count": 0,
            "effort_stability_min_per_mi": None,
        }

    avg_pace = float(row.avg_pace) if row.avg_pace is not None else None
    avg_hr = float(row.avg_hr) if row.avg_hr is not None else None
    threshold_effort_stability = (
        float(row.avg_threshold_effort_stability)
        if row.avg_threshold_effort_stability is not None
        else None
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
        "avg_easy_pct": (
            float(row.avg_easy_pct) if row.avg_easy_pct is not None else None
        ),
        "avg_z2_adherence": (
            float(row.avg_z2_adherence) if row.avg_z2_adherence is not None else None
        ),
    }


def _fetch_week_kpis_by_system(
    session: Session, user_id: str, week_start: date, week_end: date
) -> Dict[TrainingSystem, Dict[str, Any]]:
    """Fetch weekly KPI inputs for all systems. EASY + THRESHOLD are implemented."""
    weekly = _fetch_week_kpis(session, user_id, week_start, week_end)
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
        },
    }


def _fetch_prior_insight(
    session: Session, user_id: str, week_start: date
) -> Optional[Dict[str, Any]]:
    row = session.execute(
        text(
            "SELECT hr_drift_pct, z2_pace_min_per_mi, efficiency, "
            "hr_drift_band, z2_pace_band, efficiency_band, overall_band, "
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
    if snapshot:
        systems = snapshot.get("systems", {})
        th = systems.get(TrainingSystem.THRESHOLD.value, {})
        th_kpis = th.get("kpis", {})
        th_bands = th.get("bands", {})
        threshold_prior = th_kpis.get("effort_stability_min_per_mi")
        threshold_prior_band = th_bands.get("effort_stability")

    return {
        "hr_drift_pct": row.hr_drift_pct,
        "z2_pace_min_per_mi": row.z2_pace_min_per_mi,
        "efficiency": row.efficiency,
        "hr_drift_band": row.hr_drift_band,
        "z2_pace_band": row.z2_pace_band,
        "efficiency_band": row.efficiency_band,
        "overall_band": row.overall_band,
        "threshold_effort_stability": threshold_prior,
        "threshold_effort_stability_band": threshold_prior_band,
    }


def _compute_easy_system_pipeline(
    kpis: Dict[str, Any], prior: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    prior_drift = prior["hr_drift_pct"] if prior else None
    prior_pace = prior["z2_pace_min_per_mi"] if prior else None
    prior_eff = prior["efficiency"] if prior else None

    drift_band = _hr_drift_band(kpis.get("hr_drift_pct"))
    pace_band = _trend_band(
        kpis.get("z2_pace_min_per_mi"), prior_pace, lower_is_better=True
    )
    eff_band = _trend_band(kpis.get("efficiency"), prior_eff, lower_is_better=False)

    prior_bands = None
    if prior:
        prior_bands = {
            "hr_drift": prior.get("hr_drift_band"),
            "z2_pace": prior.get("z2_pace_band"),
            "efficiency": prior.get("efficiency_band"),
        }

    overall = _compute_overall_band(
        [drift_band, pace_band, eff_band],
        prior_bands,
        prior.get("overall_band") if prior else None,
    )

    deltas = {
        "hr_drift_delta": _compute_delta(kpis.get("hr_drift_pct"), prior_drift),
        "z2_pace_delta": _compute_delta(kpis.get("z2_pace_min_per_mi"), prior_pace),
        "efficiency_delta": _compute_delta(kpis.get("efficiency"), prior_eff),
    }

    bands = {"hr_drift": drift_band, "z2_pace": pace_band, "efficiency": eff_band}

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
    effort_stability = kpis.get("effort_stability_min_per_mi")
    effort_band = _trend_band(effort_stability, prior_stability, lower_is_better=True)
    effort_delta = _compute_delta(effort_stability, prior_stability)

    return {
        "system": TrainingSystem.THRESHOLD.value,
        "status": "ready",
        "kpis": kpis,
        "bands": {"effort_stability": effort_band},
        "deltas": {"effort_stability_delta": effort_delta},
        "overall_band": effort_band,
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
                "efficiency": None,
            },
            "deltas": {
                "hr_drift_delta": None,
                "z2_pace_delta": None,
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
            "bands": {"effort_stability": None},
            "deltas": {"effort_stability_delta": None},
            "overall_band": None,
        }
    return {"systems": systems}


# ---------------------------------------------------------------------------
# LLM summary generation (interpreter layer — never changes truth)
# ---------------------------------------------------------------------------

_SUMMARY_SYSTEM = """You are SmartCoach, a supportive running coach generating a weekly training summary.

Rules:
- You MUST NOT invent numbers. Only reference the KPI values provided.
- You MUST NOT override or reinterpret the band colors. Green means good, yellow means watch, red means concern.
- Output valid JSON with exactly two keys: "summary" (2-3 sentences) and "action" (1 actionable sentence).
- Match the tone instructions provided."""


def _build_summary_prompt(
    kpis: Dict[str, Any],
    bands: Dict[str, Optional[str]],
    deltas: Dict[str, Optional[float]],
    overall: str,
    coaching_level: str,
) -> str:
    level_cfg = COACHING_LEVEL_DEFAULTS.get(
        coaching_level, COACHING_LEVEL_DEFAULTS["beginner"]
    )

    pace_display = "—"
    if kpis.get("z2_pace_min_per_mi"):
        pace_display = format_pace_sec_per_mi(kpis["z2_pace_min_per_mi"] * 60)

    data_block = (
        f"Week: {kpis.get('week_start')} to {kpis.get('week_end')}\n"
        f"Easy runs: {kpis.get('easy_run_count', 0)}\n"
        f"HR Drift: {kpis.get('hr_drift_pct', '—')}% ({bands.get('hr_drift', 'no data')})\n"
        f"Z2 Pace: {pace_display} ({bands.get('z2_pace', 'no data')})\n"
        f"Efficiency: {kpis.get('efficiency', '—')} ({bands.get('efficiency', 'no data')})\n"
        f"Overall: {overall}\n"
    )

    delta_block = ""
    if deltas.get("hr_drift_delta") is not None:
        sign = "+" if deltas["hr_drift_delta"] > 0 else ""
        delta_block += f"HR Drift vs last week: {sign}{deltas['hr_drift_delta']}%\n"
    if deltas.get("z2_pace_delta") is not None:
        sign = "+" if deltas["z2_pace_delta"] > 0 else ""
        delta_block += f"Z2 Pace vs last week: {sign}{deltas['z2_pace_delta']} min/mi\n"
    if deltas.get("efficiency_delta") is not None:
        sign = "+" if deltas["efficiency_delta"] > 0 else ""
        delta_block += f"Efficiency vs last week: {sign}{deltas['efficiency_delta']}\n"

    deltas_section = (
        "Deltas:\n" + delta_block if delta_block else "No prior week for comparison."
    )

    return (
        f"Tone: {level_cfg['tone']}\n\n"
        f"KPI Data:\n{data_block}\n"
        f"{deltas_section}\n"
        "Generate the weekly summary JSON."
    )


def _generate_llm_summary(
    kpis: Dict[str, Any],
    bands: Dict[str, Optional[str]],
    deltas: Dict[str, Optional[float]],
    overall: str,
    user_id: str,
    coaching_level: str = "beginner",
) -> Tuple[Optional[str], Optional[str]]:
    """Returns (summary_text, action_text). Fails gracefully — never blocks insight storage."""
    try:
        service = get_openai_service()
        model = os.getenv("OPENAI_CONVERSATION_MODEL", "gpt-4o")

        prompt = _build_summary_prompt(kpis, bands, deltas, overall, coaching_level)

        response = service.chat_completion(
            messages=[
                {"role": "system", "content": _SUMMARY_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            user_id=user_id,
            model=model,
            temperature=0.6,
            max_tokens=300,
            require_json=True,
        )

        parsed = json.loads(response.content)
        return parsed.get("summary"), parsed.get("action")
    except Exception:
        logger.warning(
            "LLM summary generation failed; storing insight without summary",
            exc_info=True,
        )
        return None, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_weekly_insight(
    session: Session,
    user_id: str,
    ref_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Compute and store a weekly training insight for a user.
    Idempotent: re-running for the same week updates the existing row.
    """
    if ref_date is None:
        ref_date = date.today()

    week_start, week_end = _week_bounds(ref_date)
    kpis_by_system = _fetch_week_kpis_by_system(session, user_id, week_start, week_end)
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
    eff_band = bands["efficiency"]

    coaching_level = "beginner"
    try:
        pref_row = session.execute(
            text(
                "SELECT coaching_level FROM user_coach_preferences "
                "WHERE user_id = CAST(:uid AS uuid)"
            ),
            {"uid": user_id},
        ).fetchone()
        if pref_row and pref_row.coaching_level:
            coaching_level = pref_row.coaching_level
    except Exception:
        pass

    kpi_payload = {
        **kpis,
        "week_start": str(week_start),
        "week_end": str(week_end),
    }

    summary_text, action_text = _generate_llm_summary(
        kpi_payload, bands, deltas, overall, user_id, coaching_level
    )

    snapshot = {
        "kpis": {k: v for k, v in kpis.items() if k != "avg_hr"},
        "bands": bands,
        "deltas": deltas,
        "overall_band": overall,
        "training_system": TrainingSystem.EASY.value,
        "systems": pipeline["systems"],
        "coaching_level": coaching_level,
    }

    session.execute(
        text(
            """
            INSERT INTO weekly_training_insights (
                user_id, week_start, week_end,
                hr_drift_pct, z2_pace_min_per_mi, efficiency,
                hr_drift_band, z2_pace_band, efficiency_band, overall_band,
                hr_drift_delta, z2_pace_delta, efficiency_delta,
                easy_run_count, total_run_count,
                summary_text, action_text,
                kpi_snapshot, generated_at
            ) VALUES (
                CAST(:uid AS uuid), :ws, :we,
                :drift, :pace, :eff,
                :drift_band, :pace_band, :eff_band, :overall,
                :d_drift, :d_pace, :d_eff,
                :easy_cnt, :total_cnt,
                :summary, :action,
                :snapshot, now()
            )
            ON CONFLICT (user_id, week_start) DO UPDATE SET
                week_end = EXCLUDED.week_end,
                hr_drift_pct = EXCLUDED.hr_drift_pct,
                z2_pace_min_per_mi = EXCLUDED.z2_pace_min_per_mi,
                efficiency = EXCLUDED.efficiency,
                hr_drift_band = EXCLUDED.hr_drift_band,
                z2_pace_band = EXCLUDED.z2_pace_band,
                efficiency_band = EXCLUDED.efficiency_band,
                overall_band = EXCLUDED.overall_band,
                hr_drift_delta = EXCLUDED.hr_drift_delta,
                z2_pace_delta = EXCLUDED.z2_pace_delta,
                efficiency_delta = EXCLUDED.efficiency_delta,
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
            "drift_band": drift_band,
            "pace_band": pace_band,
            "eff_band": eff_band,
            "overall": overall,
            "d_drift": deltas["hr_drift_delta"],
            "d_pace": deltas["z2_pace_delta"],
            "d_eff": deltas["efficiency_delta"],
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


def get_latest_weekly_insight(session: Session, user_id: str) -> Dict[str, Any]:
    """Return the most recent weekly insight for the REST API."""
    row = session.execute(
        text(
            "SELECT * FROM weekly_training_insights "
            "WHERE user_id = CAST(:uid AS uuid) "
            "ORDER BY week_start DESC LIMIT 1"
        ),
        {"uid": user_id},
    ).fetchone()

    if not row:
        return {
            "has_insight": False,
            "message": "No weekly insights yet. We'll generate your first summary after a week of easy runs.",
            "systems": {},
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

    kpis_payload = [
        {
            "name": "hr_drift",
            "label": "HR Drift",
            "value": row.hr_drift_pct,
            "value_display": (
                f"{row.hr_drift_pct}%" if row.hr_drift_pct is not None else "—"
            ),
            "band": row.hr_drift_band,
            "delta_display": drift_delta_display,
        },
        {
            "name": "z2_pace",
            "label": "Z2 Pace",
            "value": row.z2_pace_min_per_mi,
            "value_display": pace_display,
            "band": row.z2_pace_band,
            "delta_display": pace_delta_display,
        },
        {
            "name": "efficiency",
            "label": "Efficiency",
            "value": row.efficiency,
            "value_display": str(row.efficiency) if row.efficiency is not None else "—",
            "band": row.efficiency_band,
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
    }


def get_weekly_insight_history(
    session: Session, user_id: str, weeks: int = 6
) -> Dict[str, Any]:
    """Return the last *weeks* weekly insights plus HR drift zone definitions."""
    weeks = max(1, min(weeks, 12))
    rows = session.execute(
        text(
            "SELECT week_start, hr_drift_pct, hr_drift_band, "
            "z2_pace_min_per_mi, z2_pace_band "
            "FROM weekly_training_insights "
            "WHERE user_id = CAST(:uid AS uuid) "
            "  AND hr_drift_pct IS NOT NULL "
            "ORDER BY week_start DESC "
            "LIMIT :n"
        ),
        {"uid": user_id, "n": weeks},
    ).fetchall()

    if not rows:
        return {
            "has_history": False,
            "message": "Not enough data for a trend chart yet.",
            "systems": {},
        }

    data_points = []
    for r in reversed(rows):
        val = float(r.hr_drift_pct)
        band = r.hr_drift_band or _hr_drift_band(val)
        pace = r.z2_pace_min_per_mi
        data_points.append(
            {
                "label": f"{r.week_start.month}/{r.week_start.day}",
                "value": val,
                "band": band,
                "z2_pace_min_per_mi": float(pace) if pace is not None else None,
                "z2_pace_band": r.z2_pace_band,
            }
        )

    g_max = HR_DRIFT_BANDS["green_max"]
    y_max = HR_DRIFT_BANDS["yellow_max"]
    o_max = HR_DRIFT_BANDS["orange_max"]

    zones = [
        {"color": "green", "min": 0, "max": g_max},
        {"color": "yellow", "min": g_max, "max": y_max},
        {"color": "orange", "min": y_max, "max": o_max},
        {"color": "red", "min": o_max, "max": round(o_max + 2.5, 1)},
    ]

    return {
        "has_history": True,
        "weekly_data": data_points,
        "zones": zones,
        "systems": {
            TrainingSystem.EASY.value: {"weekly_data": data_points, "zones": zones}
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

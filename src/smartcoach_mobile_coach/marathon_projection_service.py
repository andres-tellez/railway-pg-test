"""Deterministic marathon projection from recent run signals."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import Date, bindparam, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.display_format import format_pace_sec_per_mi
from src.smartcoach_mobile_coach.training_kpi_service import get_training_progress
from src.utils.activity_local_date_sql import ACTIVITY_LOCAL_DATE_SQL_FRAGMENT

MARATHON_DISTANCE_MILES = 26.2188
M_TO_MI = 0.000621371

_RECENT_RUNS_SQL = text(
    f"""
    SELECT
        activity_id,
        ({ACTIVITY_LOCAL_DATE_SQL_FRAGMENT})::date AS activity_local_date,
        distance,
        moving_time
    FROM public.activities
    WHERE user_id = :uid
      AND type = 'Run'
      AND distance IS NOT NULL
      AND moving_time IS NOT NULL
      AND distance > 1609
      AND ({ACTIVITY_LOCAL_DATE_SQL_FRAGMENT})::date >= :cutoff_date
    ORDER BY start_date DESC
    LIMIT 48
    """
).bindparams(bindparam("uid", type_=PGUUID), bindparam("cutoff_date", type_=Date()))


def _format_finish_time(total_seconds: float) -> str:
    sec = max(0, int(round(total_seconds)))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def _coerce_goal_time_seconds(raw: Optional[str]) -> Optional[int]:
    if not raw or not isinstance(raw, str):
        return None
    parts = [p.strip() for p in raw.split(":")]
    if len(parts) != 3:
        return None
    try:
        h, m, s = [int(p) for p in parts]
    except ValueError:
        return None
    if h < 0 or m < 0 or s < 0:
        return None
    if m >= 60 or s >= 60:
        return None
    return h * 3600 + m * 60 + s


def _scenario_payload(name: str, pace_sec_per_mi: float) -> Dict[str, Any]:
    finish_seconds = pace_sec_per_mi * MARATHON_DISTANCE_MILES
    return {
        "scenario": name,
        "race_pace_sec_per_mi": round(pace_sec_per_mi, 1),
        "race_pace_display": format_pace_sec_per_mi(pace_sec_per_mi),
        "projected_finish_time_seconds": int(round(finish_seconds)),
        "projected_finish_time_display": _format_finish_time(finish_seconds),
    }


def get_marathon_projection(
    session: Session,
    user_id: str,
    *,
    target_race_date: Optional[date] = None,
    goal_time_hhmmss: Optional[str] = None,
    lookback_days: int = 84,
) -> Dict[str, Any]:
    """
    Return a tool-grounded marathon projection based on recent run pace signals.

    Model assumptions are explicit in payload.assumptions:
    - Uses weighted recent run pace from activities over lookback window.
    - If available, uses latest Z2 pace from get_training_progress as aerobic anchor.
    - Projection scenarios map race pace to 10-15% faster than aerobic anchor.
    """
    lookback_days = max(28, min(int(lookback_days), 180))
    cutoff_date = date.today() - timedelta(days=lookback_days)

    rows = session.execute(
        _RECENT_RUNS_SQL,
        {"uid": user_id, "cutoff_date": cutoff_date},
    ).fetchall()
    if not rows:
        return {
            "error": "insufficient_data",
            "message": "Not enough recent run data to project a marathon time.",
            "minimum_needed": "At least one run over 1 mile in the lookback window.",
        }

    weighted_pace_num = 0.0
    weighted_pace_den = 0.0
    total_miles = 0.0
    paces: List[float] = []
    for r in rows:
        distance_m = float(r.distance or 0.0)
        moving_time = int(r.moving_time or 0)
        if distance_m <= 0 or moving_time <= 0:
            continue
        miles = distance_m * M_TO_MI
        if miles <= 0:
            continue
        pace_sec = moving_time / miles
        paces.append(pace_sec)
        weighted_pace_num += pace_sec * miles
        weighted_pace_den += miles
        total_miles += miles

    if weighted_pace_den <= 0 or not paces:
        return {
            "error": "insufficient_data",
            "message": "Recent runs are missing usable pace data for projection.",
        }

    weighted_recent_pace_sec = weighted_pace_num / weighted_pace_den

    kpi = get_training_progress(session, user_id, weeks=8)
    z2_anchor_sec: Optional[float] = None
    if not kpi.get("error"):
        for week in kpi.get("weekly_summaries", []):
            raw = week.get("avg_z2_pace_raw")
            if raw is not None:
                try:
                    z2_anchor_sec = float(raw) * 60.0
                    break
                except (TypeError, ValueError):
                    continue

    aerobic_anchor_sec = z2_anchor_sec or weighted_recent_pace_sec
    scenarios = [
        _scenario_payload("conservative", aerobic_anchor_sec * 0.90),
        _scenario_payload("on_track", aerobic_anchor_sec * 0.875),
        _scenario_payload("stretch", aerobic_anchor_sec * 0.85),
    ]

    out: Dict[str, Any] = {
        "basis": "recent_runs_plus_aerobic_anchor",
        "lookback_days": lookback_days,
        "window": {
            "start_date_inclusive": cutoff_date.isoformat(),
            "end_date_inclusive": date.today().isoformat(),
            "basis": "activity_local_date",
        },
        "data_quality": {
            "recent_runs_count": len(paces),
            "total_recent_miles": round(total_miles, 2),
            "weighted_recent_pace_display": format_pace_sec_per_mi(
                weighted_recent_pace_sec
            ),
            "z2_anchor_available": z2_anchor_sec is not None,
            "z2_anchor_pace_display": (
                format_pace_sec_per_mi(z2_anchor_sec) if z2_anchor_sec else None
            ),
        },
        "scenarios": scenarios,
        "assumptions": [
            "Projection is an estimate, not a guaranteed outcome.",
            "Race pace scenarios are modeled as 10-15% faster than aerobic anchor pace.",
            "Aerobic anchor prefers latest Z2 pace; falls back to weighted recent run pace.",
        ],
        "message": (
            "Use scenario race_pace_display and projected_finish_time_display exactly from this payload "
            "when answering prediction questions."
        ),
    }

    if target_race_date is not None:
        days = (target_race_date - date.today()).days
        out["race_target"] = {
            "target_race_date": target_race_date.isoformat(),
            "days_until_race": days,
            "weeks_until_race": round(days / 7.0, 1),
        }

    goal_secs = _coerce_goal_time_seconds(goal_time_hhmmss)
    if goal_secs is not None:
        out["goal"] = {
            "goal_time_display": _format_finish_time(goal_secs),
            "goal_time_seconds": goal_secs,
            "comparison_vs_goal": [],
        }
        for s in scenarios:
            delta = int(s["projected_finish_time_seconds"]) - goal_secs
            out["goal"]["comparison_vs_goal"].append(
                {
                    "scenario": s["scenario"],
                    "delta_seconds": delta,
                    "delta_display": _format_finish_time(abs(delta)),
                    "status": (
                        "faster_than_goal"
                        if delta < 0
                        else ("on_goal" if delta == 0 else "slower_than_goal")
                    ),
                }
            )

    return out

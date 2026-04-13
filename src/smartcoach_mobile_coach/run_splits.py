"""
Per-lap / per-split payload for coach tools (pace and HR by segment).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.db.dao.activity_dao import ActivityDAO
from src.db.dao.split_dao import get_splits_by_activity_id
from src.smartcoach_mobile_coach.db_helpers import get_primary_athlete_id
from src.smartcoach_mobile_coach.display_format import (
    format_distance_mi,
    format_duration_seconds,
    format_hr_bpm,
    format_pace_sec_per_mi,
)
from src.smartcoach_mobile_coach.run_metrics import (
    distance_miles_from_meters,
    pace_sec_per_mi,
)


def tool_get_run_splits(
    session: Session, internal_user_id: str, activity_id: int
) -> Dict[str, Any]:
    """
    Return ordered lap/split rows for one run (Strava-ingested laps, often ~1 mi each).
    Verifies activity ownership and type Run.
    """
    act = ActivityDAO.get_by_id(session, activity_id)
    primary_aid = get_primary_athlete_id(session, str(internal_user_id))
    if (
        not act
        or str(act.user_id) != str(internal_user_id)
        or primary_aid is None
        or int(act.athlete_id) != int(primary_aid)
    ):
        return {
            "error": "not_found",
            "message": "Activity not found for this user.",
        }
    if (act.type or "") != "Run":
        return {
            "error": "unsupported",
            "message": "Only Run activities support split lookup.",
        }

    rows = get_splits_by_activity_id(session, activity_id)
    if not rows:
        return {
            "activity_id": activity_id,
            "title": (act.name or "Run")[:200],
            "splits": [],
            "splits_count": 0,
            "message": (
                "No lap/split rows stored for this activity. "
                "They are saved during activity sync when Strava lap data is available."
            ),
            "scope": (
                "When present, each row is one lap from ingestion (distance and labeling follow the athlete's "
                "watch/GPS settings — often one mile per row, not guaranteed)."
            ),
        }

    splits_out: List[Dict[str, Any]] = []
    for sp in rows:
        dist_mi: Optional[float] = None
        if sp.conv_distance is not None:
            try:
                dist_mi = float(sp.conv_distance)
            except (TypeError, ValueError):
                dist_mi = None
        if dist_mi is None or dist_mi <= 0:
            dist_mi = distance_miles_from_meters(sp.distance)
        mt = int(sp.moving_time or 0)
        p_sec = pace_sec_per_mi(mt, dist_mi)

        mile_label = sp.split
        if mile_label is not None:
            try:
                segment_label = f"mile {int(mile_label)} (lap {sp.lap_index})"
            except (TypeError, ValueError):
                segment_label = f"lap {sp.lap_index}"
        else:
            segment_label = f"lap {sp.lap_index}"

        splits_out.append(
            {
                "lap_index": int(sp.lap_index),
                "segment_label": segment_label,
                "distance_display": (
                    format_distance_mi(float(dist_mi))
                    if dist_mi and dist_mi > 0
                    else "—"
                ),
                "moving_time_display": format_duration_seconds(mt),
                "avg_pace_display": format_pace_sec_per_mi(p_sec) if p_sec else "—",
                "avg_heart_rate_display": format_hr_bpm(sp.average_heartrate) or "—",
            }
        )

    return {
        "activity_id": activity_id,
        "title": (act.name or "Run")[:200],
        "splits_count": len(splits_out),
        "splits": splits_out,
        "scope": (
            "Each row is one stored lap/split from Strava ingestion. "
            "Distance and segment_label reflect device lap boundaries (often ~1 mi, not guaranteed). "
            "Use these rows for mile-by-mile or lap-by-lap pace and average HR; "
            "session-level drift and KPIs remain on get_run_summary.training_kpis."
        ),
    }

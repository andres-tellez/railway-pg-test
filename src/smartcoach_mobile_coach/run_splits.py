"""
Per-lap / per-split payload for coach tools (pace and HR by segment).

Long runs: split rows are capped (head + tail by lap order) so tool JSON and
LLM context stay bounded. Override with SMARTCOACH_RUN_SPLITS_MAX_ROWS (8–64).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

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


def max_splits_rows_for_coach() -> int:
    """Max split rows returned to the model (head + tail when truncated). Clamped 8–64."""
    raw = (os.getenv("SMARTCOACH_RUN_SPLITS_MAX_ROWS") or "24").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 24
    return max(8, min(n, 64))


def cap_split_rows_for_coach(
    splits_out: List[Dict[str, Any]], max_rows: int
) -> Tuple[List[Dict[str, Any]], bool, int]:
    """
    If splits_out exceeds max_rows, keep the first ceil(max/2) and last floor(max/2)
    laps (by existing lap order) so early warmup and late fade stay visible.
    """
    total = len(splits_out)
    if total <= max_rows or max_rows < 2:
        return splits_out, False, total
    head = (max_rows + 1) // 2
    tail = max_rows - head
    combined = splits_out[:head] + splits_out[-tail:]
    return combined, True, total


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
        if sp.distance is not None:
            try:
                dist_mi = distance_miles_from_meters(float(sp.distance))
            except (TypeError, ValueError):
                dist_mi = None
        if dist_mi is None or dist_mi <= 0:
            dist_mi = None
        if dist_mi is None or dist_mi <= 0:
            try:
                cd = float(sp.conv_distance)
                dist_mi = cd if cd > 0 else None
            except (TypeError, ValueError):
                dist_mi = None
        mt = int(sp.moving_time or 0)
        p_sec = pace_sec_per_mi(mt, dist_mi) if dist_mi and dist_mi > 0 else None
        if p_sec is None and sp.average_speed is not None:
            try:
                mps = float(sp.average_speed)
                if mps > 0:
                    # Strava-style m/s → sec/mi
                    p_sec = 1609.344 / mps
            except (TypeError, ValueError):
                pass

        segment_label = f"Lap {int(sp.lap_index)}"

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

    max_rows = max_splits_rows_for_coach()
    capped, truncated, total_laps = cap_split_rows_for_coach(splits_out, max_rows)
    scope_parts = [
        "Each row is one lap/split segment matching Strava activity split data when available "
        "(otherwise stream-derived miles). Distance is meters per segment; use displayed pace/HR "
        "for coaching copy.",
    ]
    if truncated:
        scope_parts.append(
            f"Payload capped at {max_rows} laps for speed: first and last segments in lap order "
            f"({len(capped)} rows shown of {total_laps} total). Do not infer missing middle laps."
        )

    out: Dict[str, Any] = {
        "activity_id": activity_id,
        "title": (act.name or "Run")[:200],
        "splits_count": len(capped),
        "splits_total_count": total_laps,
        "splits_returned": len(capped),
        "splits_truncated": truncated,
        "splits": capped,
        "scope": " ".join(scope_parts),
    }
    if truncated:
        out["splits_cap"] = {
            "max_rows": max_rows,
            "policy": "head_tail_by_lap_index",
            "omitted_middle_count": max(0, total_laps - len(capped)),
        }
    return out

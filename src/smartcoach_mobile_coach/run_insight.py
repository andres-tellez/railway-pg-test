"""
Build get_run_insight tool payload: facts + comparison (Topic 4 use case).
"""

from __future__ import annotations

import copy
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Integer, bindparam, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from src.db.dao.activity_dao import ActivityDAO
from src.db.models.activities import Activity
from src.smartcoach_mobile_coach.display_format import (
    format_distance_mi,
    format_duration_seconds,
    format_hr_bpm,
    format_pace_sec_per_mi,
    format_time_utc,
    table_row_date_label,
)
from src.smartcoach_mobile_coach.run_metrics import (
    distance_miles_from_meters,
    pace_sec_per_mi,
)
from src.smartcoach_mobile_coach.db_helpers import get_primary_athlete_id
from src.utils.activity_local_date_sql import ACTIVITY_LOCAL_DATE_SQL_FRAGMENT


def _median(vals: List[float]) -> Optional[float]:
    clean = [v for v in vals if v is not None and v > 0]
    if not clean:
        return None
    return float(statistics.median(clean))


def _delta_pace_display(this_sec: float, med_sec: float) -> str:
    d = this_sec - med_sec
    sec_i = int(round(abs(d)))
    m, s = divmod(sec_i, 60)
    bit = f"{m}:{s:02d}/mi"
    if d < 0:
        return f"Avg. pace {bit} faster vs recent median"
    if d > 0:
        return f"Avg. pace {bit} slower vs recent median"
    return "Avg. pace same vs recent median"


def _delta_hr_display(this_hr: float, med_hr: float) -> str:
    d = int(round(this_hr - med_hr))
    if d == 0:
        return "Avg. HR same vs recent median"
    sign = "+" if d > 0 else ""
    return f"Avg. HR {sign}{d} bpm vs recent median"


def _delta_distance_display(this_mi: float, med_mi: float) -> str:
    d = this_mi - med_mi
    if abs(d) < 0.05:
        return "Distance same vs recent median"
    sign = "+" if d > 0 else ""
    return f"Distance {sign}{d:.2f} mi vs recent median"


def _activity_start_utc_iso(start_date: Any) -> Optional[str]:
    """UTC instant for mobile local-time formatting (naive DB values treated as UTC)."""
    if start_date is None:
        return None
    try:
        if not hasattr(start_date, "isoformat"):
            return None
        dt = start_date
        if isinstance(dt, datetime) and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        s = dt.isoformat()
        return s.replace("+00:00", "Z") if s.endswith("+00:00") else s
    except Exception:
        return None


def _fetch_activity_context(
    session: Session, internal_user_id: str, activity_id: int
) -> Optional[Tuple[Any, ...]]:
    athlete_id = get_primary_athlete_id(session, str(internal_user_id))
    if athlete_id is None:
        return None
    q = text(
        f"""
        SELECT
            activity_id,
            ({ACTIVITY_LOCAL_DATE_SQL_FRAGMENT}) AS local_date,
            start_date,
            name,
            distance,
            moving_time,
            average_heartrate,
            type
        FROM public.activities
        WHERE activity_id = :aid
          AND user_id = :uid
          AND athlete_id = :athlete_id
        """
    ).bindparams(
        bindparam("uid", type_=PGUUID),
        bindparam("athlete_id", type_=Integer),
    )
    row = session.execute(
        q,
        {"aid": activity_id, "uid": internal_user_id, "athlete_id": athlete_id},
    ).fetchone()
    return row


def _peer_activities_before(
    session: Session, athlete_id: int, before_start, exclude_id: int, limit: int = 10
) -> List[Activity]:
    return (
        session.query(Activity)
        .filter(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.activity_id != exclude_id,
            Activity.start_date < before_start,
        )
        .order_by(Activity.start_date.desc())
        .limit(limit)
        .all()
    )


def build_get_run_insight_payload(
    session: Session,
    internal_user_id: str,
    activity_id: int,
    schema_version: str,
    *,
    include_peer_comparison: bool = True,
) -> Dict[str, Any]:
    row = _fetch_activity_context(session, internal_user_id, activity_id)
    if not row:
        return {"error": "not_found", "message": "Activity not found for this user."}

    _aid, local_date, start_date, name, distance_m, moving_time, avg_hr, act_type = row
    if (act_type or "") != "Run":
        return {"error": "unsupported", "message": "Only Run activities are supported."}

    distance_mi = distance_miles_from_meters(distance_m)
    pace_sec = pace_sec_per_mi(moving_time, distance_mi)
    act = ActivityDAO.get_by_id(session, activity_id)
    primary_aid = get_primary_athlete_id(session, str(internal_user_id))
    if (
        not act
        or str(act.user_id) != str(internal_user_id)
        or primary_aid is None
        or int(act.athlete_id) != int(primary_aid)
    ):
        return {"error": "not_found", "message": "Activity not found for this user."}

    local_date_str = (
        local_date.isoformat()
        if local_date and hasattr(local_date, "isoformat")
        else str(local_date or "")
    )

    facts: Dict[str, Any] = {
        "title": (name or "Run")[:200],
        "local_date": local_date_str,
        "start_time_utc_iso": _activity_start_utc_iso(start_date),
        "start_local_time_display": format_time_utc(start_date),
        "distance_display": format_distance_mi(distance_mi),
        "moving_time_display": format_duration_seconds(int(moving_time or 0)),
        "avg_pace_display": format_pace_sec_per_mi(pace_sec) if pace_sec else "—",
        "avg_heart_rate_display": format_hr_bpm(avg_hr) or "—",
        "max_heart_rate_display": format_hr_bpm(act.max_heartrate) or "—",
        "sport_type": "run",
    }
    if act.executed_type or act.run_score:
        facts["execution_summary"] = {
            "matched_plan_workout_id": act.matched_plan_workout_id,
            "planned_type": act.planned_type,
            "executed_type": act.executed_type,
            "zone_compliance_pct": act.zone_compliance_pct,
            "pct_above_zone": act.pct_above_zone,
            "pct_below_zone": act.pct_below_zone,
            "run_score": act.run_score,
            "planned_miles": act.planned_miles,
            "actual_miles": act.actual_miles,
            "completion_pct": act.completion_pct,
        }

    if not include_peer_comparison:
        return {
            "schema_version": schema_version,
            "activity_id": activity_id,
            "facts": facts,
        }

    peers = _peer_activities_before(
        session, act.athlete_id, act.start_date, activity_id, limit=10
    )[:5]

    peer_rows: List[Dict[str, Any]] = []
    peer_paces: List[float] = []
    peer_hrs: List[float] = []
    peer_dists: List[float] = []

    for p in peers:
        p_mi = distance_miles_from_meters(p.distance)
        p_pace = pace_sec_per_mi(p.moving_time, p_mi)
        p_hr = float(p.average_heartrate) if p.average_heartrate is not None else None
        if p_pace:
            peer_paces.append(p_pace)
        if p_hr:
            peer_hrs.append(p_hr)
        if p_mi > 0:
            peer_dists.append(p_mi)
        ld_iso: Optional[str] = None
        try:
            pr = _fetch_activity_context(session, internal_user_id, int(p.activity_id))
            if pr and pr[1]:
                raw_ld = pr[1]
                if hasattr(raw_ld, "isoformat"):
                    ld_iso = raw_ld.isoformat()
                else:
                    s = str(raw_ld)
                    ld_iso = s[:10] if len(s) >= 10 else None
        except Exception:
            pass
        peer_rows.append(
            {
                "local_date_iso": ld_iso,
                "activity_id": int(p.activity_id),
                "distance_display": format_distance_mi(p_mi),
                "avg_pace_display": format_pace_sec_per_mi(p_pace) if p_pace else "—",
                "avg_heart_rate_display": format_hr_bpm(p.average_heartrate) or "—",
            }
        )

    med_pace = _median(peer_paces)
    med_hr = _median(peer_hrs)
    med_dist = _median(peer_dists)

    delta_block = None
    if peer_rows and pace_sec and med_pace:
        delta_block = {
            "avg_pace": _delta_pace_display(pace_sec, med_pace),
            "avg_heart_rate": (
                _delta_hr_display(float(avg_hr), med_hr)
                if avg_hr is not None and med_hr
                else None
            ),
            "distance": (
                _delta_distance_display(distance_mi, med_dist) if med_dist else None
            ),
        }

    local_date_str = (
        local_date.isoformat()
        if local_date and hasattr(local_date, "isoformat")
        else str(local_date or "")
    )

    payload: Dict[str, Any] = {
        "schema_version": schema_version,
        "activity_id": activity_id,
        "facts": {
            "title": (name or "Run")[:200],
            "local_date": local_date_str,
            "start_time_utc_iso": _activity_start_utc_iso(start_date),
            "start_local_time_display": format_time_utc(start_date),
            "distance_display": format_distance_mi(distance_mi),
            "moving_time_display": format_duration_seconds(int(moving_time or 0)),
            "avg_pace_display": format_pace_sec_per_mi(pace_sec) if pace_sec else "—",
            "avg_heart_rate_display": format_hr_bpm(avg_hr) or "—",
            "max_heart_rate_display": format_hr_bpm(act.max_heartrate) or "—",
            "sport_type": "run",
            "execution_summary": facts.get("execution_summary"),
        },
        "comparison": {
            "peer_criteria_summary": "Up to 5 prior runs for this athlete before this activity",
            "peers_count": len(peer_rows),
            "this_run": {
                "local_date_iso": local_date_str or None,
                "activity_id": activity_id,
                "distance_display": format_distance_mi(distance_mi),
                "avg_pace_display": (
                    format_pace_sec_per_mi(pace_sec) if pace_sec else "—"
                ),
                "avg_heart_rate_display": format_hr_bpm(avg_hr) or "—",
                "max_heart_rate_display": format_hr_bpm(act.max_heartrate) or "—",
            },
            "peer_runs": peer_rows,
            "delta_vs_peer_median_display": delta_block,
        },
    }
    return payload


def apply_insight_table_labels(
    payload: Dict[str, Any], anchor_yyyy_mm_dd: Optional[str]
) -> Dict[str, Any]:
    """
    Add row `label` for comparison tables (Today vs MM-DD) using device anchor date.
    Cached payloads are canonical; this runs on every tool response.
    """
    if not payload or payload.get("error"):
        return payload
    out = copy.deepcopy(payload)
    anchor = (anchor_yyyy_mm_dd or "").strip()[:10]
    if len(anchor) < 10:
        anchor = None

    comp = out.get("comparison")
    if not comp:
        return out

    comp = dict(comp)
    this_run = dict(comp.get("this_run") or {})
    iso = this_run.get("local_date_iso")
    if not iso:
        facts = out.get("facts") or {}
        iso = facts.get("local_date")
    this_run["label"] = table_row_date_label(iso, anchor)
    comp["this_run"] = this_run

    peers = []
    for row in comp.get("peer_runs") or []:
        r = dict(row)
        r["label"] = table_row_date_label(r.get("local_date_iso"), anchor)
        peers.append(r)
    comp["peer_runs"] = peers
    out["comparison"] = comp
    return out

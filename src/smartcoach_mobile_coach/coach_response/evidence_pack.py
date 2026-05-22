"""
Coach response evidence pack (MVP: easy/Z2 only).

This module prepares compact factual evidence for coach response turns.
It intentionally avoids deterministic coaching verdict labels.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from statistics import fmean
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.activities import Activity
from src.services.recent_run_rollup import compute_recent_run_rollup_for_user
from src.services.scoring.zone_compliance import zone_distribution_from_activity
from src.services.user.user_context import build_user_context_payload
from src.smartcoach_mobile_coach.coach_response.context import WorkoutIntent
from src.smartcoach_mobile_coach.db_helpers import get_primary_athlete_id
from src.smartcoach_mobile_coach.display_format import (
    format_distance_mi,
    format_hr_bpm,
    format_pace_sec_per_mi,
)
from src.smartcoach_mobile_coach.run_metrics import (
    distance_miles_from_meters,
    pace_sec_per_mi,
)
from src.smartcoach_mobile_coach.training_kpi_service import get_training_progress

EVIDENCE_PACK_VERSION = "coach_response_evidence_pack_v1_easy"
SIMILAR_MAX_ROWS = 5
SIMILAR_LOOKBACK_DAYS = 56
EVIDENCE_PACK_MAX_CHARS = 1800

_EASY_TYPES = {"easy", "recovery"}
_HARD_TYPES = {
    "tempo",
    "threshold",
    "interval",
    "intervals",
    "speed",
    "progression",
    "race",
}


def _parse_uuid(raw: str) -> Optional[UUID]:
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


def _safe_iso_day(raw: str) -> date:
    token = str(raw or "")[:10]
    try:
        return date.fromisoformat(token)
    except ValueError:
        return datetime.utcnow().date()


def _is_easy_mvp_turn(intent: WorkoutIntent, is_easy_run: Optional[bool]) -> bool:
    planned = (intent.planned_type or "").strip().lower()
    if planned in _EASY_TYPES:
        return True
    return bool(is_easy_run)


def _as_distance_mi(act: Activity) -> Optional[float]:
    try:
        if act.distance is None:
            return None
        return float(distance_miles_from_meters(float(act.distance)))
    except (TypeError, ValueError):
        return None


def _as_avg_pace_sec_per_mi(act: Activity) -> Optional[float]:
    mi = _as_distance_mi(act)
    try:
        return pace_sec_per_mi(int(act.moving_time or 0), mi or 0.0)
    except (TypeError, ValueError):
        return None


def _zone_dist_pct(act: Activity) -> Optional[Dict[str, float]]:
    try:
        dist = zone_distribution_from_activity(act)
    except Exception:
        return None
    if not isinstance(dist, dict):
        return None
    out = {f"z{k}": round(float(v), 2) for k, v in dist.items() if isinstance(k, int)}
    if not out or sum(out.values()) <= 0:
        return None
    return out


def _activity_row_for_similarity(act: Activity) -> Dict[str, Any]:
    mi = _as_distance_mi(act)
    psec = _as_avg_pace_sec_per_mi(act)
    avg_hr = float(act.average_heartrate) if act.average_heartrate is not None else None
    max_hr = float(act.max_heartrate) if act.max_heartrate is not None else None
    day_iso = act.start_date.date().isoformat() if act.start_date else None
    return {
        "local_date_iso": day_iso,
        "executed_type": (act.executed_type or "").strip().lower() or None,
        "planned_type": (act.planned_type or "").strip().lower() or None,
        "distance_display": format_distance_mi(mi) if mi is not None else "—",
        "distance_mi": round(mi, 2) if mi is not None else None,
        "avg_pace_display": format_pace_sec_per_mi(psec) if psec else "—",
        "avg_pace_sec_per_mi": round(float(psec), 2) if psec else None,
        "avg_hr_display": format_hr_bpm(avg_hr) or "—",
        "avg_hr_bpm": round(avg_hr, 1) if avg_hr is not None else None,
        "max_hr_display": format_hr_bpm(max_hr) or "—",
        "max_hr_bpm": round(max_hr, 1) if max_hr is not None else None,
        "time_in_zones_pct": _zone_dist_pct(act),
    }


def _select_similar_runs(
    current: Activity, candidates: List[Activity]
) -> Tuple[str, List[Activity]]:
    executed = [
        a for a in candidates if (a.executed_type or "").strip().lower() in _EASY_TYPES
    ]
    if len(executed) >= 3:
        return "executed_type", executed[:SIMILAR_MAX_ROWS]

    planned = [
        a for a in candidates if (a.planned_type or "").strip().lower() in _EASY_TYPES
    ]
    if len(planned) >= 3:
        return "planned_type", planned[:SIMILAR_MAX_ROWS]

    cur_mi = _as_distance_mi(current)
    if cur_mi and cur_mi > 0:
        low = cur_mi * 0.85
        high = cur_mi * 1.15
        band = [
            a
            for a in candidates
            if (_as_distance_mi(a) or 0.0) >= low
            and (_as_distance_mi(a) or 0.0) <= high
        ]
        if len(band) >= 3:
            return "distance_band", band[:SIMILAR_MAX_ROWS]

    return "none", []


def _simple_deltas(current: Activity, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    cohort_paces = [
        float(r["avg_pace_sec_per_mi"])
        for r in rows
        if r.get("avg_pace_sec_per_mi") is not None
    ]
    cohort_hrs = [
        float(r["avg_hr_bpm"]) for r in rows if r.get("avg_hr_bpm") is not None
    ]
    cohort_dists = [
        float(r["distance_mi"]) for r in rows if r.get("distance_mi") is not None
    ]
    current_pace = _as_avg_pace_sec_per_mi(current)
    current_hr = (
        float(current.average_heartrate)
        if current.average_heartrate is not None
        else None
    )

    avg_pace = fmean(cohort_paces) if cohort_paces else None
    avg_hr = fmean(cohort_hrs) if cohort_hrs else None
    avg_dist = fmean(cohort_dists) if cohort_dists else None

    pace_delta = (
        (current_pace - avg_pace)
        if current_pace is not None and avg_pace is not None
        else None
    )
    hr_delta = (
        (current_hr - avg_hr) if current_hr is not None and avg_hr is not None else None
    )

    return {
        "cohort": {
            "count": len(rows),
            "avg_pace_sec_per_mi": round(avg_pace, 2) if avg_pace is not None else None,
            "avg_pace_display": format_pace_sec_per_mi(avg_pace) if avg_pace else None,
            "avg_hr_bpm": round(avg_hr, 1) if avg_hr is not None else None,
            "avg_distance_mi": round(avg_dist, 2) if avg_dist is not None else None,
        },
        "today_vs_cohort": {
            "pace_delta_sec_per_mi": (
                round(pace_delta, 2) if pace_delta is not None else None
            ),
            "pace_delta_display": (
                f"{'-' if pace_delta < 0 else '+'}{format_pace_sec_per_mi(abs(pace_delta) or 0)}"
                if pace_delta is not None
                else None
            ),
            "hr_delta_bpm": round(hr_delta, 1) if hr_delta is not None else None,
            "hr_delta_display": (
                f"{'+' if hr_delta >= 0 else ''}{round(hr_delta, 1)} bpm"
                if hr_delta is not None
                else None
            ),
        },
    }


def _goal_phase_context(
    *, session: Session, internal_user_id: str, today: date
) -> Dict[str, Any]:
    uid = _parse_uuid(internal_user_id)
    if uid is None:
        return {"race": None, "phase": None}
    payload = build_user_context_payload(
        session=session,
        user_id=uid,
        tz="UTC",
        today=today,
    )
    if not isinstance(payload, dict):
        return {"race": None, "phase": None}
    race = (
        payload.get("race_goal") if isinstance(payload.get("race_goal"), dict) else None
    )
    plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else None
    phase = None
    if isinstance(plan, dict):
        phase = {
            "label": plan.get("current_phase"),
            "week_in_phase": plan.get("current_week_number"),
            "phase_priority": plan.get("phase_kpi_priority"),
        }
    return {"race": race, "phase": phase}


def _recent_load_context(
    *,
    session: Session,
    internal_user_id: str,
    today: date,
    recent_candidates: List[Activity],
) -> Dict[str, Any]:
    uid = _parse_uuid(internal_user_id)
    rollup = (
        compute_recent_run_rollup_for_user(session, uid, today=today)
        if uid is not None
        else {}
    )
    weekly = get_training_progress(session, str(internal_user_id), weeks=4)
    mileage_4w: Optional[List[int]] = None
    if isinstance(weekly, dict) and isinstance(weekly.get("weekly_summaries"), list):
        vals: List[int] = []
        for row in weekly.get("weekly_summaries", [])[:4]:
            if not isinstance(row, dict):
                continue
            miles = row.get("total_miles")
            try:
                vals.append(int(round(float(miles))))
            except (TypeError, ValueError):
                continue
        if vals:
            mileage_4w = list(reversed(vals))

    last_hard = None
    for act in recent_candidates:
        t = (act.executed_type or "").strip().lower()
        if t in _HARD_TYPES:
            day = act.start_date.date() if act.start_date else None
            last_hard = {
                "executed_type": t,
                "days_ago": ((today - day).days if day else None),
                "local_date_iso": (day.isoformat() if day else None),
            }
            break

    longest_m = rollup.get("longest_run_meters_28d")
    return {
        "runs_28d": rollup.get("runs_28d"),
        "weeks_with_runs_28d": rollup.get("weeks_with_runs_28d"),
        "longest_run_mi_28d": (
            round(distance_miles_from_meters(float(longest_m)), 2)
            if longest_m is not None
            else None
        ),
        "mileage_4w_mi": mileage_4w,
        "last_hard_workout": last_hard,
    }


def _trim_to_budget(pack: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    def _size() -> int:
        return len(json.dumps(pack, separators=(",", ":"), default=str))

    while _size() > EVIDENCE_PACK_MAX_CHARS and pack["similar_runs"]["rows"]:
        pack["similar_runs"]["rows"].pop()
    if _size() > EVIDENCE_PACK_MAX_CHARS:
        for row in pack["similar_runs"]["rows"]:
            row.pop("time_in_zones_pct", None)
    if _size() > EVIDENCE_PACK_MAX_CHARS and isinstance(pack.get("load"), dict):
        pack["load"]["mileage_4w_mi"] = None
    return pack, _size()


def build_evidence_pack(
    *,
    session: Session,
    internal_user_id: str,
    activity_id: int,
    anchor_local_date: str,
    facts: Dict[str, Any],
    workout_intent: WorkoutIntent,
    is_easy_run: Optional[bool],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Build evidence pack for easy/Z2 coach-response turns."""
    trace: Dict[str, Any] = {
        "enabled": True,
        "version": EVIDENCE_PACK_VERSION,
        "present": False,
        "reason": None,
    }
    if not _is_easy_mvp_turn(workout_intent, is_easy_run):
        trace["reason"] = "non_easy_turn"
        return None, trace

    athlete_id = get_primary_athlete_id(session, str(internal_user_id))
    current = (
        session.query(Activity)
        .filter(Activity.activity_id == int(activity_id))
        .one_or_none()
    )
    if current is None or athlete_id is None:
        trace["reason"] = "missing_activity_or_athlete"
        return None, trace

    today = _safe_iso_day(anchor_local_date)
    before = datetime.combine(today, datetime.max.time())
    candidates = (
        session.query(Activity)
        .filter(
            Activity.athlete_id == int(athlete_id),
            Activity.type == "Run",
            Activity.activity_id != int(activity_id),
            Activity.start_date < before,
        )
        .order_by(Activity.start_date.desc())
        .limit(80)
        .all()
    )
    basis, similar = _select_similar_runs(current, candidates)
    similar_rows = [_activity_row_for_similarity(a) for a in similar[:SIMILAR_MAX_ROWS]]
    lookback_start = (
        today.fromordinal(today.toordinal() - SIMILAR_LOOKBACK_DAYS)
    ).isoformat()
    lookback_end = today.isoformat()

    execution = facts.get("execution_summary") if isinstance(facts, dict) else {}
    planned = execution.get("planned") if isinstance(execution, dict) else {}
    pack: Dict[str, Any] = {
        "version": EVIDENCE_PACK_VERSION,
        "current_run": {
            "distance": facts.get("distance_display"),
            "duration": facts.get("moving_time_display"),
            "avg_pace": facts.get("avg_pace_display"),
            "avg_hr": facts.get("avg_heart_rate_display"),
            "max_hr": facts.get("max_heart_rate_display"),
            "time_in_zones_pct": _zone_dist_pct(current),
            "total_elevation_gain_m": (
                round(float(current.total_elevation_gain), 1)
                if current.total_elevation_gain is not None
                else None
            ),
            "conditions": None,
        },
        "planned": {
            "planned_type": planned.get("type") if isinstance(planned, dict) else None,
            "planned_miles": (
                planned.get("miles") if isinstance(planned, dict) else None
            ),
            "target_zone": (
                planned.get("target_zone") if isinstance(planned, dict) else None
            ),
            "target_hr": (
                planned.get("target_hr") if isinstance(planned, dict) else None
            ),
            "plan_status": (
                execution.get("plan_status") if isinstance(execution, dict) else None
            ),
            "violated_rest_day": (
                execution.get("violated_rest_day")
                if isinstance(execution, dict)
                else None
            ),
        },
        "similar_runs": {
            "selection_basis": basis,
            "window": {
                "lookback_days": SIMILAR_LOOKBACK_DAYS,
                "start_date_iso": lookback_start,
                "end_date_iso": lookback_end,
                "sample_size": len(similar_rows),
                "max_rows": SIMILAR_MAX_ROWS,
            },
            "rows": similar_rows,
        },
        "similar_deltas": _simple_deltas(current, similar_rows),
        "goal_phase": _goal_phase_context(
            session=session,
            internal_user_id=internal_user_id,
            today=today,
        ),
        "load": _recent_load_context(
            session=session,
            internal_user_id=internal_user_id,
            today=today,
            recent_candidates=candidates[:30],
        ),
    }
    pack, size_chars = _trim_to_budget(pack)
    final_rows = pack["similar_runs"]["rows"]
    pack["similar_runs"]["window"]["sample_size"] = len(final_rows)
    pack["similar_deltas"] = _simple_deltas(current, final_rows)
    trace.update(
        {
            "present": True,
            "size_chars": size_chars,
            "selection_basis": basis,
            "similar_runs_count": len(final_rows),
            "sample_size": int(pack["similar_runs"]["window"]["sample_size"]),
            "lookback_days": SIMILAR_LOOKBACK_DAYS,
        }
    )
    return pack, trace

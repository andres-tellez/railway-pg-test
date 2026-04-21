"""
Build get_run_insight tool payload: facts + comparison (Topic 4 use case).
"""

from __future__ import annotations

import copy
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import Integer, bindparam, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from src.db.dao.activity_dao import ActivityDAO
from src.db.models.activities import Activity
from src.services.plan.plan_status import (
    PlanStatus,
    derive_violated_rest_day,
    plan_status_for_activity,
)
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


# ---------------------------------------------------------------------------
# V1.6 Pre-Phase A 0.A — Canonical planned.* / actual.* execution block.
#
# SINGLE SOURCE OF TRUTH for per-run plan-vs-actual field extraction from
# the ``Activity`` row. Both ``get_run_summary`` (LLM tool) and
# ``GET /api/plan/current-week`` (mobile route) MUST consume this builder
# via one of the legacy shape adapters below. No caller may read planned
# or actual fields directly off ``Activity`` for payload construction.
#
# Shape rationale (V1.6 §6, SMARTCOACH_SYSTEM_SPEC_V1.md):
#   - ``planned.*`` holds fields committed at plan-creation time.
#   - ``actual.*`` holds fields derived from the executed activity.
#   - Metadata fields (``matched_plan_workout_id``, ``activity_id``,
#     ``start_date``) live outside the namespaces — they describe the
#     link, not a side of the plan-vs-actual contract.
#
# Adapter strategy during V1.6 transition:
#   - Mobile and the LLM tool still consume flat shapes today. The two
#     adapter helpers (``execution_block_to_weekly_plan_shape`` and
#     ``execution_block_to_insight_summary_shape``) preserve those
#     byte-exact shapes so 0.A is a behavior-preserving refactor.
#   - 0.E (mobile refactor) and Phase B (new plan-aware tools) will
#     consume the namespaced block directly, at which point the
#     legacy adapters can be deprecated.
# ---------------------------------------------------------------------------


def _avg_pace_per_mile_display_from_activity(act: Any) -> Optional[str]:
    """M:SS/mi from activity ``conv_distance`` and ``moving_time``.

    Moved here from ``plan_routes.py`` as part of 0.A so the weekly-plan
    adapter has no dependency on ``plan_routes`` internals.
    """
    mi = getattr(act, "conv_distance", None)
    mt = getattr(act, "moving_time", None)
    if not mi or mi <= 0 or not mt or mt <= 0:
        return None
    sec_per_mi = float(mt) / float(mi)
    total_sec = int(round(sec_per_mi))
    m = total_sec // 60
    s = total_sec % 60
    if s == 60:
        m += 1
        s = 0
    return f"{m}:{s:02d}/mi"


def build_run_execution_block(
    act: Any,
    *,
    plan_training_days: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Canonical V1.6 planned.* / actual.* block for one activity.

    This is the **only** place where planned / actual fields are read
    off an ``Activity`` for payload construction. All downstream
    payloads (weekly plan day.execution, get_run_summary
    execution_summary, future Phase B plan-aware tools) flow from this
    dict.

    Returns a dict with five top-level keys:

    * ``matched_plan_workout_id`` — FK to ``plan_workouts.id`` (``None``
      when the activity is unplanned).
    * ``plan_status`` — V1.6 §6 enum string (``"executed"`` when linked,
      ``"unplanned"`` otherwise). Derived via
      ``src.services.plan.plan_status.plan_status_for_activity`` —
      the single source of truth for this field. Lives at top level
      (neither ``planned.*`` nor ``actual.*``) because it describes
      the pairing between the two sides, not a side of it.
    * ``violated_rest_day`` — V1.6 §6 derived flag (Phase A item 2).
      ``True`` iff ``plan_status == "unplanned"`` and the activity's
      weekday is not among ``plan_training_days``. ``False`` otherwise,
      including when ``plan_training_days`` is ``None`` (safe default
      — coach §19 must not escalate on ambiguous plan metadata).
      Derived via
      ``src.services.plan.plan_status.derive_violated_rest_day``.
    * ``planned`` — fields populated at plan-creation time.
    * ``actual`` — fields derived from the executed activity.

    Args:
        act: ``Activity`` or duck-typed object with the attributes
            read by the ``getattr`` calls below.
        plan_training_days: ``plan.training_days`` (nullable array of
            day-name strings, full or abbreviated). Keyword-only to
            keep the positional contract backward-compatible. When
            ``None`` the ``violated_rest_day`` flag degrades to
            ``False`` per spec "false otherwise".

    Absent (unlinked) vs null: a ``None`` value means "checked, no
    value"; the per-key presence always holds (V1.6 §4 null-vs-absent
    convention). Shape adapters may drop keys to match legacy shapes.
    """
    matched_pw_id = getattr(act, "matched_plan_workout_id", None)
    plan_status = plan_status_for_activity(matched_pw_id)
    # violated_rest_day only requires weekday-lookup on the UNPLANNED
    # branch. For EXECUTED the flag is unconditionally False (a day
    # with a planned workout is by definition not a rest day), and
    # we skip reading start_date so the function stays cheap and
    # tolerant of duck-typed inputs without a start_date attribute.
    if plan_status == PlanStatus.UNPLANNED:
        start_date = getattr(act, "start_date", None)
        day_weekday = start_date.weekday() if start_date is not None else None
        violated = (
            derive_violated_rest_day(
                plan_status_value=plan_status,
                day_weekday=day_weekday,
                plan_training_days=plan_training_days,
            )
            if day_weekday is not None
            else False
        )
    else:
        violated = False
    return {
        "matched_plan_workout_id": matched_pw_id,
        "plan_status": plan_status.value,
        "violated_rest_day": violated,
        "planned": {
            "type": getattr(act, "planned_type", None),
            "miles": getattr(act, "planned_miles", None),
        },
        "actual": {
            "type": getattr(act, "executed_type", None),
            "miles": getattr(act, "actual_miles", None),
            "completion_pct": getattr(act, "completion_pct", None),
            "run_score": getattr(act, "run_score", None),
            "zone_compliance_pct": getattr(act, "zone_compliance_pct", None),
            "pct_above_zone": getattr(act, "pct_above_zone", None),
            "pct_below_zone": getattr(act, "pct_below_zone", None),
            "scoring_detail": getattr(act, "scoring_detail", None),
            "average_heartrate": getattr(act, "average_heartrate", None),
        },
    }


def execution_block_to_weekly_plan_shape(
    block: Dict[str, Any], act: Any
) -> Dict[str, Any]:
    """
    Adapter for ``GET /api/plan/current-week`` and mobile
    ``CurrentWeekExecutionPayload`` (smartcoach_app/lib/api/plan.ts).

    V1.6 0.E — dual-emit shape:

    - **Canonical V1.6 §6 namespaced blocks:** ``planned`` and ``actual``
      sub-objects. New mobile consumers (``weekly-plan-panel.tsx`` as
      of 0.E) and Phase B plan-aware tools MUST read from these.
      ``actual`` is a display-augmented variant of the canonical
      block's ``actual`` — ``average_heartrate`` is rounded to an int
      for UI and ``avg_pace_per_mile`` is the formatted M:SS/mi string.

    - **Legacy flat fields (DEPRECATED post-Phase B):** kept for
      backward compatibility with any non-0.E consumer. Every flat
      field is sourced from the same canonical block as the nested
      namespaces, so they cannot drift. Once all consumers have
      migrated to ``planned.*`` / ``actual.*``, these can be removed
      in a separate PR.
    """
    planned = block.get("planned") or {}
    actual = block.get("actual") or {}
    avg_hr = actual.get("average_heartrate")
    avg_hr_display = int(round(avg_hr)) if avg_hr is not None else None
    pace_display = _avg_pace_per_mile_display_from_activity(act)

    # Display-augmented actual block: rounded HR + formatted pace for UI,
    # while preserving all raw KPI fields for the LLM.
    actual_namespaced: Dict[str, Any] = {
        **actual,
        "average_heartrate": avg_hr_display,
        "avg_pace_per_mile": pace_display,
    }

    start_date = getattr(act, "start_date", None)
    start_date_iso = (
        start_date.isoformat()
        if start_date and hasattr(start_date, "isoformat")
        else None
    )

    return {
        "activity_id": int(act.activity_id),
        "start_date": start_date_iso,
        "matched_plan_workout_id": block.get("matched_plan_workout_id"),
        # V1.6 §6 canonical namespaced shape — 0.E mobile reads from here.
        "planned": dict(planned),
        "actual": actual_namespaced,
        # Legacy flat fields — DEPRECATED post-Phase B. Sourced from
        # the same canonical block, so they cannot drift from the
        # namespaced shape above.
        "planned_type": planned.get("type"),
        "executed_type": actual.get("type"),
        "run_score": actual.get("run_score"),
        "zone_compliance_pct": actual.get("zone_compliance_pct"),
        "planned_miles": planned.get("miles"),
        "actual_miles": actual.get("miles"),
        "completion_pct": actual.get("completion_pct"),
        "scoring_detail": actual.get("scoring_detail"),
        "average_heartrate": avg_hr_display,
        "avg_pace_per_mile": pace_display,
    }


def execution_block_to_insight_summary_shape(
    block: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Adapter for the LLM ``get_run_summary`` tool's
    ``facts.execution_summary``.

    Surfaces all pre-0.A fields plus V1.6 Phase A additions
    (``plan_status`` — Phase A item 1; further Phase A fields follow
    in subsequent commits). Single source: every value comes from the
    canonical ``block`` produced by ``build_run_execution_block``.
    Phase B tools will read ``block`` directly and this adapter will
    be deprecated.
    """
    planned = block.get("planned") or {}
    actual = block.get("actual") or {}
    return {
        "matched_plan_workout_id": block.get("matched_plan_workout_id"),
        "plan_status": block.get("plan_status"),
        "violated_rest_day": block.get("violated_rest_day"),
        "planned_type": planned.get("type"),
        "executed_type": actual.get("type"),
        "zone_compliance_pct": actual.get("zone_compliance_pct"),
        "pct_above_zone": actual.get("pct_above_zone"),
        "pct_below_zone": actual.get("pct_below_zone"),
        "run_score": actual.get("run_score"),
        "planned_miles": planned.get("miles"),
        "actual_miles": actual.get("miles"),
        "completion_pct": actual.get("completion_pct"),
    }


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
    # V1.6 0.A: sourced from the single canonical planned.* / actual.* block.
    if act.executed_type or act.run_score:
        facts["execution_summary"] = execution_block_to_insight_summary_shape(
            build_run_execution_block(act)
        )

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
            **facts,
            "local_date": local_date_str,
            # Preserve pre-0.A behavior: the full-payload branch always
            # surfaced ``execution_summary`` as a key (possibly ``None``),
            # even when the short branch above had not populated it.
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

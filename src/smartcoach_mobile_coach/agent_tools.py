"""Execute agent tools (server-side). Returns JSON-serializable dict."""

from __future__ import annotations

import json
import logging
import warnings
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from src.db.dao.activity_dao import ActivityDAO
from src.smartcoach_mobile_coach.config import INSIGHT_SCHEMA_VERSION
from src.smartcoach_mobile_coach.db_helpers import (
    fetch_user_hr_profile_for_coach,
    get_primary_athlete_id,
)
from src.smartcoach_mobile_coach.display_format import (
    format_distance_mi,
    format_time_utc,
)
from src.smartcoach_mobile_coach.insight_cache import cache_key, get_cached, set_cached
from src.smartcoach_mobile_coach.marathon_projection_service import (
    get_marathon_projection,
)
from src.smartcoach_mobile_coach.plan_intake_flow import (
    build_plan_request_from_state,
    summarize_this_week_from_plan_rows,
    update_plan_intake_state,
)
from src.smartcoach_mobile_coach.run_insight import (
    apply_insight_table_labels,
    build_get_run_insight_payload,
)
from src.smartcoach_mobile_coach.run_metrics import distance_miles_from_meters
from src.smartcoach_mobile_coach.run_splits import tool_get_run_splits
from src.smartcoach_mobile_coach.training_kpi_service import (
    get_run_kpi_detail,
    get_training_progress,
)
from src.smartcoach_mobile_coach.weekly_insights_service import (
    get_latest_weekly_insight,
    weekly_insight_tool_slim_default_from_env,
)
from src.routes.plan_generation_v2 import run_v2_plan_generation
from src.services.training_plan.plan_storage_service import PlanStorageService
from src.utils.config import config
from src.utils.hr_zone_constants import (
    ALLOWED_METRICS,
    COACHING_LEVEL_DEFAULTS,
    hr_drift_band_zones_chart,
)

logger = logging.getLogger("smartcoach_mobile_coach")

_DEFAULT_KPI_WEEKS = 4
_MAX_KPI_WEEKS = 52


def _increment_tool_call_count(session: Session, tool_name: str) -> None:
    """Best-effort counter bump; never blocks the tool response."""
    try:
        session.execute(
            text(
                "UPDATE coach_tools "
                "SET call_count = call_count + 1, last_called_at = now() "
                "WHERE name = :name"
            ),
            {"name": tool_name},
        )
        session.commit()
    except Exception:
        logger.debug("Could not increment call_count for %s", tool_name, exc_info=True)


def _parse_activity_id(args: Dict[str, Any]) -> Optional[int]:
    raw = args.get("activity_id")
    try:
        aid = int(raw)
    except (TypeError, ValueError):
        return None
    return aid if aid > 0 else None


def _coerce_tool_bool(value: Any, default: bool) -> bool:
    """Parse optional boolean tool args from JSON (bool, string, or int)."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no"):
            return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    return default


def _parse_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_optional_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_get_run_summary_include_flags(
    args: Dict[str, Any],
) -> tuple[bool, bool, bool]:
    """
    Optional sections for get_run_summary (defaults all True = backward compatible).

    - include_peer_comparison: peer table + deltas vs recent runs
    - include_execution_kpis: v_easy_runs KPIs + zone_bounds + is_easy_run
    - include_hr_profile: user_hr_zones profile (Z1–Z5, max/resting used)
    """
    return (
        _coerce_tool_bool(args.get("include_peer_comparison"), True),
        _coerce_tool_bool(args.get("include_execution_kpis"), True),
        _coerce_tool_bool(args.get("include_hr_profile"), True),
    )


# ---------------------------------------------------------------------------
# Tool: find_runs_by_date
# ---------------------------------------------------------------------------


def tool_find_runs_by_date(
    session: Session, internal_user_id: str, local_date: str
) -> Dict[str, Any]:
    try:
        d = datetime.strptime(str(local_date).strip(), "%Y-%m-%d").date()
    except ValueError:
        return {
            "error": "invalid_date",
            "message": "local_date must be YYYY-MM-DD",
        }

    athlete_id = get_primary_athlete_id(session, internal_user_id)
    if not athlete_id:
        return {"error": "no_athlete", "message": "No linked athlete for this account."}

    lookback = getattr(config, "SMARTCOACH_DATE_LOOKBACK_DAYS", None) or None
    if lookback is not None and lookback <= 0:
        lookback = None

    ids = ActivityDAO.find_run_activity_ids_on_local_date(
        session, athlete_id, d, max_lookback_days=lookback
    )

    if len(ids) == 0:
        return {
            "disambiguation_needed": False,
            "no_runs": True,
            "local_date": local_date,
            "message": "No runs on that date.",
        }

    if len(ids) == 1:
        return {
            "disambiguation_needed": False,
            "activity_id": ids[0],
            "local_date": local_date,
        }

    candidates = []
    for aid in ids[:12]:
        act = ActivityDAO.get_by_id(session, aid)
        if not act or str(act.user_id) != str(internal_user_id):
            continue
        dm = distance_miles_from_meters(act.distance)
        candidates.append(
            {
                "activity_id": int(aid),
                "title": (act.name or "Run")[:120],
                "distance_display": format_distance_mi(dm),
                "start_local_time_display": format_time_utc(act.start_date),
            }
        )

    return {
        "disambiguation_needed": True,
        "local_date": local_date,
        "candidates": candidates,
        "message": "Ask the user which run they mean.",
    }


# ---------------------------------------------------------------------------
# Tool: search_runs
# ---------------------------------------------------------------------------


def tool_search_runs(
    session: Session,
    internal_user_id: str,
    *,
    min_distance_m: Optional[float] = None,
    max_distance_m: Optional[float] = None,
    name_query: Optional[str] = None,
    start_date_from: Optional[date] = None,
    start_date_to: Optional[date] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    athlete_id = get_primary_athlete_id(session, internal_user_id)
    if not athlete_id:
        return {"error": "no_athlete", "message": "No linked athlete for this account."}

    rows = ActivityDAO.search_runs(
        session,
        athlete_id,
        min_distance_m=min_distance_m,
        max_distance_m=max_distance_m,
        name_query=name_query,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        limit=limit,
    )

    matches = [
        {
            "activity_id": r["activity_id"],
            "title": (r.get("name") or "Run")[:120],
            "distance_display": format_distance_mi(
                distance_miles_from_meters(r.get("distance"))
            ),
            "start_local_time_display": format_time_utc(r.get("start_date")),
            "start_local_date": (
                r.get("start_date").date().isoformat()
                if getattr(r.get("start_date"), "date", None)
                else None
            ),
        }
        for r in rows
    ]

    return {
        "matches": matches,
        "count": len(matches),
        "filters": {
            "min_distance_m": min_distance_m,
            "max_distance_m": max_distance_m,
            "name_query": name_query,
            "start_date_from": start_date_from.isoformat() if start_date_from else None,
            "start_date_to": start_date_to.isoformat() if start_date_to else None,
            "limit": max(1, min(int(limit), 20)),
        },
        "message": (
            "No matching runs found."
            if len(matches) == 0
            else "Use the first match as the most recent run that fits the filters."
        ),
    }


def tool_aggregate_runs_in_range(
    session: Session,
    internal_user_id: str,
    *,
    start_date_from: date,
    start_date_to: date,
    min_distance_m: Optional[float] = None,
    max_distance_m: Optional[float] = None,
    name_query: Optional[str] = None,
) -> Dict[str, Any]:
    """Full count and total distance for Run activities in an inclusive date window."""
    athlete_id = get_primary_athlete_id(session, internal_user_id)
    if not athlete_id:
        return {"error": "no_athlete", "message": "No linked athlete for this account."}

    agg = ActivityDAO.aggregate_runs(
        session,
        athlete_id,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        min_distance_m=min_distance_m,
        max_distance_m=max_distance_m,
        name_query=name_query,
    )
    if agg.get("error"):
        return agg

    total_m = float(agg["total_distance_m"])
    miles = distance_miles_from_meters(total_m)
    weekly_rows = agg.get("weekly_summaries") or []
    weekly_summaries: List[Dict[str, Any]] = []
    for row in weekly_rows:
        week_monday_iso = row.get("week_monday")
        week_label = None
        if isinstance(week_monday_iso, str):
            try:
                d = datetime.strptime(week_monday_iso[:10], "%Y-%m-%d").date()
                week_label = f"Week of {d.month}/{d.day}"
            except ValueError:
                week_label = None
        w_total_m = float(row.get("total_distance_m") or 0.0)
        w_miles = distance_miles_from_meters(w_total_m)
        weekly_summaries.append(
            {
                "iso_week": row.get("iso_week"),
                "week_monday": week_monday_iso,
                "week_label": week_label,
                "run_count": int(row.get("run_count") or 0),
                "total_distance_meters": w_total_m,
                "total_distance_miles": round(w_miles, 4),
                "total_mi_display": format_distance_mi(w_miles),
            }
        )
    filters = {
        "start_date_from": start_date_from.isoformat(),
        "start_date_to": start_date_to.isoformat(),
        "min_distance_m": min_distance_m,
        "max_distance_m": max_distance_m,
        "name_query": name_query,
    }
    out = {
        "run_count": int(agg["run_count"]),
        "total_distance_meters": total_m,
        "total_distance_miles": round(miles, 4),
        "total_mi_display": format_distance_mi(miles),
        "weekly_summaries": weekly_summaries,
        "filters": filters,
        "scope": (
            "All Strava runs in range (type Run). Dates are each activity's local calendar day "
            "(same rule as find_runs_by_date / activities API), not raw UTC date. "
            "Same optional filters as search_runs; no row cap."
        ),
        "weekly_summaries_scope": (
            "Weekly rows are grouped by ISO week (Monday-Sunday) from the same filtered "
            "activities set used for overall totals in this payload."
        ),
        "message": (
            "Report totals using **exactly** run_count and total_mi_display from this payload — "
            "do not round differently or estimate. For weekly breakdowns, use weekly_summaries. "
            "Do not infer totals from search_runs."
        ),
    }
    logger.info(
        "aggregate_runs_in_range from=%s to=%s run_count=%s total_mi_display=%s",
        start_date_from.isoformat(),
        start_date_to.isoformat(),
        out["run_count"],
        out["total_mi_display"],
    )
    return out


# ---------------------------------------------------------------------------
# Tool: get_run_summary
# ---------------------------------------------------------------------------


def tool_get_run_summary(
    session: Session,
    internal_user_id: str,
    activity_id: int,
    anchor_local_date: Optional[str] = None,
    *,
    include_peer_comparison: bool = True,
    include_execution_kpis: bool = True,
    include_hr_profile: bool = True,
) -> Dict[str, Any]:
    ck = cache_key(
        internal_user_id,
        activity_id,
        INSIGHT_SCHEMA_VERSION,
        include_peer_comparison=include_peer_comparison,
    )
    hit = get_cached(ck)
    if hit is not None:
        payload = apply_insight_table_labels(hit, anchor_local_date)
    else:
        payload = build_get_run_insight_payload(
            session,
            internal_user_id,
            activity_id,
            INSIGHT_SCHEMA_VERSION,
            include_peer_comparison=include_peer_comparison,
        )
        if "error" not in payload:
            set_cached(ck, payload)
        payload = apply_insight_table_labels(payload, anchor_local_date)

    if payload.get("error"):
        return payload

    if include_execution_kpis:
        kpi_data = get_run_kpi_detail(session, internal_user_id, activity_id)
        if not kpi_data.get("error"):
            payload["training_kpis"] = kpi_data.get("kpis")
            payload["zone_bounds"] = kpi_data.get("zone_bounds")
            payload["is_easy_run"] = kpi_data.get("is_easy_run")

    if include_hr_profile:
        profile = fetch_user_hr_profile_for_coach(session, internal_user_id)
        if profile is not None:
            payload["user_hr_profile"] = profile

    payload["hr_drift_band_zones"] = hr_drift_band_zones_chart()

    return payload


# ---------------------------------------------------------------------------
# Tool: get_training_kpis
# ---------------------------------------------------------------------------


def tool_get_training_kpis(
    session: Session,
    internal_user_id: str,
    weeks: int = _DEFAULT_KPI_WEEKS,
    *,
    start_date_from: Optional[date] = None,
    start_date_to: Optional[date] = None,
) -> Dict[str, Any]:
    weeks = max(1, min(weeks, _MAX_KPI_WEEKS))
    return get_training_progress(
        session,
        internal_user_id,
        weeks,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
    )


# ---------------------------------------------------------------------------
# Tool: get_weekly_training_insight
#
# DEPRECATED V1.6 (PHASE_3_IMPLEMENTATION_CHECKLIST 0.C):
#   This tool will be superseded by the V1.7 plan-aware tool
#   `get_weekly_plan` (AGENTIC_COACH.md Topic 9). The replacement will
#   enforce the V1.6 §6 planned.* / actual.* namespace isolation and the
#   future-week payload contract, neither of which this tool models.
#
#   During V1.6: existing consumers (LLM tool calls routed via
#   `execute_tool` and the system-prompt snippets in `orchestrator.py`)
#   are preserved to avoid breaking live coach conversations.
#
#   V1.6 policy: **NO NEW CONSUMERS.** New read paths for weekly plan or
#   weekly actuals MUST target `get_weekly_plan` (Phase B) and its
#   planned.* / actual.* namespaces. Any PR that adds a new caller of
#   `tool_get_weekly_training_insight` (or references the string
#   "get_weekly_training_insight" as a handler key outside the existing
#   dispatch table) should be flagged in review. The runtime
#   DeprecationWarning emitted below gives CI/logs a grep-friendly
#   signal; see tests/test_get_weekly_training_insight_deprecation.py
#   for the lock-in test.
# ---------------------------------------------------------------------------


_GWTI_DEPRECATION_MESSAGE = (
    "tool_get_weekly_training_insight is deprecated (V1.6 Pre-Phase A 0.C). "
    "Do not add new consumers. New plan-aware reads must use "
    "get_weekly_plan (V1.7, AGENTIC_COACH.md Topic 9) to get strict "
    "planned.* / actual.* namespace isolation and the future-week "
    "payload contract."
)


def _parse_include_kpi_detail_arg(raw: Any) -> Optional[bool]:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(int(raw))
    if isinstance(raw, str):
        t = raw.strip().lower()
        if t in ("1", "true", "yes", "on"):
            return True
        if t in ("0", "false", "no", "off"):
            return False
    return None


def tool_get_weekly_training_insight(
    session: Session,
    internal_user_id: str,
    *,
    include_kpi_detail: Optional[bool] = None,
) -> Dict[str, Any]:
    """Return the latest precomputed weekly insight row for the user.

    .. deprecated:: V1.6 (Pre-Phase A 0.C)
        Will be replaced by :func:`tool_get_weekly_plan` (V1.7, Topic 9).
        The replacement enforces the V1.6 §6 ``planned.*`` / ``actual.*``
        namespace isolation and the future-week payload contract, neither
        of which this tool models. **Do not add new callers.** Existing
        callers are preserved during V1.6 to avoid breaking live coach
        conversations; rewrites happen in Phase C–F.

    Default payload is orientation-only when
    ``SMARTCOACH_WEEKLY_INSIGHT_TOOL_SLIM`` is on (see
    :mod:`src.smartcoach_mobile_coach.weekly_insights_service`).
    """
    warnings.warn(
        _GWTI_DEPRECATION_MESSAGE,
        DeprecationWarning,
        stacklevel=2,
    )
    if include_kpi_detail is None:
        want_full = not weekly_insight_tool_slim_default_from_env()
    else:
        want_full = bool(include_kpi_detail)
    return get_latest_weekly_insight(session, internal_user_id, slim=not want_full)


# ---------------------------------------------------------------------------
# Tool: get_weekly_plan (V1.6 Phase B 3B.2–3B.4)
#
# V1.6 §6 canonical weekly-plan read. Supersedes
# ``get_weekly_training_insight`` as the way the coach learns what a
# specific week looks like:
#
# * **3B.2** — Takes an optional ``week_start_iso`` (Monday) and returns
#   the plan for any past / current / future Monday-to-Sunday window.
#   When the arg is omitted, returns the athlete's current week.
# * **3B.3** — Enforces the future-week payload contract
#   **structurally**: when the target week is in the future, no
#   activity join runs, every day's ``execution`` block is ``None``,
#   every day's ``plan_status`` is ``"planned_only"``, and the weekly
#   ``adherence`` block is ``None``. The LLM has no way to read an
#   ``actual.*`` field that doesn't exist.
# * **3B.4** — For PAST / CURRENT weeks, the payload includes the
#   canonical weekly ``adherence_runs_pct`` block and the week-level
#   ``phase_kpi_priority`` block so the coach can emphasize the right
#   KPIs per §19.4 and calibrate tone by adherence band per §19.8
#   without re-deriving either signal.
#
# Implementation: thin wrapper over
# :func:`src.services.plan.weekly_plan.build_weekly_plan_payload`.
# That same service backs ``GET /api/plan/current-week`` so the LLM
# and the mobile app see byte-exact the same shape (§X.5
# single-source-of-truth).
# ---------------------------------------------------------------------------


def _parse_week_start_iso(raw: Any) -> Optional[date]:
    """
    Parse the ``week_start_iso`` tool argument.

    Returns ``None`` when omitted (caller treats this as "current week").
    Returns ``None`` for malformed values so the tool degrades to
    current-week rather than raising — the LLM-facing contract is "we
    answer with what we can prove", not "we crash on a typo".
    """
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        # Accept "YYYY-MM-DD" and "YYYY-MM-DDTHH:MM:SS" variants.
        try:
            return datetime.fromisoformat(s.split("T")[0]).date()
        except ValueError:
            return None
    return None


def tool_get_weekly_plan(
    session: Session,
    internal_user_id: str,
    *,
    week_start_iso: Optional[str] = None,
    tz: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return the V1.6 §6 weekly-plan payload for any past / current /
    future Monday-to-Sunday window.

    Args:
        session: Active SQLAlchemy session.
        internal_user_id: Internal user UUID string (not Auth0 subject).
        week_start_iso: ISO date (``YYYY-MM-DD``) within the target
            week; normalized to that week's Monday. ``None`` resolves
            to the athlete's current week in ``tz``.
        tz: Optional IANA timezone name. Defaults to UTC. Primarily
            affects "what week is current" — past/future weeks are
            absolute.

    Returns:
        Either a tool-friendly error envelope
        (``{"error": "no_plan", ...}``) or the payload produced by
        :func:`src.services.plan.weekly_plan.build_weekly_plan_payload`.

    V1.6 contracts enforced by delegation to the service:
        * §6 namespace isolation (``planned.*`` / ``actual.*`` per day).
        * §19.5 future-week contract (no actuals, no adherence).
        * §7 adherence band + §8 phase emphasis for past/current weeks.
    """
    import uuid

    try:
        user_uuid = uuid.UUID(str(internal_user_id))
    except (TypeError, ValueError):
        return {
            "error": "invalid_user_id",
            "message": "internal_user_id must be a UUID string.",
        }

    target_monday = _parse_week_start_iso(week_start_iso)
    tz_value = tz if (isinstance(tz, str) and tz.strip()) else "UTC"

    from src.services.plan.weekly_plan import build_weekly_plan_payload

    return build_weekly_plan_payload(
        session,
        user_uuid,
        tz=tz_value,
        target_week_start=target_monday,
    )


# ---------------------------------------------------------------------------
# Tool: get_plan_overview (V1.6 Phase B 3B.5)
#
# End-to-end, **planned-only** view of the athlete's active (or most
# recently created) training plan. Supersedes any ad-hoc whole-plan
# summaries the coach previously had to synthesize from
# ``get_weekly_training_insight`` + inline math.
#
# Surfaces three coach-facing views:
#
# * ``phase_blocks`` — contiguous runs of same-phase weeks (Base /
#   Build / Peak / Taper) with week span, workout count, planned
#   mileage, and the canonical §8 ``phase_kpi_priority`` emphasis
#   list. Use this to narrate the plan arc ("you're in Build for the
#   next 4 weeks; the top emphasis is Pace Consistency").
# * ``volume_curve`` — one row per plan week (planned_runs +
#   planned_miles_total) for progression and deload narratives.
# * ``long_run_progression`` — one row per plan week with the longest
#   planned run (date, miles, canonical run-type key).
#
# §19.5 future-week contract extension
# ------------------------------------
# ``get_plan_overview`` is purely plan-side — no ``Activity`` table
# read runs. Because the tool structurally cannot load an actual, the
# §19.5 future-week "no actuals" rule applies to **every** week in
# the overview, not just future weeks. If the coach needs actuals
# for a past/current week, it must call ``get_weekly_plan``.
#
# Implementation: thin wrapper over
# :func:`src.services.plan.plan_overview.build_plan_overview_payload`.
# The tool has no parameters other than the implicit ``tz`` — the
# overview is always "the plan, end to end".
# ---------------------------------------------------------------------------


def tool_get_plan_overview(
    session: Session,
    internal_user_id: str,
    *,
    tz: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return the V1.6 Phase B 3B.5 end-to-end plan overview payload.

    Args:
        session: Active SQLAlchemy session.
        internal_user_id: Internal user UUID string (not Auth0 subject).
        tz: Optional IANA timezone name. Defaults to UTC. Only affects
            the ``week_temporality`` stamp on each ``volume_curve``
            row — plan-side fields are absolute.

    Returns:
        Either a tool-friendly error envelope
        (``{"error": "no_plan", ...}`` /
        ``{"error": "invalid_user_id", ...}``) or the payload produced
        by :func:`src.services.plan.plan_overview.build_plan_overview_payload`.

    V1.6 contracts enforced by delegation to the service:
        * §19.5 no-actuals on every week (structural — no activity
          query runs).
        * §8 per-phase emphasis list is the canonical table, not a
          derived restatement.
        * §7 majority-of-days / plurality rule drives per-week phase
          resolution inside the volume curve.
    """
    import uuid

    try:
        user_uuid = uuid.UUID(str(internal_user_id))
    except (TypeError, ValueError):
        return {
            "error": "invalid_user_id",
            "message": "internal_user_id must be a UUID string.",
        }

    tz_value = tz if (isinstance(tz, str) and tz.strip()) else "UTC"

    from src.services.plan.plan_overview import build_plan_overview_payload

    return build_plan_overview_payload(
        session,
        user_uuid,
        tz=tz_value,
    )


# ---------------------------------------------------------------------------
# Tool: get_phase_analysis (V1.6 Phase B 3B.6)
#
# Per-run-type KPI trend for phase-to-date. Given one of the four
# canonical phases (Base / Build / Peak / Taper), surfaces how each
# run type is actually being executed in that phase so far:
#
# * ``phase_kpi_priority`` — the §8 ordered emphasis list the coach
#   should lead with ("in Build, talk about Pace Consistency first").
# * ``phase_weeks`` — total / completed / in_progress / future counts
#   + completion_pct + phase_temporality.
# * ``phase_window`` — first-Monday / last-Sunday / evaluated_through
#   (the later of today or the last evaluable Sunday).
# * ``by_run_type`` — one entry per canonical run-type key with
#   planned vs matched counts, mileage totals, zone-compliance avg +
#   weekly trend series, deviation-direction distribution, and
#   run-score distribution.
#
# §X.5 single-source-of-truth: every actual-side value is sourced
# from ``build_run_execution_block`` — the same producer the LLM's
# ``get_run_summary`` and ``get_weekly_plan`` tools use. This module
# never reads planned / actual fields off ``Activity`` directly.
#
# §19.5 future-week contract extension: future phase-weeks contribute
# **zero** execution data to the trend. Planned counts are still
# aggregated phase-wide so the coach sees the denominator ("you have
# 4 planned Tempo runs this phase; you've completed 2 so far").
#
# Implementation: thin wrapper over
# :func:`src.services.plan.phase_analysis.build_phase_analysis_payload`.
# ---------------------------------------------------------------------------


def tool_get_phase_analysis(
    session: Session,
    internal_user_id: str,
    *,
    phase_id: Optional[str] = None,
    tz: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return the V1.6 Phase B 3B.6 phase-analysis payload.

    Args:
        session: Active SQLAlchemy session.
        internal_user_id: Internal user UUID string (not Auth0 subject).
        phase_id: One of ``"Base"``, ``"Build"``, ``"Peak"``,
            ``"Taper"`` (case-insensitive). Required. Any other value
            returns an ``invalid_phase`` envelope with the allowed
            list.
        tz: Optional IANA timezone name. Defaults to UTC. Used to
            resolve the athlete's "today" for the phase-to-date cutoff
            and the per-week trend window.

    Returns:
        Either a tool-friendly error envelope
        (``{"error": "no_plan" | "invalid_phase" | "invalid_user_id" |
        "missing_phase_id", ...}``) or the payload produced by
        :func:`src.services.plan.phase_analysis.build_phase_analysis_payload`.

    V1.6 contracts enforced by delegation to the service:
        * §X.5 single-source-of-truth for every actual-side field
          (read via ``build_run_execution_block``).
        * §19.5 no execution data on future phase-weeks.
        * §7 per-week phase resolution agrees byte-exact with
          ``get_weekly_plan`` / ``get_plan_overview``.
        * §8 ``phase_kpi_priority`` is the canonical table, not a
          restatement.
    """
    import uuid

    try:
        user_uuid = uuid.UUID(str(internal_user_id))
    except (TypeError, ValueError):
        return {
            "error": "invalid_user_id",
            "message": "internal_user_id must be a UUID string.",
        }

    if phase_id is None or (isinstance(phase_id, str) and not phase_id.strip()):
        return {
            "error": "missing_phase_id",
            "message": "phase_id is required (one of Base, Build, Peak, Taper).",
        }

    tz_value = tz if (isinstance(tz, str) and tz.strip()) else "UTC"

    from src.services.plan.phase_analysis import build_phase_analysis_payload

    return build_phase_analysis_payload(
        session,
        user_uuid,
        phase_id,
        tz=tz_value,
    )


# ---------------------------------------------------------------------------
# Tool: get_user_context (V1.6 Phase B 3B.10)
#
# Light "who is this user" payload the coach reads at the start of a
# conversation (nudged by the orchestrator when ``turn_type ==
# "opening"`` — wired in 3B.13). Supersedes any ad-hoc "reach into a
# few other tools and piece together race goal + phase + coaching
# level" patterns the model was falling into.
#
# Surfaces:
#
# * ``race_goal`` — race name/date/distance, goal_time, primary_goal,
#   weeks_until_race (from the active or most recent plan).
# * ``plan`` — plan_id, plan_name, plan_start/end, total_weeks,
#   current_week_number, is_active, and the **current phase** +
#   canonical §8 ``phase_kpi_priority`` emphasis list so the coach can
#   open with spec-correct emphasis in one read.
# * ``baseline_status`` — canonical §12 three-band enum
#   (``insufficient`` / ``thin`` / ``strong``) via
#   ``compute_baseline_status_for_athlete``.
# * ``coaching`` — ``coaching_level`` / ``verbosity`` + stored
#   per-surface metric priorities from ``user_coach_preferences``
#   (falls back to beginner defaults when no row saved yet).
# * ``preferences`` — ``training_days``, derived ``long_run_day``,
#   ``unit_system``, emitted ``timezone``.
# * ``session_summary`` — explicit ``None`` placeholder for V1.7 (no
#   session-summary table exists yet; shape key is stable so a later
#   release can backfill without breakage).
#
# §X.5 single-source-of-truth: every field is a read through an
# existing canonical producer (``compute_baseline_status_for_athlete``,
# ``resolve_week_phase``, ``phase_kpi_priority_for_phase``). This tool
# never re-derives a deterministic signal.
#
# Payload size budget (3B.11): < 2 KB for a fully populated user.
# Stable keys — documented in the service docstring and locked by
# contract tests.
#
# Implementation: thin wrapper over
# :func:`src.services.user.user_context.build_user_context_payload`.
# ---------------------------------------------------------------------------


def tool_get_user_context(
    session: Session,
    internal_user_id: str,
    *,
    tz: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return the V1.6 Phase B 3B.10 ``user_context`` payload.

    Args:
        session: Active SQLAlchemy session.
        internal_user_id: Internal user UUID string (not Auth0 subject).
        tz: Optional IANA timezone name. Defaults to UTC. Drives
            resolution of "today" and is emitted in
            ``preferences.timezone``.

    Returns:
        Either a tool-friendly error envelope
        (``{"error": "invalid_user_id" | "no_user", ...}``) or the
        payload produced by
        :func:`src.services.user.user_context.build_user_context_payload`.

    V1.6 contracts enforced by delegation to the service:
        * §X.5 single-source-of-truth for every deterministic field.
        * §19 PII posture (first-name only, no email / picture).
        * §8 canonical ``phase_kpi_priority`` for the current phase.
    """
    import uuid

    try:
        user_uuid = uuid.UUID(str(internal_user_id))
    except (TypeError, ValueError):
        return {
            "error": "invalid_user_id",
            "message": "internal_user_id must be a UUID string.",
        }

    tz_value = tz if (isinstance(tz, str) and tz.strip()) else "UTC"

    from src.services.user.user_context import build_user_context_payload

    return build_user_context_payload(
        session,
        user_uuid,
        tz=tz_value,
    )


# ---------------------------------------------------------------------------
# Tool: get_marathon_projection
# ---------------------------------------------------------------------------


def tool_get_marathon_projection(
    session: Session,
    internal_user_id: str,
    *,
    target_race_date: Optional[date] = None,
    goal_time_hhmmss: Optional[str] = None,
    lookback_days: int = 84,
) -> Dict[str, Any]:
    return get_marathon_projection(
        session,
        internal_user_id,
        target_race_date=target_race_date,
        goal_time_hhmmss=goal_time_hhmmss,
        lookback_days=lookback_days,
    )


# ---------------------------------------------------------------------------
# Tool: save_coach_preference
# ---------------------------------------------------------------------------

_VALID_LEVELS = set(COACHING_LEVEL_DEFAULTS.keys())
_VALID_VERBOSITY = {"minimal", "normal", "detailed"}


def _validate_metric_list(raw: Any) -> Optional[List[str]]:
    """Return a cleaned list of allowed metrics, or None if input is invalid."""
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    return [m for m in raw if isinstance(m, str) and m in ALLOWED_METRICS] or None


def tool_save_coach_preference(
    session: Session, internal_user_id: str, args: Dict[str, Any]
) -> Dict[str, Any]:
    level = args.get("coaching_level")
    run_priority = args.get("run_summary_priority")
    training_priority = args.get("training_summary_priority")
    verbosity = args.get("verbosity")

    if level and level not in _VALID_LEVELS:
        return {
            "error": "invalid_level",
            "message": f"coaching_level must be one of {sorted(_VALID_LEVELS)}",
        }
    if verbosity and verbosity not in _VALID_VERBOSITY:
        return {
            "error": "invalid_verbosity",
            "message": f"verbosity must be one of {sorted(_VALID_VERBOSITY)}",
        }

    run_priority = _validate_metric_list(run_priority)
    training_priority = _validate_metric_list(training_priority)

    set_clauses = ["updated_at = now()"]
    params: Dict[str, Any] = {"uid": internal_user_id}

    if level:
        set_clauses.append("coaching_level = :level")
        params["level"] = level
    if run_priority is not None:
        set_clauses.append("run_summary_priority = :rsp")
        params["rsp"] = json.dumps(run_priority)
    if training_priority is not None:
        set_clauses.append("training_summary_priority = :tsp")
        params["tsp"] = json.dumps(training_priority)
    if verbosity:
        set_clauses.append("verbosity = :verbosity")
        params["verbosity"] = verbosity

    session.execute(
        text(
            f"INSERT INTO user_coach_preferences (user_id) "
            f"VALUES (CAST(:uid AS uuid)) "
            f"ON CONFLICT (user_id) DO UPDATE SET {', '.join(set_clauses)}"
        ),
        params,
    )
    session.commit()

    row = session.execute(
        text(
            "SELECT coaching_level, run_summary_priority, training_summary_priority, verbosity "
            "FROM user_coach_preferences WHERE user_id = CAST(:uid AS uuid)"
        ),
        {"uid": internal_user_id},
    ).fetchone()

    current = {
        "coaching_level": row.coaching_level if row else "beginner",
        "run_summary_priority": row.run_summary_priority if row else None,
        "training_summary_priority": row.training_summary_priority if row else None,
        "verbosity": row.verbosity if row else "normal",
    }

    return {
        "saved": True,
        "preferences": current,
        "message": "Preferences saved for your account only. I'll use these going forward.",
    }


def tool_update_plan_intake(
    session: Session,
    internal_user_id: str,
    args: Dict[str, Any],
    *,
    current_state: Optional[Dict[str, Any]] = None,
    source_user_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deterministically merge plan intake fields and report missing required items.
    """
    updates = args.get("updates")
    if updates is None:
        updates = {}
    clear_fields = args.get("clear_fields")
    if not isinstance(clear_fields, list):
        clear_fields = []
    reset = _coerce_tool_bool(args.get("reset"), False)

    msg = source_user_message
    if not (isinstance(msg, str) and msg.strip()):
        raw_ctx = args.get("source_user_message")
        if isinstance(raw_ctx, str) and raw_ctx.strip():
            msg = raw_ctx.strip()

    state = update_plan_intake_state(
        current_state,
        updates=updates if isinstance(updates, dict) else {},
        clear_fields=[str(f) for f in clear_fields if isinstance(f, str)],
        reset=reset,
        source_user_message=msg if isinstance(msg, str) else None,
    )
    return {
        "plan_intake_state": state,
        "status": state.get("status"),
        "ready_to_generate": bool(state.get("ready_to_generate")),
        "missing_required": state.get("missing_required", []),
        "missing_required_labels": state.get("missing_required_labels", []),
        "errors": state.get("errors", []),
        "confirmation_summary": state.get("confirmation_summary"),
        "message": (
            "Plan intake updated. Ask one missing field next."
            if not state.get("ready_to_generate")
            else "All required fields are present. Ask for confirmation before generating."
        ),
    }


def _safe_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def _safe_int(value: Any) -> Optional[int]:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return None
    return out


def _ordinal_day(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _format_friendly_week_one_start(date_str: str) -> str:
    """e.g. Mon., April 20th (from YYYY-MM-DD)."""
    raw = str(date_str or "").strip()[:10]
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return raw
    weekdays = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    months = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    wd = weekdays[dt.weekday()]
    mon = months[dt.month - 1]
    return f"{wd}., {mon} {_ordinal_day(dt.day)}"


def _format_weekday_only(date_str: str) -> str:
    """Mon, Tue, … from YYYY-MM-DD (no month/day)."""
    raw = str(date_str or "").strip()[:10]
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return raw[:3] if len(raw) >= 3 else raw
    return ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[dt.weekday()]


def _phase_block_week_count(block: Dict[str, Any]) -> Optional[int]:
    sw = _safe_int(block.get("start_week"))
    ew = _safe_int(block.get("end_week"))
    if sw is not None and ew is not None:
        return max(1, ew - sw + 1)
    if sw is not None or ew is not None:
        return 1
    return None


def _extract_plan_weeks(validation_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    validated_plan = validation_result.get("validated_plan")
    if isinstance(validated_plan, dict) and isinstance(
        validated_plan.get("weeks"), list
    ):
        return [w for w in validated_plan.get("weeks", []) if isinstance(w, dict)]
    draft = validation_result.get("draft")
    if isinstance(draft, dict) and isinstance(draft.get("weeks"), list):
        return [w for w in draft.get("weeks", []) if isinstance(w, dict)]
    return []


def _plan_overview_from_validation(
    validation_result: Dict[str, Any],
    plan_request: Dict[str, Any],
    saved_plan: Dict[str, Any],
) -> Dict[str, Any]:
    weeks = _extract_plan_weeks(validation_result)
    phase_sequence: List[str] = []
    phase_blocks: List[Dict[str, Any]] = []
    phase_idx: Dict[str, int] = {}
    peak_weekly_miles: Optional[float] = None
    peak_long_run_miles: Optional[float] = None
    for w in weeks:
        phase = str(w.get("phase") or "").strip()
        if phase and phase not in phase_sequence:
            phase_sequence.append(phase)
        week_num = _safe_int(w.get("week_number"))
        weekly = _safe_float(w.get("weekly_mileage"))
        if weekly is not None:
            peak_weekly_miles = (
                weekly if peak_weekly_miles is None else max(peak_weekly_miles, weekly)
            )
        if phase:
            if phase not in phase_idx:
                phase_idx[phase] = len(phase_blocks)
                phase_blocks.append(
                    {
                        "phase": phase,
                        "start_week": week_num,
                        "end_week": week_num,
                        "peak_weekly_miles": weekly,
                    }
                )
            else:
                block = phase_blocks[phase_idx[phase]]
                if week_num is not None:
                    start_week = _safe_int(block.get("start_week"))
                    end_week = _safe_int(block.get("end_week"))
                    if start_week is None or week_num < start_week:
                        block["start_week"] = week_num
                    if end_week is None or week_num > end_week:
                        block["end_week"] = week_num
                if weekly is not None:
                    prev_peak = _safe_float(block.get("peak_weekly_miles"))
                    block["peak_weekly_miles"] = (
                        weekly if prev_peak is None else max(prev_peak, weekly)
                    )
        long_run = _safe_float(w.get("long_run_miles"))
        if long_run is not None:
            peak_long_run_miles = (
                long_run
                if peak_long_run_miles is None
                else max(peak_long_run_miles, long_run)
            )

    start_date: Optional[str] = None
    validated_plan = validation_result.get("validated_plan")
    if isinstance(validated_plan, dict):
        raw = validated_plan.get("start_date")
        if isinstance(raw, str) and raw.strip():
            start_date = raw.strip()[:10]
    if not start_date:
        draft = validation_result.get("draft")
        if isinstance(draft, dict):
            raw = draft.get("start_date")
            if isinstance(raw, str) and raw.strip():
                start_date = raw.strip()[:10]
    if not start_date:
        workouts = saved_plan.get("workouts")
        if isinstance(workouts, list):
            dates = sorted(
                {
                    str(w.get("date"))[:10]
                    for w in workouts
                    if isinstance(w, dict) and str(w.get("date") or "").strip()
                }
            )
            if dates:
                start_date = dates[0]

    return {
        "plan_start_date": start_date,
        "race_date": saved_plan.get("race_date"),
        "race_distance": saved_plan.get("race_distance"),
        "total_weeks": len(weeks) if weeks else None,
        "phase_sequence": phase_sequence,
        "phase_blocks": [
            {
                "phase": str(block.get("phase") or "").strip(),
                "start_week": _safe_int(block.get("start_week")),
                "end_week": _safe_int(block.get("end_week")),
                "peak_weekly_miles": (
                    round(float(block["peak_weekly_miles"]), 1)
                    if _safe_float(block.get("peak_weekly_miles")) is not None
                    else None
                ),
            }
            for block in phase_blocks
            if str(block.get("phase") or "").strip()
        ],
        "peak_weekly_miles": (
            round(float(peak_weekly_miles), 1)
            if peak_weekly_miles is not None
            else None
        ),
        "peak_long_run_miles": (
            round(float(peak_long_run_miles), 1)
            if peak_long_run_miles is not None
            else None
        ),
        "training_days": plan_request.get("training_days") or [],
        "long_run_day": plan_request.get("long_run_day"),
    }


def _plan_baseline_from_validation(
    validation_result: Dict[str, Any], *, activity_weeks: int
) -> Dict[str, Any]:
    rationale = validation_result.get("pass1_rationale")
    if not isinstance(rationale, dict):
        rationale = {}
    base_mpw = _safe_float(rationale.get("base_mpw"))
    longest_recent = _safe_float(rationale.get("longest_recent"))
    start_lr = _safe_float(rationale.get("start_lr"))
    recommended_weeks_raw = rationale.get("recommended_weeks")
    try:
        recommended_weeks = int(recommended_weeks_raw)
    except (TypeError, ValueError):
        recommended_weeks = None
    return {
        "source": "materialized_view",
        "lookback_weeks_requested": int(activity_weeks),
        "avg_weekly_miles": round(base_mpw, 1) if base_mpw is not None else None,
        "longest_recent_run_miles": (
            round(longest_recent, 1) if longest_recent is not None else None
        ),
        "starting_long_run_miles": round(start_lr, 1) if start_lr is not None else None,
        "recommended_weeks": recommended_weeks,
    }


def _build_plan_generation_brief(
    race_distance: str,
    race_date: str,
    payload: Dict[str, Any],
) -> str:
    overview = payload.get("overview") if isinstance(payload, dict) else {}
    baseline = payload.get("baseline") if isinstance(payload, dict) else {}
    this_week = payload.get("this_week") if isinstance(payload, dict) else {}

    race_label = (race_distance or "race").strip() or "race"
    race_day = (race_date or "").strip() or "TBD"
    start_raw = (
        overview.get("plan_start_date") if isinstance(overview, dict) else None
    ) or "TBD"
    start_friendly = (
        _format_friendly_week_one_start(str(start_raw))
        if start_raw != "TBD" and len(str(start_raw).strip()) >= 10
        else str(start_raw)
    )
    lines: List[str] = [
        f"Your {race_label} plan is saved for {race_day}.",
        "",
        f"**Week 1 starts:** {start_friendly}",
    ]

    if isinstance(baseline, dict):
        avg_mpw = baseline.get("avg_weekly_miles")
        long_run = baseline.get("longest_recent_run_miles")
        lookback = baseline.get("lookback_weeks_requested")
        has_metrics = avg_mpw is not None or long_run is not None
        lines.append("")
        if has_metrics:
            if isinstance(lookback, int) and lookback > 0:
                lines.append(
                    f"To create the plan, I used your running data from the last **{lookback}** weeks."
                )
            else:
                lines.append(
                    "To create the plan, I used your recent running data from synced activities."
                )
            lines.append("")
            if avg_mpw is not None:
                lines.append(f"- **Weekly miles:** {avg_mpw:.1f} mi/week")
            else:
                lines.append("- **Weekly miles:** —")
            if long_run is not None:
                lines.append(f"- **Longest run:** {long_run:.1f} mi")
            else:
                lines.append("- **Longest run:** —")
        else:
            lines.append(
                "There wasn’t enough recent running history to personalize this plan from your "
                "mileage yet, so the schedule follows a solid built-in progression. "
                "Keep syncing runs so future plans can reflect your fitness."
            )

    if isinstance(overview, dict):
        total_weeks = overview.get("total_weeks")
        peak_lr = overview.get("peak_long_run_miles")
        phase_blocks = overview.get("phase_blocks")
        lines.append("")
        if isinstance(total_weeks, int) and total_weeks > 0:
            lines.append(f"**Plan overview** ({total_weeks} weeks)")
        else:
            lines.append("**Plan overview**")
        if isinstance(phase_blocks, list) and phase_blocks:
            lines.append("")
            lines.append("| Phase | Weeks |")
            lines.append("| --- | --- |")
            for block in phase_blocks:
                if not isinstance(block, dict):
                    continue
                phase_name = str(block.get("phase") or "").strip() or "Phase"
                week_count = _phase_block_week_count(block)
                week_label = str(week_count) if week_count is not None else "—"
                lines.append(f"| {phase_name} | {week_label} |")
        else:
            phase_sequence = overview.get("phase_sequence")
            if isinstance(phase_sequence, list):
                named = [str(p).strip() for p in phase_sequence if str(p).strip()]
                if named:
                    lines.extend(["", f"Phases: {' → '.join(named)}"])
        if peak_lr is not None:
            lines.append(
                f"- **Peak long run (plan):** {float(peak_lr):.1f} mi",
            )

    if isinstance(this_week, dict):
        workouts = this_week.get("workouts")
        if isinstance(workouts, list) and workouts:
            lines.extend(
                [
                    "",
                    "**Week 1 Preview**",
                    "",
                    "| Day | Run Type | Miles |",
                    "| --- | --- | --- |",
                ]
            )
            for w in workouts[:6]:
                if not isinstance(w, dict):
                    continue
                d = _format_weekday_only(str(w.get("date") or ""))
                wt_raw = str(w.get("workout_type") or "run").replace("_", " ").strip()
                wt = wt_raw.title() if wt_raw else "Run"
                miles = _safe_float(w.get("miles"))
                miles_text = f"{miles:.1f}" if miles is not None else "—"
                lines.append(f"| {d} | {wt} | {miles_text} |")
        else:
            lines.append(
                "Week-by-week workouts are ready in Plan. Open that tab for the full schedule."
            )

    lines.extend(
        [
            "",
            "**View your Plan:** click on Plan ![Plan tab](smartcoach-tab-icon://plan) to see full details "
            "and upcoming phases.",
            "",
            "**Questions** - Any questions?",
        ]
    )
    return "\n".join(lines)


def tool_generate_training_plan(
    session: Session,
    internal_user_id: str,
    args: Dict[str, Any],
    *,
    current_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Deterministically generate and save plan once intake is complete and confirmed.
    """
    if not isinstance(current_state, dict) or not current_state.get("draft"):
        return {
            "error": "no_plan_intake_state",
            "message": "No plan intake state found. Collect plan details first.",
        }

    confirm = _coerce_tool_bool(args.get("confirm"), False)
    if not confirm:
        return {
            "error": "confirmation_required",
            "message": (
                "Ask for explicit confirmation before generating. "
                "Call again with confirm=true once the user says yes."
            ),
            "plan_intake_state": current_state,
            "confirmation_summary": current_state.get("confirmation_summary"),
        }

    activity_weeks_raw = args.get("activity_weeks", 12)
    try:
        activity_weeks = int(activity_weeks_raw)
    except (TypeError, ValueError):
        activity_weeks = 12
    activity_weeks = max(4, min(activity_weeks, 24))

    try:
        plan_request = build_plan_request_from_state(current_state)
    except Exception as e:
        return {
            "error": "invalid_plan_intake_state",
            "message": str(e),
            "plan_intake_state": current_state,
        }

    try:
        result = run_v2_plan_generation(
            session=session,
            user_id=str(internal_user_id),
            plan_request=plan_request,
            activity_weeks=activity_weeks,
            mode="rolling",
        )
    except Exception as e:
        logger.exception("Plan generation failed user=%s", internal_user_id)
        return {
            "error": "plan_generation_failed",
            "message": str(e),
            "plan_intake_state": current_state,
        }

    if not result.get("valid") or not result.get("validated_plan"):
        return {
            "error": "plan_validation_failed",
            "message": "Generated plan failed validation.",
            "violations": result.get("violations", []),
            "plan_intake_state": current_state,
        }

    validation_payload = {
        "valid": True,
        "validated_plan": result["validated_plan"],
        "violations": result.get("violations", []),
    }
    plan_id = PlanStorageService.save_validated_plan(
        session=session,
        user_id=str(internal_user_id),
        validated_plan=validation_payload,
        plan_request=plan_request,
    )
    session.commit()

    from src.db.dao.plans_dao import get_plan_with_workouts

    saved = get_plan_with_workouts(session, int(plan_id), str(internal_user_id)) or {}
    week_summary = summarize_this_week_from_plan_rows(saved.get("workouts") or [])
    plan_overview = _plan_overview_from_validation(result, plan_request, saved)
    plan_baseline = _plan_baseline_from_validation(
        result, activity_weeks=activity_weeks
    )
    plan_generation_payload = {
        "plan_id": int(plan_id),
        "plan_name": saved.get("plan_name"),
        "this_week": week_summary,
        "overview": plan_overview,
        "baseline": plan_baseline,
        "navigation": {
            "primary_tab": "Plan",
            "hint": "Open the Plan tab to review full workouts and phase-by-phase progression.",
        },
    }
    post_generation_brief = _build_plan_generation_brief(
        race_distance=str(saved.get("race_distance") or ""),
        race_date=str(saved.get("race_date") or ""),
        payload=plan_generation_payload,
    )
    next_state = dict(current_state)
    next_state["status"] = "generated"
    next_state["last_generated_plan_id"] = int(plan_id)
    return {
        "ok": True,
        "plan_id": int(plan_id),
        "plan_name": saved.get("plan_name"),
        "race_date": saved.get("race_date"),
        "race_distance": saved.get("race_distance"),
        "this_week": week_summary,
        "post_generation_brief": post_generation_brief,
        "plan_intake_state": next_state,
        "plan_generation": plan_generation_payload,
        "message": "Plan created and activated successfully.",
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_TOOL_HANDLERS = {
    "find_runs_by_date": "find_runs_by_date",
    "search_runs": "search_runs",
    "aggregate_runs_in_range": "aggregate_runs_in_range",
    "get_run_summary": "get_run_summary",
    "get_run_splits": "get_run_splits",
    "get_training_kpis": "get_training_kpis",
    # DEPRECATED V1.6 (PHASE_3_IMPLEMENTATION_CHECKLIST 0.C): do not add
    # new references to this handler key. Replacement: get_weekly_plan
    # (V1.6 Phase B 3B.2, AGENTIC_COACH.md Topic 9).
    "get_weekly_training_insight": "get_weekly_training_insight",
    # V1.6 Phase B 3B.2–3B.4 — canonical weekly-plan read with the
    # §6 planned.* / actual.* namespace isolation and the §19.5
    # future-week payload contract enforced structurally.
    "get_weekly_plan": "get_weekly_plan",
    # V1.6 Phase B 3B.5 — end-to-end, planned-only overview of the
    # active plan (phase blocks + volume curve + long-run progression).
    # No activity query ever runs, so §19.5 future-week "no actuals"
    # is structurally extended to every week in the overview.
    "get_plan_overview": "get_plan_overview",
    # V1.6 Phase B 3B.6 — per-run-type KPI trend for phase-to-date
    # (Base / Build / Peak / Taper). Surfaces canonical actual.*
    # fields (zone compliance, completion_pct, deviation direction,
    # run score) per run_type_key from phase-to-date matched activities.
    "get_phase_analysis": "get_phase_analysis",
    # V1.6 Phase B 3B.10 — light "who is this user" payload:
    # race goal + current phase + baseline_status + coaching_level
    # + preferences. Coach reads at the start of a conversation
    # (orchestrator nudge wired in 3B.13).
    "get_user_context": "get_user_context",
    "get_marathon_projection": "get_marathon_projection",
    "save_coach_preference": "save_coach_preference",
    "update_plan_intake": "update_plan_intake",
    "generate_training_plan": "generate_training_plan",
    # Legacy names → map to current handlers
    "list_runs_for_local_date": "find_runs_by_date",
    "get_run_insight": "get_run_summary",
}


def execute_tool(
    session: Session,
    internal_user_id: str,
    name: str,
    arguments_json: str,
    *,
    anchor_local_date: Optional[str] = None,
    plan_intake_state: Optional[Dict[str, Any]] = None,
    source_user_message: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return {
            "error": "invalid_arguments",
            "message": "Tool arguments were not valid JSON.",
        }

    handler_key = _TOOL_HANDLERS.get(name)
    if not handler_key:
        return {"error": "unknown_tool", "message": f"Unknown tool: {name}"}

    _increment_tool_call_count(session, name)

    try:
        if handler_key == "find_runs_by_date":
            ld = args.get("local_date")
            if not ld or not isinstance(ld, str):
                return {
                    "error": "missing_local_date",
                    "message": "Parameter local_date (YYYY-MM-DD) is required.",
                }
            return tool_find_runs_by_date(session, internal_user_id, ld.strip())

        if handler_key == "search_runs":
            min_distance_m = _parse_optional_float(args.get("min_distance_m"))
            max_distance_m = _parse_optional_float(args.get("max_distance_m"))
            name_query = args.get("name_query")
            if name_query is not None and not isinstance(name_query, str):
                name_query = None
            start_date_from = _parse_optional_date(args.get("start_date_from"))
            start_date_to = _parse_optional_date(args.get("start_date_to"))
            limit_raw = args.get("limit", 5)
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                limit = 5
            return tool_search_runs(
                session,
                internal_user_id,
                min_distance_m=min_distance_m,
                max_distance_m=max_distance_m,
                name_query=(name_query or "").strip() or None,
                start_date_from=start_date_from,
                start_date_to=start_date_to,
                limit=limit,
            )

        if handler_key == "aggregate_runs_in_range":
            d_from = _parse_optional_date(args.get("start_date_from"))
            d_to = _parse_optional_date(args.get("start_date_to"))
            if d_from is None or d_to is None:
                return {
                    "error": "missing_dates",
                    "message": (
                        "start_date_from and start_date_to (YYYY-MM-DD, inclusive) are required."
                    ),
                }
            min_distance_m = _parse_optional_float(args.get("min_distance_m"))
            max_distance_m = _parse_optional_float(args.get("max_distance_m"))
            nq = args.get("name_query")
            if nq is not None and not isinstance(nq, str):
                nq = None
            return tool_aggregate_runs_in_range(
                session,
                internal_user_id,
                start_date_from=d_from,
                start_date_to=d_to,
                min_distance_m=min_distance_m,
                max_distance_m=max_distance_m,
                name_query=(nq or "").strip() or None,
            )

        if handler_key == "get_run_summary":
            aid = _parse_activity_id(args)
            if aid is None:
                return {
                    "error": "missing_activity_id",
                    "message": "activity_id must be a positive integer.",
                }
            inc_peers, inc_kpis, inc_hr = _parse_get_run_summary_include_flags(args)
            return tool_get_run_summary(
                session,
                internal_user_id,
                aid,
                anchor_local_date=anchor_local_date,
                include_peer_comparison=inc_peers,
                include_execution_kpis=inc_kpis,
                include_hr_profile=inc_hr,
            )

        if handler_key == "get_run_splits":
            aid = _parse_activity_id(args)
            if aid is None:
                return {
                    "error": "missing_activity_id",
                    "message": "activity_id must be a positive integer.",
                }
            return tool_get_run_splits(session, internal_user_id, aid)

        if handler_key == "get_training_kpis":
            weeks = args.get("weeks", _DEFAULT_KPI_WEEKS)
            try:
                weeks = int(weeks)
            except (TypeError, ValueError):
                weeks = _DEFAULT_KPI_WEEKS
            d_from = _parse_optional_date(args.get("start_date_from"))
            d_to = _parse_optional_date(args.get("start_date_to"))
            if (d_from is None) ^ (d_to is None):
                return {
                    "error": "missing_dates",
                    "message": (
                        "Provide both start_date_from and start_date_to (YYYY-MM-DD), "
                        "or omit both for rolling weeks mode."
                    ),
                }
            return tool_get_training_kpis(
                session,
                internal_user_id,
                weeks,
                start_date_from=d_from,
                start_date_to=d_to,
            )

        if handler_key == "get_weekly_training_insight":
            detail_raw = _parse_include_kpi_detail_arg(args.get("include_kpi_detail"))
            return tool_get_weekly_training_insight(
                session, internal_user_id, include_kpi_detail=detail_raw
            )

        if handler_key == "get_weekly_plan":
            # V1.6 Phase B 3B.2 — ``week_start_iso`` is optional; when
            # omitted the tool returns the athlete's current week.
            # Malformed values degrade to current-week inside the
            # parser (not an error) so the LLM never gets stuck on a
            # typoed date — it still gets a useful payload back.
            week_start_raw = args.get("week_start_iso")
            tz_raw = args.get("tz")
            tz_val = tz_raw if isinstance(tz_raw, str) else None
            return tool_get_weekly_plan(
                session,
                internal_user_id,
                week_start_iso=week_start_raw,
                tz=tz_val,
            )

        if handler_key == "get_plan_overview":
            # V1.6 Phase B 3B.5 — no required arguments. ``tz`` is
            # optional and only affects the per-week
            # ``week_temporality`` stamp on the volume curve; every
            # other field in the payload is absolute.
            tz_raw = args.get("tz")
            tz_val = tz_raw if isinstance(tz_raw, str) else None
            return tool_get_plan_overview(
                session,
                internal_user_id,
                tz=tz_val,
            )

        if handler_key == "get_phase_analysis":
            # V1.6 Phase B 3B.6 — ``phase_id`` is required. Accepts
            # any case of the four canonical names ("Base", "build",
            # "PEAK", "Taper"); the service normalizes. Missing /
            # non-string values return a ``missing_phase_id`` envelope.
            phase_raw = args.get("phase_id")
            phase_val = phase_raw if isinstance(phase_raw, str) else None
            tz_raw = args.get("tz")
            tz_val = tz_raw if isinstance(tz_raw, str) else None
            return tool_get_phase_analysis(
                session,
                internal_user_id,
                phase_id=phase_val,
                tz=tz_val,
            )

        if handler_key == "get_user_context":
            # V1.6 Phase B 3B.10 — no required arguments. ``tz`` is
            # optional and only affects "today" resolution + the
            # emitted ``preferences.timezone`` field. Unknown / non-
            # string tz falls back to UTC inside the service.
            tz_raw = args.get("tz")
            tz_val = tz_raw if isinstance(tz_raw, str) else None
            return tool_get_user_context(
                session,
                internal_user_id,
                tz=tz_val,
            )

        if handler_key == "get_marathon_projection":
            d_target = _parse_optional_date(args.get("target_race_date"))
            goal = args.get("goal_time_hhmmss")
            if goal is not None and not isinstance(goal, str):
                goal = None
            lookback_raw = args.get("lookback_days", 84)
            try:
                lookback_days = int(lookback_raw)
            except (TypeError, ValueError):
                lookback_days = 84
            return tool_get_marathon_projection(
                session,
                internal_user_id,
                target_race_date=d_target,
                goal_time_hhmmss=(goal or "").strip() or None,
                lookback_days=lookback_days,
            )

        if handler_key == "save_coach_preference":
            return tool_save_coach_preference(session, internal_user_id, args)

        if handler_key == "update_plan_intake":
            return tool_update_plan_intake(
                session,
                internal_user_id,
                args,
                current_state=plan_intake_state,
                source_user_message=source_user_message,
            )

        if handler_key == "generate_training_plan":
            return tool_generate_training_plan(
                session,
                internal_user_id,
                args,
                current_state=plan_intake_state,
            )

        return {"error": "unknown_tool", "message": f"Unknown tool: {name}"}
    except Exception as e:
        logger.exception("Tool execution failed tool=%s", name)
        return {
            "error": "tool_execution_failed",
            "message": str(e),
            "tool": name,
        }

"""Execute agent tools (server-side). Returns JSON-serializable dict."""

# pylint: disable=too-many-lines,import-outside-toplevel,broad-exception-caught,not-callable,missing-function-docstring,too-many-arguments,too-many-locals,too-many-return-statements,too-many-branches,too-many-statements,line-too-long,protected-access,redefined-outer-name,reimported,unused-import,unused-argument

from __future__ import annotations

import json
import logging
import os
import warnings
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, text, update

from src.db.dao.activity_dao import ActivityDAO
from src.coaching_intelligence.pre_generation_runner_assessment import (
    extract_alignment_answer_bookkeeping,
)
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
from src.smartcoach_mobile_coach.plan_creation_ui import (
    PHASE_AWAITING_TRADEOFF_CHOICE,
    PHASE_COLLECTING_ADDITIONAL_TRAINING_DAY,
    PHASE_GENERATED,
    sync_legacy_ux_from_phase,
)
from src.smartcoach_mobile_coach.readiness_gate import (
    get_or_compute_readiness_gate,
)
from src.smartcoach_mobile_coach.plan_intake_flow import (
    PLAN_UX_STAGE_GENERATED,
    build_plan_request_from_state,
    plan_creation_split_confirm_enabled,
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
from src.db.dao.user_profile_dao import get_user_profile
from src.smartcoach_mobile_coach.plan_generation import (
    generate_training_plan_tool,
    run_v2_plan_generation,
)
from src.services.training_plan.v2.plan_validation_silent_repair import (
    attempt_silent_repair_then_revalidate,
)
from src.services.training_plan.v2.race_distance_factory_v2 import (
    get_race_distance_services,
    normalize_race_distance,
)
from src.services.llm.openai_coach_adapter import OpenAICoachAdapter
from src.services.security.external_apis.openai_service import get_openai_service
from src.services.training_plan.plan_storage_service import PlanStorageService
from src.services.training_plan.v2.plan_coach import generate_plan_explanation
from src.services.training_plan.v2.plan_context_from_storage import (
    build_plan_context_from_active_plan,
)
from src.services.training_plan.v2.plan_insights import build_plan_insights
from src.utils.config import config
from src.utils.hr_zone_constants import (
    ALLOWED_METRICS,
    COACHING_LEVEL_DEFAULTS,
    hr_drift_band_zones_chart,
)

logger = logging.getLogger("smartcoach_mobile_coach")


def _record_plan_generation_tool_event(
    internal_user_id: str,
    outcome: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        from src.services.product_analytics_service import record_product_event

        record_product_event(
            event_name="plan_generation_tool",
            outcome=outcome,
            user_id=str(internal_user_id),
            source="server",
            properties=properties,
        )
    except Exception:
        logger.debug("plan_generation_tool analytics skipped", exc_info=True)


_DEFAULT_KPI_WEEKS = 4
_MAX_KPI_WEEKS = 52
_INTAKE_ALIGNMENT_FEATURE_FLAG = "SMARTCOACH_ENABLE_INTAKE_ALIGNMENT_V1"


def _increment_tool_call_count(session: Session, tool_name: str) -> None:
    """Best-effort counter bump; never blocks the tool response."""
    try:
        from src.db.models.coach_tools import CoachTool

        session.execute(
            update(CoachTool)
            .where(CoachTool.name == tool_name)
            .values(
                call_count=CoachTool.call_count + 1,
                last_called_at=func.now(),
            )
        )
        session.commit()
    except Exception:
        logger.debug("Could not increment call_count for %s", tool_name, exc_info=True)
        try:
            session.rollback()
        except Exception:
            logger.debug(
                "Could not rollback after call_count failure for %s",
                tool_name,
                exc_info=True,
            )


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


def _intake_alignment_enabled() -> bool:
    return (os.getenv(_INTAKE_ALIGNMENT_FEATURE_FLAG) or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


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
    - include_execution_kpis: activities execution columns + zone_bounds + insights_system
    - include_hr_profile: runner_zone_profiles profile (Z1–Z5, max/resting used)
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

    # V1.6 3B.8 Topic 5 — per-request dedup across repeat calls with
    # the same (user, week, tz, today) window. Past-week payloads are
    # stable; current-week bounded by TTL (new activity landing within
    # the TTL window is acceptable staleness); future-week invalidated
    # on plan regen via ``invalidate_user_plan_cache``.
    #
    # Import ``get_today_date_in_timezone`` from the service module so
    # the cache's "what is today" resolve follows the same binding the
    # service itself uses — tests that pin today on the service module
    # also pin the cache key without a separate patch.
    from src.services.plan.weekly_plan import (
        build_weekly_plan_payload,
        get_today_date_in_timezone,
    )
    from src.smartcoach_mobile_coach import plan_cache

    user_id_str = str(user_uuid)
    resolved_today = get_today_date_in_timezone(tz_value)
    today_iso = resolved_today.isoformat()
    extra_key = target_monday.isoformat() if target_monday is not None else "default"

    cached = plan_cache.get_cached(
        "weekly_plan",
        user_id_str,
        tz=tz_value,
        today_iso=today_iso,
        extra=extra_key,
    )
    if cached is not None:
        return cached

    payload = build_weekly_plan_payload(
        session,
        user_uuid,
        tz=tz_value,
        target_week_start=target_monday,
    )
    plan_cache.set_cached(
        "weekly_plan",
        user_id_str,
        payload,
        tz=tz_value,
        today_iso=today_iso,
        extra=extra_key,
    )
    return payload


# ---------------------------------------------------------------------------
# Tool: explain_current_plan (plan_insights + plan_coach, agent-integrated)
# ---------------------------------------------------------------------------


def tool_explain_current_plan(
    session: Session,
    internal_user_id: str,
) -> Dict[str, Any]:
    """
    Load the active plan, build :class:`~src.services.training_plan.v2.plan_context.PlanContext`,
    run :func:`~src.services.training_plan.v2.plan_insights.build_plan_insights`, and return
    natural-language copy from :func:`~src.services.training_plan.v2.plan_coach.generate_plan_explanation`.

    The authenticated user's id is always taken from the agent session — never from tool arguments.
    """
    import uuid as _uuid

    try:
        user_uuid = _uuid.UUID(str(internal_user_id))
    except (TypeError, ValueError):
        return {
            "error": "invalid_user_id",
            "message": "internal_user_id must be a UUID string.",
        }

    context = build_plan_context_from_active_plan(session, user_uuid)
    if context is None:
        return {
            "error": "no_plan",
            "message": "No training plan found for this account.",
        }

    insights = build_plan_insights(context)
    adapter = OpenAICoachAdapter(
        get_openai_service(),
        user_id=str(internal_user_id),
    )
    try:
        explanation = generate_plan_explanation(context, insights, adapter)
    except Exception:
        logger.exception(
            "explain_current_plan: plan_coach LLM failed user=%s",
            internal_user_id,
        )
        return {
            "error": "explanation_failed",
            "message": "Could not generate a plan explanation. Please try again.",
        }

    meta = context.metadata if isinstance(context.metadata, dict) else {}
    return {
        "explanation": explanation,
        "plan_id": meta.get("plan_id"),
        "plan_name": meta.get("plan_name"),
        "race_date": meta.get("race_date"),
        "race_distance": meta.get("race_distance"),
        "message": (
            "Use the `explanation` field as the grounded plan narrative. "
            "Do not invent long-run or weekly mileage figures beyond what it states."
        ),
    }


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

    # V1.6 3B.8 Topic 5 — plan_overview is planned-only (no activity
    # read), so it is effectively immutable between plan regens.
    # Cache keyed on (user, tz, today) with TTL and invalidation on
    # ``tool_generate_training_plan``. Today is resolved through the
    # service's own binding so tests that pin today on the service
    # also pin the cache key.
    from src.services.plan.plan_overview import (
        build_plan_overview_payload,
        get_today_date_in_timezone,
    )
    from src.smartcoach_mobile_coach import plan_cache

    user_id_str = str(user_uuid)
    today_iso = get_today_date_in_timezone(tz_value).isoformat()

    cached = plan_cache.get_cached(
        "plan_overview",
        user_id_str,
        tz=tz_value,
        today_iso=today_iso,
    )
    if cached is not None:
        return cached

    payload = build_plan_overview_payload(
        session,
        user_uuid,
        tz=tz_value,
    )
    plan_cache.set_cached(
        "plan_overview",
        user_id_str,
        payload,
        tz=tz_value,
        today_iso=today_iso,
    )
    return payload


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

    # V1.6 3B.8 Topic 5 — phase_analysis rolls up per-run-type data
    # through ``build_run_execution_block``. Cache keyed on (user,
    # phase, tz, today) with TTL and invalidation on plan regen.
    # Today is resolved through the service's own binding so tests
    # that pin today on the service also pin the cache key.
    from src.services.plan.phase_analysis import (
        build_phase_analysis_payload,
        get_today_date_in_timezone,
    )
    from src.smartcoach_mobile_coach import plan_cache

    user_id_str = str(user_uuid)
    today_iso = get_today_date_in_timezone(tz_value).isoformat()
    # Normalize case so "Base" and "base" hit the same cache entry;
    # the service already performs its own case-insensitive resolve.
    phase_key = phase_id.strip().lower() if isinstance(phase_id, str) else str(phase_id)

    cached = plan_cache.get_cached(
        "phase_analysis",
        user_id_str,
        tz=tz_value,
        today_iso=today_iso,
        extra=phase_key,
    )
    if cached is not None:
        return cached

    payload = build_phase_analysis_payload(
        session,
        user_uuid,
        phase_id,
        tz=tz_value,
    )
    plan_cache.set_cached(
        "phase_analysis",
        user_id_str,
        payload,
        tz=tz_value,
        today_iso=today_iso,
        extra=phase_key,
    )
    return payload


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

    # Resolve "today" once via the same helper the service uses so the
    # cache key and the payload can never drift across the tool/service
    # boundary (e.g. if this call straddles a midnight rollover).
    from src.services.user.user_context import (
        build_user_context_payload,
        get_today_date_in_timezone,
    )
    from src.smartcoach_mobile_coach import user_context_cache

    user_id_str = str(user_uuid)
    resolved_today = get_today_date_in_timezone(tz_value)
    today_iso = resolved_today.isoformat()

    # 3B.12: per-request dedup — repeated calls within the same
    # (user, tz, today) window reuse the first DB fan-out. Write paths
    # that mutate a producer input (prefs / plan / athlete link) call
    # ``invalidate_user_context`` after commit to keep reads fresh.
    cached = user_context_cache.get_cached(user_id_str, tz_value, today_iso)
    if cached is not None:
        return cached

    payload = build_user_context_payload(
        session,
        user_uuid,
        tz=tz_value,
        today=resolved_today,
    )
    user_context_cache.set_cached(user_id_str, tz_value, today_iso, payload)
    return payload


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

    # 3B.12: ``user_coach_preferences`` is an input of
    # ``build_user_context_payload.coaching``; drop any cached context
    # for this user so the next read rebuilds.
    from src.smartcoach_mobile_coach import user_context_cache

    user_context_cache.invalidate_user_context(str(internal_user_id))

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


# ---------------------------------------------------------------------------
# Tool: save_phase_goal (V1.6 Phase D 3D.2)
# ---------------------------------------------------------------------------


def tool_save_phase_goal(
    session: Session, internal_user_id: str, args: Dict[str, Any]
) -> Dict[str, Any]:
    """V1.6 Phase D 3D.2 — persist the athlete's current phase focus.

    Soft-semantics writer: no hard consent gate. The coach calls this
    whenever it has agreement (explicit or soft) from the user on a
    behavior-and-outcome focus sentence for the current / next phase.
    Supersede-then-insert keeps history without partial unique indexes.

    Args (``args`` dict — LLM-provided):
        phase: Required. One of Base / Build / Peak / Taper
            (case-insensitive).
        goal_text: Required. 1–280 chars behavior-and-outcome sentence
            (NOT a KPI threshold; see spec §19.4).
        source: Optional. One of ``auto_proposed`` / ``coach_refined``
            / ``user_stated``. Defaults to ``auto_proposed`` so the
            common path (coach proposes on phase entry) needs no arg.
        confirmed: Optional bool. When ``True`` stamps
            ``confirmed_at = now``; the coach uses this on turns where
            the user has explicitly agreed ("yes keep that as my focus").

    Returns:
        On success::

            {
                "saved": True,
                "goal": {id, plan_id, phase, goal_text, status,
                         source, confirmed_at, created_at},
                "superseded_goal_id": <int | None>,
                "message": "Saved your <phase> focus.",
            }

        On error, a standard ``{"error": code, "message": ...}``
        envelope where ``code`` is one of: ``invalid_user_id``,
        ``invalid_phase``, ``invalid_goal_text``, ``invalid_source``,
        ``no_active_plan``, ``tool_execution_failed``.
    """
    import uuid as _uuid

    from src.services.plan.phase_goal import save_phase_goal as service_save_phase_goal

    try:
        user_uuid = _uuid.UUID(str(internal_user_id))
    except (TypeError, ValueError):
        return {
            "error": "invalid_user_id",
            "message": "internal_user_id must be a UUID string.",
        }

    phase_raw = args.get("phase")
    goal_text_raw = args.get("goal_text")
    source_raw = args.get("source")
    confirmed_raw = args.get("confirmed", False)
    # Explicit bool coercion — LLM can emit "true" / "false" strings.
    if isinstance(confirmed_raw, str):
        confirmed = confirmed_raw.strip().lower() == "true"
    else:
        confirmed = bool(confirmed_raw)

    status, payload = service_save_phase_goal(
        session,
        user_uuid,
        phase_raw,
        goal_text_raw,
        source_raw=source_raw,
        confirmed=confirmed,
    )

    if status != "ok":
        # Service already wrote rollback-safe state (no-op on failed
        # validation paths because nothing was flushed). The tool layer
        # commits on success only.
        return payload

    try:
        session.commit()
    except Exception:
        logger.exception("[tool_save_phase_goal] commit failed")
        try:
            session.rollback()
        except Exception:
            logger.debug(
                "[tool_save_phase_goal] rollback after commit failure also failed",
                exc_info=True,
            )
        return {
            "error": "tool_execution_failed",
            "message": "Could not save phase goal. Please try again.",
        }

    phase_label = payload["goal"]["phase"]
    return {
        "saved": True,
        "goal": payload["goal"],
        "superseded_goal_id": payload["superseded_goal_id"],
        "message": f"Saved your {phase_label} focus.",
    }


def tool_remember_plan_preference(
    session: Session, internal_user_id: str, args: Dict[str, Any]
) -> Dict[str, Any]:
    """V1.6 Phase F — persist a user-stated plan preference (Layer C)."""
    import uuid as _uuid

    from datetime import datetime, timezone

    from src.smartcoach_mobile_coach.memory.plan_memory_store import (
        MEMORY_SOURCE_COACH_TOOL,
        append_plan_memory,
    )

    try:
        user_uuid = _uuid.UUID(str(internal_user_id))
    except (TypeError, ValueError):
        return {
            "error": "invalid_user_id",
            "message": "internal_user_id must be a UUID string.",
        }

    raw = args.get("preference_text")
    if not isinstance(raw, str) or not raw.strip():
        return {
            "error": "invalid_preference_text",
            "message": "preference_text is required (1–280 characters).",
        }
    text = raw.strip()
    if len(text) > 280:
        return {
            "error": "invalid_preference_text",
            "message": "preference_text must be at most 280 characters.",
        }

    row, deduplicated = append_plan_memory(
        session, user_uuid, text, source=MEMORY_SOURCE_COACH_TOOL
    )
    if row is None:
        return {
            "error": "invalid_preference_text",
            "message": "Could not normalize preference_text.",
        }

    try:
        session.commit()
    except Exception:
        logger.exception("[tool_remember_plan_preference] commit failed")
        try:
            session.rollback()
        except Exception:
            logger.debug(
                "[tool_remember_plan_preference] rollback after commit failure also failed",
                exc_info=True,
            )
        return {
            "error": "tool_execution_failed",
            "message": "Could not save preference. Please try again.",
        }

    from src.smartcoach_mobile_coach import user_context_cache

    user_context_cache.invalidate_user_context(str(user_uuid))

    created = row.created_at
    if isinstance(created, datetime):
        c = created
        if c.tzinfo is None:
            c = c.replace(tzinfo=timezone.utc)
        created_iso = c.replace(microsecond=0).isoformat()
    else:
        created_iso = None

    out: Dict[str, Any] = {
        "saved": True,
        "memory": {
            "id": str(row.id),
            "text": row.memory_text,
            "source": row.source,
            "created_at": created_iso,
        },
        "message": "I'll remember that for your training plans and context.",
    }
    mt = getattr(row, "memory_type", None)
    if mt:
        out["memory"]["memory_type"] = mt
    if deduplicated:
        out["deduplicated"] = True
        out["message"] = "I already had that noted — I'll keep using it."
    return out


def tool_apply_plan_adjustments(
    session: Session, internal_user_id: str, args: Dict[str, Any]
) -> Dict[str, Any]:
    """V1.6 Phase E — structured plan-adjustment writer.

    The LLM MUST supply a typed ``operations`` array — never free-text
    mutation instructions. This wrapper only owns:

    * UUID validation
    * commit / rollback semantics
    * stable error-envelope translation

    All normalization, cap enforcement, audit logging, and plan writes
    live in :mod:`src.services.plan.plan_adjustments`.
    """
    import uuid as _uuid

    from src.services.plan.plan_adjustments import apply_plan_adjustments

    try:
        user_uuid = _uuid.UUID(str(internal_user_id))
    except (TypeError, ValueError):
        return {
            "error": "invalid_user_id",
            "message": "internal_user_id must be a UUID string.",
        }

    status, payload = apply_plan_adjustments(
        session,
        user_uuid,
        week_start_date_raw=args.get("week_start_date"),
        operations_raw=args.get("operations"),
    )
    if status != "ok":
        return payload

    try:
        session.commit()
    except Exception:
        logger.exception("[tool_apply_plan_adjustments] commit failed")
        try:
            session.rollback()
        except Exception:
            logger.debug(
                "[tool_apply_plan_adjustments] rollback after commit failure also failed",
                exc_info=True,
            )
        return {
            "error": "tool_execution_failed",
            "message": "Could not apply plan adjustments. Please try again.",
        }

    return payload


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
    ready = bool(state.get("ready_to_generate"))
    ux_tip = state.get("ux") if isinstance(state.get("ux"), dict) else {}
    if ready and plan_creation_split_confirm_enabled():
        if not ux_tip.get("intake_confirmed"):
            merge_msg = (
                "All required fields are present. Ask for intake recap confirmation "
                "(race, goal, schedule) before the runner assessment."
            )
        elif not ux_tip.get("runner_review_delivered"):
            merge_msg = "Intake confirmed — runner assessment should follow on the assistant turn."
        elif not ux_tip.get("plan_generation_confirmed"):
            merge_msg = (
                "After your runner assessment, ask the athlete to tap Create my plan "
                "or say create/build/generate the plan."
            )
        else:
            merge_msg = (
                "Plan creation is authorized — call generate_training_plan with confirm=true "
                "when appropriate."
            )
    else:
        merge_msg = (
            "Plan intake updated. Ask one missing field next."
            if not ready
            else "All required fields are present. Ask for confirmation before generating."
        )
    return {
        "plan_intake_state": state,
        "status": state.get("status"),
        "ready_to_generate": ready,
        "missing_required": state.get("missing_required", []),
        "missing_required_labels": state.get("missing_required_labels", []),
        "errors": state.get("errors", []),
        "confirmation_summary": state.get("confirmation_summary"),
        "message": merge_msg,
    }


def tool_generate_training_plan(
    session: Session,
    internal_user_id: str,
    args: Dict[str, Any],
    *,
    current_state: Optional[Dict[str, Any]] = None,
    anchor_local_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Deterministically generate and save plan once intake is complete."""
    return generate_training_plan_tool(
        session=session,
        internal_user_id=internal_user_id,
        args=args,
        current_state=current_state,
        anchor_local_date=anchor_local_date,
        coerce_tool_bool=_coerce_tool_bool,
        plan_request_builder=build_plan_request_from_state,
        run_plan_fn=run_v2_plan_generation,
        readiness_gate_fn=get_or_compute_readiness_gate,
    )


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
    # Deterministic plan_insights + plan_coach LLM — narrative "why is my plan like this".
    "explain_current_plan": "explain_current_plan",
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
    # V1.6 Phase D 3D.2 — persist the athlete's current phase focus
    # (behavior/outcome sentence, NOT a KPI threshold). Supersede-
    # then-insert preserves history; ``confirmed=True`` stamps explicit
    # agreement. Soft-semantics writer: no hard consent gate, coach
    # decides based on conversational intent.
    "save_phase_goal": "save_phase_goal",
    "remember_plan_preference": "remember_plan_preference",
    # V1.6 Phase E minimal structured writer — the LLM emits typed
    # operations[] and the backend validates / caps / audits before any
    # plan mutation happens.
    "apply_plan_adjustments": "apply_plan_adjustments",
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

        if handler_key == "explain_current_plan":
            return tool_explain_current_plan(session, internal_user_id)

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

        if handler_key == "save_phase_goal":
            return tool_save_phase_goal(session, internal_user_id, args)

        if handler_key == "remember_plan_preference":
            return tool_remember_plan_preference(session, internal_user_id, args)

        if handler_key == "apply_plan_adjustments":
            return tool_apply_plan_adjustments(session, internal_user_id, args)

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
                anchor_local_date=anchor_local_date,
            )

        return {"error": "unknown_tool", "message": f"Unknown tool: {name}"}
    except Exception as e:
        logger.exception("Tool execution failed tool=%s", name)
        return {
            "error": "tool_execution_failed",
            "message": str(e),
            "tool": name,
        }

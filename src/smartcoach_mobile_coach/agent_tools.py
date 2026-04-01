"""Execute agent tools (server-side). Returns JSON-serializable dict."""

from __future__ import annotations

import json
import logging
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
from src.smartcoach_mobile_coach.run_insight import (
    apply_insight_table_labels,
    build_get_run_insight_payload,
)
from src.smartcoach_mobile_coach.training_kpi_service import (
    get_run_kpi_detail,
    get_training_progress,
)
from src.smartcoach_mobile_coach.weekly_insights_service import (
    get_latest_weekly_insight,
)
from src.utils.config import config
from src.utils.hr_zone_constants import (
    ALLOWED_METRICS,
    COACHING_LEVEL_DEFAULTS,
    hr_drift_band_zones_chart,
)

logger = logging.getLogger("smartcoach_mobile_coach")

_DEFAULT_KPI_WEEKS = 4
_MAX_KPI_WEEKS = 52


def _distance_miles_from_meters(meters) -> float:
    if meters is None:
        return 0.0
    return float(meters) * 0.000621371


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
        dm = _distance_miles_from_meters(act.distance)
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
                _distance_miles_from_meters(r.get("distance"))
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
    session: Session, internal_user_id: str, weeks: int = _DEFAULT_KPI_WEEKS
) -> Dict[str, Any]:
    weeks = max(1, min(weeks, _MAX_KPI_WEEKS))
    return get_training_progress(session, internal_user_id, weeks)


# ---------------------------------------------------------------------------
# Tool: get_weekly_training_insight
# ---------------------------------------------------------------------------


def tool_get_weekly_training_insight(
    session: Session, internal_user_id: str
) -> Dict[str, Any]:
    return get_latest_weekly_insight(session, internal_user_id)


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


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_TOOL_HANDLERS = {
    "find_runs_by_date": "find_runs_by_date",
    "search_runs": "search_runs",
    "get_run_summary": "get_run_summary",
    "get_training_kpis": "get_training_kpis",
    "get_weekly_training_insight": "get_weekly_training_insight",
    "save_coach_preference": "save_coach_preference",
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

    if handler_key == "get_training_kpis":
        weeks = args.get("weeks", _DEFAULT_KPI_WEEKS)
        try:
            weeks = int(weeks)
        except (TypeError, ValueError):
            weeks = _DEFAULT_KPI_WEEKS
        return tool_get_training_kpis(session, internal_user_id, weeks)

    if handler_key == "get_weekly_training_insight":
        return tool_get_weekly_training_insight(session, internal_user_id)

    if handler_key == "save_coach_preference":
        return tool_save_coach_preference(session, internal_user_id, args)

    return {"error": "unknown_tool", "message": f"Unknown tool: {name}"}

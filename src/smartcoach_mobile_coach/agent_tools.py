"""Execute agent tools (server-side). Returns JSON-serializable dict."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from src.db.dao.activity_dao import ActivityDAO
from src.smartcoach_mobile_coach.config import INSIGHT_SCHEMA_VERSION
from src.smartcoach_mobile_coach.db_helpers import get_primary_athlete_id
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
from src.utils.config import config

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
# Tool: get_run_summary
# ---------------------------------------------------------------------------


def tool_get_run_summary(
    session: Session,
    internal_user_id: str,
    activity_id: int,
    anchor_local_date: Optional[str] = None,
) -> Dict[str, Any]:
    ck = cache_key(internal_user_id, activity_id, INSIGHT_SCHEMA_VERSION)
    hit = get_cached(ck)
    if hit is not None:
        payload = apply_insight_table_labels(hit, anchor_local_date)
    else:
        payload = build_get_run_insight_payload(
            session, internal_user_id, activity_id, INSIGHT_SCHEMA_VERSION
        )
        if "error" not in payload:
            set_cached(ck, payload)
        payload = apply_insight_table_labels(payload, anchor_local_date)

    if payload.get("error"):
        return payload

    kpi_data = get_run_kpi_detail(session, internal_user_id, activity_id)
    if not kpi_data.get("error"):
        payload["training_kpis"] = kpi_data.get("kpis")
        payload["zone_bounds"] = kpi_data.get("zone_bounds")
        payload["is_easy_run"] = kpi_data.get("is_easy_run")

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
# Dispatch
# ---------------------------------------------------------------------------

_TOOL_HANDLERS = {
    "find_runs_by_date": "find_runs_by_date",
    "get_run_summary": "get_run_summary",
    "get_training_kpis": "get_training_kpis",
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
    import json

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

    if handler_key == "get_run_summary":
        aid = _parse_activity_id(args)
        if aid is None:
            return {
                "error": "missing_activity_id",
                "message": "activity_id must be a positive integer.",
            }
        return tool_get_run_summary(
            session, internal_user_id, aid, anchor_local_date=anchor_local_date
        )

    if handler_key == "get_training_kpis":
        weeks = args.get("weeks", _DEFAULT_KPI_WEEKS)
        try:
            weeks = int(weeks)
        except (TypeError, ValueError):
            weeks = _DEFAULT_KPI_WEEKS
        return tool_get_training_kpis(session, internal_user_id, weeks)

    return {"error": "unknown_tool", "message": f"Unknown tool: {name}"}

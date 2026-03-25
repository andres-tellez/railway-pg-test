"""Execute agent tools (server-side). Returns JSON-serializable dict."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from src.db.dao.activity_dao import ActivityDAO
from src.smartcoach_mobile_coach.config import INSIGHT_SCHEMA_VERSION
from src.smartcoach_mobile_coach.db_helpers import get_primary_athlete_id
from src.smartcoach_mobile_coach.display_format import (
    format_distance_mi,
    format_time_utc,
)
from src.smartcoach_mobile_coach.insight_cache import cache_key, get_cached, set_cached
from src.smartcoach_mobile_coach.run_insight import build_get_run_insight_payload
from src.utils.config import config


def _distance_miles_from_meters(meters) -> float:
    if meters is None:
        return 0.0
    return float(meters) * 0.000621371


def tool_list_runs_for_local_date(
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


def tool_get_run_insight(
    session: Session, internal_user_id: str, activity_id: int
) -> Dict[str, Any]:
    ck = cache_key(internal_user_id, activity_id, INSIGHT_SCHEMA_VERSION)
    hit = get_cached(ck)
    if hit is not None:
        return hit

    payload = build_get_run_insight_payload(
        session, internal_user_id, activity_id, INSIGHT_SCHEMA_VERSION
    )
    if "error" not in payload:
        set_cached(ck, payload)
    return payload


def execute_tool(
    session: Session,
    internal_user_id: str,
    name: str,
    arguments_json: str,
) -> Dict[str, Any]:
    import json

    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        return {
            "error": "invalid_arguments",
            "message": "Tool arguments were not valid JSON.",
        }

    if name == "list_runs_for_local_date":
        ld = args.get("local_date")
        if not ld or not isinstance(ld, str):
            return {
                "error": "missing_local_date",
                "message": "Parameter local_date (YYYY-MM-DD) is required.",
            }
        return tool_list_runs_for_local_date(session, internal_user_id, ld.strip())

    if name == "get_run_insight":
        raw = args.get("activity_id")
        try:
            aid = int(raw)
        except (TypeError, ValueError):
            return {
                "error": "missing_activity_id",
                "message": "activity_id must be an integer.",
            }
        if aid <= 0:
            return {
                "error": "invalid_activity_id",
                "message": "activity_id must be positive.",
            }
        return tool_get_run_insight(session, internal_user_id, aid)

    return {"error": "unknown_tool", "message": f"Unknown tool: {name}"}

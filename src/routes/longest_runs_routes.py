"""
Longest Runs Routes Module
===========================

This module provides API endpoints for retrieving longest run comparisons.
It follows the EXACT same architectural pattern as metrics_routes.py for consistency.

Pattern:
--------
1. PostgreSQL Materialized View (mv_longest_runs) - Pre-calculates everything
2. Simple SELECT query - No complex logic in Python
3. In-memory caching - 5-10 min TTL
4. Single API endpoint - One call gets all data
5. Minimal formatting - Only pace/date formatting in Python

Endpoints:
----------
GET /api/longest-runs/data?weeks=8
    Returns all longest run data for the specified number of weeks.
    Default: 8 weeks. Options: 4, 8, 12, 16, 20

GET /api/longest-runs/config
    Returns configuration options (time periods, thresholds, etc.)

Dependencies:
------------
- SQLAlchemy: ORM for database interaction
- Flask: Web framework for routing
- Auth0 JWT: Authentication decorator
- Metrics Cache Service: In-memory caching (reusing existing service)
- User Identity DAO: Resolves internal user IDs

Data Source:
-----------
- mv_longest_runs (Materialized View): Pre-calculated longest runs with all metadata

Author: SmartCoach Development Team
Last Updated: October 12, 2025
"""

from flask import Blueprint, jsonify, g, request
from datetime import datetime, timedelta
from src.db.db_session import get_session
from src.services.metrics_cache_service import (
    get_cached_metrics,
    set_cached_metrics,
    _get_cache_key,
)
from src.utils.auth0_jwt import requires_auth
from src.utils.auth_helpers import get_user_id_from_request
from src.utils.normalize_claims import normalize_claims
from sqlalchemy import text
import time
import traceback

longest_runs_bp = Blueprint("longest_runs", __name__, url_prefix="/api/longest-runs")

# Configuration (can be moved to database later)
DEFAULT_CONFIG = {
    "time_periods": {"default": 8, "options": [4, 8, 12, 16, 20]},
    "thresholds": {
        "pr_detection_window_weeks": 52,
        "significant_drop_percentage": 20,
        "significant_drop_min_distance": 1.0,
        "stable_threshold_percentage": 5,
        "improvement_min_percentage": 5,
    },
}


def format_pace(avg_speed_mps: float) -> str:
    """
    Convert average speed (m/s) to pace (min/mi).
    Follows exact same pattern as metrics_routes.py
    """
    if not avg_speed_mps or avg_speed_mps == 0:
        return "0:00"

    seconds_per_mile = 1609.34 / avg_speed_mps
    minutes = int(seconds_per_mile // 60)
    seconds = int(seconds_per_mile % 60)

    return f"{minutes}:{seconds:02d}"


def format_duration(seconds: int) -> str:
    """Format duration in seconds to HH:MM:SS"""
    if not seconds:
        return "0:00:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def get_athlete_id_for_user(session, user_id) -> int | None:
    """
    Helper function to get athlete_id from user_id.
    Follows exact same pattern as metrics_routes.py
    """
    stmt = text(
        """
        SELECT athlete_id
        FROM public.user_athletes
        WHERE user_id = :uid
        LIMIT 1
        """
    )

    result = session.execute(stmt, {"uid": user_id}).fetchone()
    return result.athlete_id if result else None


def get_longest_runs_ultra_optimized(session, athlete_id: int, weeks: int = 8):
    """
    ULTRA-OPTIMIZED: Get ALL longest run data from materialized view.
    This is the fastest possible approach - simple SELECT, all processing done by database.

    Follows EXACT same pattern as get_all_metrics_ultra_optimized() in metrics_routes.py
    """
    # Single simple query to materialized view
    result = session.execute(
        text("SELECT * FROM mv_longest_runs WHERE athlete_id = :athlete_id"),
        {"athlete_id": athlete_id},
    ).first()

    if not result or not result.weekly_runs:
        return {
            "runs": [],
            "summary": {
                "total_weeks": 0,
                "pr_count": 0,
                "drop_count": 0,
                "improving_weeks": 0,
            },
        }

    # Extract weekly runs (pre-aggregated by database)
    weekly_runs = result.weekly_runs

    # Filter to requested number of weeks (frontend can also filter)
    filtered_runs = (
        weekly_runs[:weeks] if weeks and weeks < len(weekly_runs) else weekly_runs
    )

    # Format data (only formatting, no calculations)
    formatted_runs = []
    for run in filtered_runs:
        formatted_runs.append(
            {
                "week_start": run["week_start"],
                "activity_id": run["activity_id"],
                "name": run["name"],
                "date": run["date"],
                "distance": float(run["distance"]),
                "pace": format_pace(run["average_speed"]),
                "duration": format_duration(run["moving_time"]),
                "heart_rate_zones": run["heart_rate_zones"],
                "is_personal_record": run["is_personal_record"],
                "is_significant_drop": run["is_significant_drop"],
                "trend": run["trend"],
                "change_pct": float(run["change_pct"]),
                "prev_week_distance": (
                    float(run["prev_week_distance"])
                    if run["prev_week_distance"]
                    else None
                ),
            }
        )

    # Extract summary stats (pre-calculated by database)
    summary = {
        "total_weeks": int(result.total_weeks),
        "pr_count": int(result.pr_count),
        "drop_count": int(result.drop_count),
        "improving_weeks": int(result.improving_weeks),
    }

    return {"runs": formatted_runs, "summary": summary}


@longest_runs_bp.route("/data", methods=["GET"])
@requires_auth
def get_longest_runs_data():
    """
    Get longest runs data in a single optimized call.
    Follows EXACT same pattern as get_all_metrics_combined() in metrics_routes.py

    Query Parameters:
        weeks (int): Number of weeks to return (default: 8)
    """
    session = get_session()

    try:
        # Get user identity (same as metrics)
        from src.utils.auth_helpers import get_user_id_from_request

        claims = getattr(g, "current_user", {}) or {}
        claims = normalize_claims(claims)

        user_id, error = get_user_id_from_request(claims, create_if_missing=False)
        if error:
            return error

        # Get athlete_id
        athlete_id = get_athlete_id_for_user(session, user_id)

        if not athlete_id:
            return (
                jsonify(
                    {
                        "error": "No Strava connection found",
                        "runs": [],
                        "summary": {},
                    }
                ),
                200,
            )

        # Get weeks parameter
        weeks = request.args.get("weeks", type=int, default=8)

        # Validate weeks parameter
        if weeks not in DEFAULT_CONFIG["time_periods"]["options"]:
            weeks = DEFAULT_CONFIG["time_periods"]["default"]

        # Check cache first
        cache_key = _get_cache_key(athlete_id, f"longest_runs_{weeks}")
        cached_result = get_cached_metrics(cache_key)
        if cached_result is not None:
            print(f"[CACHE HIT] Longest runs for athlete {athlete_id} ({weeks} weeks)")
            return jsonify(cached_result), 200

        print(f"[CACHE MISS] Longest runs for athlete {athlete_id} ({weeks} weeks)")

        # Performance timing
        start_time = time.time()

        # ULTRA-OPTIMIZED: Single query to materialized view
        result = get_longest_runs_ultra_optimized(session, athlete_id, weeks)

        # Cache the result for 5 minutes (same as metrics)
        set_cached_metrics(cache_key, result, ttl=300)

        # Performance logging
        execution_time = time.time() - start_time
        print(f"[PERF] Longest runs query took {execution_time:.3f}s")

        return jsonify(result), 200

    except Exception as e:
        print(f"[ERROR] Error in get_longest_runs_data: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

    finally:
        session.close()


@longest_runs_bp.route("/config", methods=["GET"])
@requires_auth
def get_longest_runs_config():
    """
    Get configuration for longest runs feature.
    Returns available time periods and thresholds.
    """
    try:
        return jsonify(DEFAULT_CONFIG), 200

    except Exception as e:
        print(f"[ERROR] Error in get_longest_runs_config: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": "Failed to get configuration"}), 500

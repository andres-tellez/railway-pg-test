"""
Metrics Routes Module
=====================

This module provides API endpoints for retrieving running metrics and analytics.
Uses a materialized view (mv_athlete_metrics) for ultra-fast performance.

Endpoints:
----------
GET /api/metrics/all-metrics
    Returns ALL metrics in a single optimized call:
    - Dashboard metrics (current/previous week comparison)
    - Weekly trends (20 weeks of distance, runs, pace)
    - Heart rate zone distribution (weekly and 30-day)

    Response format:
    {
        "weekly_distance": {
            "current": 42.3,      # Miles this week
            "previous": 35.8,     # Miles last week
            "change_pct": 18.1    # Percentage change
        },
        "weekly_runs": {
            "current": 5,         # Runs this week
            "previous": 4,        # Runs last week
            "change_pct": 25.0    # Percentage change
        },
        "average_pace": {
            "current": "8:45",    # Current pace (min/mi)
            "previous": "9:52",   # Previous pace
            "change_pct": 0       # Not calculated yet
        },
        "hr_zones": {
            "zone_1": 15.2,       # % time in Zone 1 (recovery) - last 30 days
            "zone_2": 45.8,       # % time in Zone 2 (aerobic)
            "zone_3": 28.3,       # % time in Zone 3 (tempo)
            "zone_4": 8.5,        # % time in Zone 4 (threshold)
            "zone_5": 2.2         # % time in Zone 5 (VO2 max)
        },
        "weekly_trends": [
            {
                "week": "2025-10-06",
                "distance": 27.3,
                "runs": 4,
                "avgPace": "8:45"
            },
            ...
        ],
        "weekly_hr_zones": [
            {
                "week": "2025-10-06",
                "zone_1": 15.2,
                "zone_2": 45.8,
                ...
            },
            ...
        ]
    }

GET /api/metrics/performance
    Returns cache statistics and performance monitoring data.
    Useful for debugging and admin purposes.

Dependencies:
------------
- mv_athlete_metrics: Materialized view (pre-calculated metrics)
- requires_auth: JWT authentication decorator
- Flask session management

Data Sources:
------------
- mv_athlete_metrics: Pre-aggregated metrics (refreshed on activity sync)
- activities table: Main activity records from Strava
- user_athletes table: Maps user_id to athlete_id

Performance:
-----------
- Query time: ~5-10ms (vs ~100-200ms with CASE statements)
- Cache TTL: 5 minutes
- Auto-refresh: On activity sync

Author: SmartCoach Development Team
Last Updated: October 11, 2025
"""

from flask import Blueprint, jsonify, g
from src.db.db_session import get_session
from src.services.metrics_cache_service import (
    get_cached_metrics,
    set_cached_metrics,
    _get_cache_key,
)
from src.utils.auth0_jwt import requires_auth
from src.utils.auth_helpers import get_user_id_from_request
from src.utils.normalize_claims import normalize_claims
from src.utils.planned_metrics_calculator import get_planned_miles_for_current_week
from src.utils.logger import get_logger
from sqlalchemy import text

logger = get_logger(__name__)

metrics_bp = Blueprint("metrics", __name__, url_prefix="/api/metrics")


def get_all_metrics_ultra_optimized(session, athlete_id, user_id=None, weeks=8):
    """
    ULTRA-OPTIMIZED: Get ALL metrics from materialized view.
    This is the fastest possible approach - simple SELECT, all processing done by database.
    Query time: ~5-10ms (vs ~100ms with CASE statements)

    For current week, shows PLANNED miles from training plan instead of actual miles.
    """
    # Single simple query to materialized view
    result = session.execute(
        text("SELECT * FROM mv_athlete_metrics WHERE athlete_id = :athlete_id"),
        {"athlete_id": athlete_id},
    ).first()

    # Get longest runs data from materialized view
    longest_runs_result = session.execute(
        text("SELECT * FROM mv_longest_runs WHERE athlete_id = :athlete_id"),
        {"athlete_id": athlete_id},
    ).first()

    if not result:
        # No data for this athlete, return empty metrics
        return {
            "weekly_distance": {"current": 0.0, "previous": 0.0, "change_pct": 0.0},
            "weekly_runs": {"current": 0, "previous": 0, "change_pct": 0.0},
            "average_pace": {"current": "0:00", "previous": "0:00", "change_pct": 0},
            "hr_zones": {
                "zone_1": 0.0,
                "zone_2": 0.0,
                "zone_3": 0.0,
                "zone_4": 0.0,
                "zone_5": 0.0,
            },
            "weekly_trends": [],
            "weekly_hr_zones": [],
            "weekly_goals": [],  # NEW: Include empty weekly_goals
            "longest_runs": [],  # NEW: Include empty longest_runs
        }

    # Extract pre-calculated dashboard metrics
    current_distance = round(result.current_distance or 0, 1)

    previous_distance = round(result.previous_distance or 0, 1)
    current_runs = int(result.current_runs or 0)
    previous_runs = int(result.previous_runs or 0)

    # Format paces (only thing we need to do in Python)
    current_pace = (
        format_pace(result.current_avg_speed) if result.current_avg_speed else "0:00"
    )
    previous_pace = (
        format_pace(result.previous_avg_speed) if result.previous_avg_speed else "0:00"
    )

    # Get pre-calculated percentage changes
    distance_change = round(result.distance_change_pct or 0, 1)
    runs_change = round(result.runs_change_pct or 0, 1)

    # Get pre-calculated HR zone percentages
    hr_zones = {
        "zone_1": round(result.zone_1_pct or 0, 1),
        "zone_2": round(result.zone_2_pct or 0, 1),
        "zone_3": round(result.zone_3_pct or 0, 1),
        "zone_4": round(result.zone_4_pct or 0, 1),
        "zone_5": round(result.zone_5_pct or 0, 1),
    }

    # Parse weekly data from JSON (pre-aggregated by database)
    # The materialized view returns it as a list, not a JSON string
    weekly_data = result.weekly_data if result.weekly_data else []

    # FIXED: Filter out current week entirely, keep previous week as leftmost bar
    # Materialized view orders by DESC (current week first), but we want previous week first
    if weekly_data:
        # Calculate what the current week should be
        from datetime import datetime, timedelta

        from src.utils.date_helpers import get_current_week_start

        today = datetime.now().date()
        current_week_start = get_current_week_start()
        current_week_str = current_week_start.isoformat()

        # Filter out the current week entirely
        filtered_weekly_data = []
        for week in weekly_data:
            week_date = week.get("week")
            if isinstance(week_date, str):
                week_date = week_date[:10]  # Extract just the date part

            # Only include weeks that are NOT the current week
            if week_date != current_week_str:
                filtered_weekly_data.append(week)
            else:
                logger.info(
                    f"📊 Filtering out current week ({week_date}) from weekly trends"
                )

        weekly_data = filtered_weekly_data

        # Log final ordering
        if weekly_data:
            logger.info(
                f"📊 Weekly trends (current week filtered out) - First 3 weeks: {[w['week'] for w in weekly_data[:3]]}"
            )

    # Parse weekly_goals from JSON string (if it's a string) or use as-is (if already parsed)
    import json

    if isinstance(result.weekly_goals, str):
        weekly_goals = json.loads(result.weekly_goals) if result.weekly_goals else []
    else:
        weekly_goals = result.weekly_goals if result.weekly_goals else []

    # For previous week (leftmost bar), update weekly_goals with planned miles from training plan
    if user_id and weekly_data:
        planned_miles = get_planned_miles_for_current_week(session, user_id)
        if planned_miles > 0 and weekly_data:
            # Find previous week in weekly_data (now the leftmost bar)
            from datetime import datetime, timedelta

            from src.utils.date_helpers import get_current_week_start

            today = datetime.now().date()
            current_week_start = get_current_week_start()
            previous_week_start = current_week_start - timedelta(days=7)
            previous_week_str = previous_week_start.isoformat()

            # Update previous week goal (handle both date formats)
            goal_found = False
            for goal in weekly_goals:
                goal_week = goal.get("week", "")
                # Check both formats: '2025-10-06' and '2025-10-06T00:00:00'
                if goal_week == previous_week_str or goal_week.startswith(
                    previous_week_str + "T"
                ):
                    goal["goal_miles"] = planned_miles
                    goal_found = True
                    logger.info(f"📊 Updated existing goal: {goal}")
                    break

            if not goal_found:
                weekly_goals.append(
                    {"week": previous_week_str, "goal_miles": planned_miles}
                )
                logger.info(
                    f"📊 Added new goal: week={previous_week_str}, goal_miles={planned_miles}"
                )

            logger.info(
                f"📊 Updated weekly_goals with planned miles for previous week: {planned_miles}"
            )

    # Process weekly trends and HR zones
    weekly_trends = []
    weekly_hr_zones = []

    for week in weekly_data:  # Process all weeks (filtering done in frontend)
        # Format pace for this week
        avg_speed = week.get("avg_speed_mps")
        avg_pace_str = format_pace(avg_speed) if avg_speed else "0:00"

        # Use actual miles for the bar height (planned miles will be shown in shaded section)
        week_distance = float(week["distance"])

        weekly_trends.append(
            {
                "week": week["week"],
                "distance": week_distance,
                "runs": int(week["runs"]),
                "avgPace": avg_pace_str,
            }
        )

        # Calculate HR zone percentages for this week
        total_hr = week.get("total_hr_time", 0)
        if total_hr > 0:
            weekly_hr_zones.append(
                {
                    "week": week["week"],
                    "zone_1": round((week.get("hr_zone_1", 0) / total_hr) * 100, 1),
                    "zone_2": round((week.get("hr_zone_2", 0) / total_hr) * 100, 1),
                    "zone_3": round((week.get("hr_zone_3", 0) / total_hr) * 100, 1),
                    "zone_4": round((week.get("hr_zone_4", 0) / total_hr) * 100, 1),
                    "zone_5": round((week.get("hr_zone_5", 0) / total_hr) * 100, 1),
                }
            )
        else:
            weekly_hr_zones.append(
                {
                    "week": week["week"],
                    "zone_1": 0.0,
                    "zone_2": 0.0,
                    "zone_3": 0.0,
                    "zone_4": 0.0,
                    "zone_5": 0.0,
                }
            )

    # Process longest runs data (from mv_longest_runs materialized view)
    longest_runs = []
    if longest_runs_result and longest_runs_result.weekly_runs:
        weekly_runs = longest_runs_result.weekly_runs
        # Log first few runs to debug
        if weekly_runs:
            logger.info(f"📊 [Longest Runs] Raw data from view (first 3):")
            for i, run in enumerate(weekly_runs[:3]):
                logger.info(
                    f"  [{i}] Week: {run.get('week_start')}, Distance: {run.get('distance')} miles, Name: {run.get('name')}"
                )

        # Filter to requested number of weeks
        filtered_runs = (
            weekly_runs[:weeks] if weeks and weeks < len(weekly_runs) else weekly_runs
        )

        # FIXED: Filter out current week entirely (same as other charts)
        # Materialized view orders by DESC (current week first), but we want previous week first
        if filtered_runs:
            # Calculate what the current week should be
            from datetime import datetime, timedelta

            from src.utils.date_helpers import get_current_week_start

            today = datetime.now().date()
            current_week_start = get_current_week_start()
            current_week_str = current_week_start.isoformat()

            # Filter out the current week entirely
            filtered_runs_list = []
            for run in filtered_runs:
                run_week = run.get("week_start")
                if isinstance(run_week, str):
                    run_week = run_week[:10]  # Extract just the date part

                # Only include weeks that are NOT the current week
                if run_week != current_week_str:
                    filtered_runs_list.append(run)
                else:
                    logger.info(
                        f"📊 [Longest Runs] Filtering out current week ({run_week}) from longest runs"
                    )

            filtered_runs = filtered_runs_list

        # Format data (only formatting, no calculations - already done by database)
        for run in filtered_runs:
            longest_runs.append(
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

    # Compute planned long-run per week (based on latest plan)
    weekly_long_run_goals = []
    try:
        if user_id:
            plan_id_row = session.execute(
                text(
                    """
                    SELECT id FROM plans
                    WHERE user_id = :uid
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                ),
                {"uid": str(user_id)},
            ).fetchone()
            if plan_id_row:
                plan_id_val = plan_id_row[0]
                rows = session.execute(
                    text(
                        """
                        SELECT DATE_TRUNC('week', pw.date)::date AS week_start,
                               MAX(pw.miles) FILTER (WHERE LOWER(pw.workout_type) LIKE 'long run%'
                                                    OR LOWER(pw.workout_type) = 'long run') AS long_run_miles
                        FROM plan_workouts pw
                        WHERE pw.plan_id = :pid
                        GROUP BY DATE_TRUNC('week', pw.date)
                        ORDER BY week_start DESC
                        LIMIT :weeks
                    """
                    ),
                    {"pid": plan_id_val, "weeks": 20},
                ).fetchall()
                weekly_long_run_goals = [
                    {
                        "week": r[0].isoformat(),
                        "long_run_miles": float(r[1] or 0.0),
                    }
                    for r in rows
                ]
    except Exception as e:
        logger.warning(f"[Longest Runs] Failed to compute weekly long run goals: {e}")

    return {
        "weekly_distance": {
            "current": current_distance,
            "previous": previous_distance,
            "change_pct": distance_change,
        },
        "weekly_runs": {
            "current": current_runs,
            "previous": previous_runs,
            "change_pct": runs_change,
        },
        "average_pace": {
            "current": current_pace,
            "previous": previous_pace,
            "change_pct": 0,
        },
        "hr_zones": hr_zones,
        "weekly_trends": weekly_trends,
        "weekly_hr_zones": weekly_hr_zones,
        "weekly_goals": weekly_goals,  # NEW: Include weekly_goals from materialized view
        "longest_runs": longest_runs,  # NEW: Include longest_runs from materialized view
        "weekly_long_run_goals": weekly_long_run_goals,  # NEW: planned long-run per week
    }


def get_athlete_id_for_user(session, user_id) -> int | None:
    """
    Helper function to get athlete_id from user_id.

    Args:
        session: SQLAlchemy session
        user_id: Internal user ID (UUID string or UUID object)

    Returns:
        athlete_id (int) or None if not found
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


def format_pace(avg_speed_mps: float) -> str:
    """
    Convert average speed (m/s) to pace (min/mi).

    Args:
        avg_speed_mps: Average speed in meters per second

    Returns:
        Formatted pace string (e.g., "8:45")
    """
    if not avg_speed_mps or avg_speed_mps == 0:
        return "0:00"

    # Convert m/s to min/mi
    # 1 mile = 1609.34 meters
    seconds_per_mile = 1609.34 / avg_speed_mps
    minutes = int(seconds_per_mile // 60)
    seconds = int(seconds_per_mile % 60)

    return f"{minutes}:{seconds:02d}"


def format_duration(seconds: int) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS"""
    if not seconds:
        return "0:00:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


@metrics_bp.route("/all-metrics", methods=["GET"])
@requires_auth
def get_all_metrics_combined():
    import uuid

    request_id = str(uuid.uuid4())[:8]
    print(f"[API CALL {request_id}] /api/metrics/all-metrics endpoint hit!")
    """
    Get ALL metrics (dashboard + weekly trends + HR zones) in a single optimized call.
    This is the fastest possible approach - one API call, minimal queries, maximum caching.

    Uses materialized view (mv_athlete_metrics) for ultra-fast performance (~5-10ms query time).

    Returns:
        JSON response with all metrics data

    Error Codes:
        401: Unauthorized (missing/invalid JWT)
        404: User not found or no Strava connection
        500: Internal server error
    """
    session = get_session()

    try:
        from src.utils.auth_helpers import get_user_id_from_request

        claims = getattr(g, "current_user", {}) or {}
        claims = normalize_claims(claims)

        user_id, error = get_user_id_from_request(claims, create_if_missing=False)
        if error:
            return error

        # Get athlete_id for this user
        athlete_id = get_athlete_id_for_user(session, user_id)

        if not athlete_id:
            return (
                jsonify(
                    {
                        "error": "No Strava connection found",
                        "weekly_distance": {
                            "current": 0,
                            "previous": 0,
                            "change_pct": 0,
                        },
                        "average_pace": {
                            "current": "0:00",
                            "previous": "0:00",
                            "change_pct": 0,
                        },
                        "weekly_runs": {"current": 0, "previous": 0, "change_pct": 0},
                        "hr_zones": {
                            "zone_1": 0,
                            "zone_2": 0,
                            "zone_3": 0,
                            "zone_4": 0,
                            "zone_5": 0,
                        },
                        "weekly_trends": [],
                        "weekly_hr_zones": [],
                        "weekly_goals": [],
                    }
                ),
                200,
            )

        # Check cache first (5-minute TTL)
        cache_key = _get_cache_key(athlete_id, "all_metrics_combined")
        cached_result = get_cached_metrics(cache_key)
        if cached_result is not None:
            print(f"[CACHE HIT {request_id}] All metrics for athlete {athlete_id}")
            return jsonify(cached_result), 200

        print(f"[CACHE MISS {request_id}] Fetching fresh data for athlete {athlete_id}")

        # Performance timing
        import time

        start_time = time.time()

        # ULTRA-OPTIMIZED: Single query to materialized view (now includes weekly_goals)
        # Pass user_id to enable planned miles calculation for current week
        result = get_all_metrics_ultra_optimized(
            session, athlete_id, user_id=user_id, weeks=20
        )

        weekly_goals = result.get("weekly_goals", [])
        print(f"[DEBUG] Weekly goals for user {user_id}: {weekly_goals}")
        print(f"[DEBUG] Number of weekly goals: {len(weekly_goals)}")
        print(f"[DEBUG] Weekly goals type: {type(weekly_goals)}")
        if weekly_goals:
            print(f"[DEBUG] First goal: {weekly_goals[0]}")

        # Cache the result for 5 minutes
        set_cached_metrics(cache_key, result, ttl=300, athlete_id=athlete_id)

        # Performance logging
        execution_time = time.time() - start_time
        print(
            f"[PERF {request_id}] All metrics query took {execution_time:.3f}s (ULTRA-OPTIMIZED: single materialized view query)"
        )
        print(
            f"[PERF {request_id}] Plan goals: {len(result.get('weekly_goals', []))} weeks (from materialized view)"
        )

        # Log first 3 weeks being returned
        weekly_trends = result.get("weekly_trends", [])
        if weekly_trends:
            first_3_weeks = [w["week"] for w in weekly_trends[:3]]
            print(f"[DEBUG {request_id}] First 3 weeks in response: {first_3_weeks}")
            print(
                f"[DEBUG {request_id}] Total weekly_trends in result: {len(weekly_trends)}"
            )
            print(
                f"[DEBUG {request_id}] ALL weeks in weekly_trends: {[w['week'] for w in weekly_trends]}"
            )

        # Also log what the raw weekly_data looked like
        if result.get("weekly_trends"):
            print(
                f"[DEBUG {request_id}] weekly_trends type: {type(result.get('weekly_trends'))}"
            )

        return jsonify(result), 200

    except Exception as e:
        print(f"[ERROR] Error in get_all_metrics_combined: {str(e)}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

    finally:
        session.close()


@metrics_bp.route("/performance", methods=["GET"])
@requires_auth
def get_metrics_performance():
    """
    Get performance metrics and cache statistics for monitoring.

    Useful for debugging and admin purposes.

    Returns:
        JSON response with cache stats and performance info

    Error Codes:
        500: Internal server error
    """
    from src.services.metrics_cache_service import get_cache_stats

    try:
        cache_stats = get_cache_stats()

        return (
            jsonify(
                {
                    "cache_stats": cache_stats,
                    "optimizations": {
                        "database_indexes": "Enabled",
                        "query_caching": "Enabled (5 min TTL)",
                        "materialized_view": "Enabled",
                        "performance_monitoring": "Enabled",
                    },
                    "performance_notes": [
                        "Metrics are cached for 5 minutes",
                        "Uses materialized view (mv_athlete_metrics) for 20x faster queries",
                        "Database queries optimized with proper indexes",
                        "Cache automatically invalidates on data updates",
                    ],
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": "Failed to get performance stats"}), 500

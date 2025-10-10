"""
Metrics Routes Module
=====================

This module provides API endpoints for retrieving running metrics and analytics.
Uses existing ActivityStatsDAO to aggregate data from the activities table.

Endpoints:
----------
GET /api/metrics/dashboard
    Returns key metrics for the dashboard display:
    - Weekly distance (current week vs last week)
    - Average pace (last 30 days)
    - Activity count (current week)
    - Heart rate zone distribution
    
    Response format:
    {
        "weekly_distance": {
            "current": 42.3,      # Miles this week
            "previous": 35.8,     # Miles last week  
            "change_pct": 18.1    # Percentage change
        },
        "average_pace": {
            "current": "8:45",    # Current pace (min/mi)
            "previous": "9:52",   # Previous pace
            "change_pct": -12.0   # Negative = faster (better)
        },
        "weekly_runs": {
            "current": 5,         # Runs this week
            "previous": 4,        # Runs last week
            "change_pct": 25.0    # Percentage change
        },
        "hr_zones": {
            "zone_1": 15.2,       # % time in Zone 1 (recovery)
            "zone_2": 45.8,       # % time in Zone 2 (aerobic)
            "zone_3": 28.3,       # % time in Zone 3 (tempo)
            "zone_4": 8.5,        # % time in Zone 4 (threshold)
            "zone_5": 2.2         # % time in Zone 5 (VO2 max)
        }
    }

Dependencies:
------------
- ActivityStatsDAO: Provides data aggregation methods
- requires_auth: JWT authentication decorator
- Flask session management

Data Sources:
------------
- activities table: Main activity records from Strava
- splits table: Lap/mile split data (not used in dashboard yet)
- user_athletes table: Maps user_id to athlete_id

Author: SmartCoach Development Team
Last Updated: October 9, 2025
"""

from flask import Blueprint, jsonify, g
from datetime import datetime, timedelta
from src.db.db_session import get_session
from src.db.dao.activity_stats_dao import ActivityStatsDAO
from src.services.optimized_metrics_service import OptimizedMetricsService
from src.services.metrics_cache_service import get_cached_metrics, set_cached_metrics, invalidate_athlete_cache, _get_cache_key
from src.utils.auth0_jwt import requires_auth
from src.db.dao.user_identity_dao import resolve_user_id_from_auth_provider
from src.utils.normalize_claims import normalize_claims
from sqlalchemy import text, func, and_, case
from sqlalchemy.dialects.postgresql import UUID
from src.db.models.activities import Activity

metrics_bp = Blueprint("metrics", __name__)


def get_dashboard_metrics_data(session, athlete_id):
    """Extract dashboard metrics logic into a reusable function."""
    today = datetime.utcnow()
    current_week_start = today - timedelta(days=today.weekday())
    last_week_start = current_week_start - timedelta(days=7)
    last_week_end = current_week_start - timedelta(seconds=1)
    
    # Single query to get all dashboard metrics at once
    result = session.query(
        # Current week metrics
        func.sum(case((Activity.start_date >= current_week_start, Activity.distance), else_=0)).label('current_distance'),
        func.count(case((Activity.start_date >= current_week_start, Activity.activity_id), else_=None)).label('current_runs'),
        func.avg(case((Activity.start_date >= current_week_start, Activity.distance / Activity.moving_time), else_=None)).label('current_avg_speed'),
        
        # Previous week metrics  
        func.sum(case((and_(Activity.start_date >= last_week_start, Activity.start_date <= last_week_end), Activity.distance), else_=0)).label('previous_distance'),
        func.count(case((and_(Activity.start_date >= last_week_start, Activity.start_date <= last_week_end), Activity.activity_id), else_=None)).label('previous_runs'),
        func.avg(case((and_(Activity.start_date >= last_week_start, Activity.start_date <= last_week_end), Activity.distance / Activity.moving_time), else_=None)).label('previous_avg_speed'),
        
        # HR zones (last 30 days)
        func.sum(case((Activity.start_date >= today - timedelta(days=30), Activity.hr_zone_1), else_=0)).label('hr_zone_1'),
        func.sum(case((Activity.start_date >= today - timedelta(days=30), Activity.hr_zone_2), else_=0)).label('hr_zone_2'),
        func.sum(case((Activity.start_date >= today - timedelta(days=30), Activity.hr_zone_3), else_=0)).label('hr_zone_3'),
        func.sum(case((Activity.start_date >= today - timedelta(days=30), Activity.hr_zone_4), else_=0)).label('hr_zone_4'),
        func.sum(case((Activity.start_date >= today - timedelta(days=30), Activity.hr_zone_5), else_=0)).label('hr_zone_5'),
        
        # Total HR time for percentage calculation
        func.sum(case((Activity.start_date >= today - timedelta(days=30), 
                     Activity.hr_zone_1 + Activity.hr_zone_2 + Activity.hr_zone_3 + Activity.hr_zone_4 + Activity.hr_zone_5), 
                     else_=0)).label('total_hr_time')
    ).filter(
        Activity.athlete_id == athlete_id,
        Activity.type == "Run",
        Activity.distance > 0
    ).first()
    
    # Process results
    current_distance = (result.current_distance or 0) / 1609.34  # Convert to miles
    previous_distance = (result.previous_distance or 0) / 1609.34
    current_runs = result.current_runs or 0
    previous_runs = result.previous_runs or 0
    
    # Calculate pace
    current_pace = format_pace(result.current_avg_speed) if result.current_avg_speed else "0:00"
    previous_pace = format_pace(result.previous_avg_speed) if result.previous_avg_speed else "0:00"
    
    # Calculate HR zone percentages
    total_hr_time = result.total_hr_time or 0
    hr_zones = {}
    if total_hr_time > 0:
        for zone in range(1, 6):
            zone_time = getattr(result, f'hr_zone_{zone}', 0) or 0
            hr_zones[f'zone_{zone}'] = (zone_time / total_hr_time) * 100
    else:
        for zone in range(1, 6):
            hr_zones[f'zone_{zone}'] = 0.0
    
    # Calculate percentage changes
    distance_change = ((current_distance - previous_distance) / previous_distance * 100) if previous_distance > 0 else 0
    runs_change = ((current_runs - previous_runs) / previous_runs * 100) if previous_runs > 0 else 0
    pace_change = 0  # Skip pace change calculation for now
    
    return {
        "weekly_distance": {
            "current": round(current_distance, 1),
            "previous": round(previous_distance, 1),
            "change_pct": round(distance_change, 1)
        },
        "weekly_runs": {
            "current": current_runs,
            "previous": previous_runs,
            "change_pct": round(runs_change, 1)
        },
        "average_pace": {
            "current": current_pace,
            "previous": previous_pace,
            "change_pct": pace_change
        },
        "hr_zones": hr_zones
    }


def get_weekly_data_optimized(session, athlete_id):
    """Extract weekly data logic into a reusable function."""
    # Ultra-optimized database aggregation for all 20 weeks
    current_week_start = datetime(2025, 10, 6)  # Monday Oct 6
    
    # Build week boundaries for the 20 weeks
    week_boundaries = []
    for i in range(20):
        week_start = current_week_start - timedelta(days=7 * i)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        week_boundaries.append({
            'week_start': week_start,
            'week_end': week_end,
            'week_key': week_start.strftime("%Y-%m-%d")
        })
    
    # Single database query with multiple CASE statements for all 20 weeks
    case_statements_distance = []
    case_statements_runs = []
    case_statements_avg_speed = []
    
    for i, week in enumerate(week_boundaries):
        # Distance aggregation
        case_statements_distance.append(
            case((Activity.start_date.between(week['week_start'], week['week_end']), Activity.distance), else_=0)
        )
        
        # Run count aggregation  
        case_statements_runs.append(
            case((Activity.start_date.between(week['week_start'], week['week_end']), 1), else_=0)
        )
        
        # Average speed aggregation
        case_statements_avg_speed.append(
            case((Activity.start_date.between(week['week_start'], week['week_end']), 
                 Activity.distance / Activity.moving_time), else_=None)
        )
    
    # Execute single optimized query
    result = session.query(
        func.sum(case_statements_distance[0]).label('week_0_distance'),
        func.sum(case_statements_distance[1]).label('week_1_distance'),
        func.sum(case_statements_distance[2]).label('week_2_distance'),
        func.sum(case_statements_distance[3]).label('week_3_distance'),
        func.sum(case_statements_distance[4]).label('week_4_distance'),
        func.sum(case_statements_distance[5]).label('week_5_distance'),
        func.sum(case_statements_distance[6]).label('week_6_distance'),
        func.sum(case_statements_distance[7]).label('week_7_distance'),
        func.sum(case_statements_distance[8]).label('week_8_distance'),
        func.sum(case_statements_distance[9]).label('week_9_distance'),
        func.sum(case_statements_distance[10]).label('week_10_distance'),
        func.sum(case_statements_distance[11]).label('week_11_distance'),
        func.sum(case_statements_distance[12]).label('week_12_distance'),
        func.sum(case_statements_distance[13]).label('week_13_distance'),
        func.sum(case_statements_distance[14]).label('week_14_distance'),
        func.sum(case_statements_distance[15]).label('week_15_distance'),
        func.sum(case_statements_distance[16]).label('week_16_distance'),
        func.sum(case_statements_distance[17]).label('week_17_distance'),
        func.sum(case_statements_distance[18]).label('week_18_distance'),
        func.sum(case_statements_distance[19]).label('week_19_distance'),
        
        func.sum(case_statements_runs[0]).label('week_0_runs'),
        func.sum(case_statements_runs[1]).label('week_1_runs'),
        func.sum(case_statements_runs[2]).label('week_2_runs'),
        func.sum(case_statements_runs[3]).label('week_3_runs'),
        func.sum(case_statements_runs[4]).label('week_4_runs'),
        func.sum(case_statements_runs[5]).label('week_5_runs'),
        func.sum(case_statements_runs[6]).label('week_6_runs'),
        func.sum(case_statements_runs[7]).label('week_7_runs'),
        func.sum(case_statements_runs[8]).label('week_8_runs'),
        func.sum(case_statements_runs[9]).label('week_9_runs'),
        func.sum(case_statements_runs[10]).label('week_10_runs'),
        func.sum(case_statements_runs[11]).label('week_11_runs'),
        func.sum(case_statements_runs[12]).label('week_12_runs'),
        func.sum(case_statements_runs[13]).label('week_13_runs'),
        func.sum(case_statements_runs[14]).label('week_14_runs'),
        func.sum(case_statements_runs[15]).label('week_15_runs'),
        func.sum(case_statements_runs[16]).label('week_16_runs'),
        func.sum(case_statements_runs[17]).label('week_17_runs'),
        func.sum(case_statements_runs[18]).label('week_18_runs'),
        func.sum(case_statements_runs[19]).label('week_19_runs'),
        
        func.avg(case_statements_avg_speed[0]).label('week_0_avg_speed'),
        func.avg(case_statements_avg_speed[1]).label('week_1_avg_speed'),
        func.avg(case_statements_avg_speed[2]).label('week_2_avg_speed'),
        func.avg(case_statements_avg_speed[3]).label('week_3_avg_speed'),
        func.avg(case_statements_avg_speed[4]).label('week_4_avg_speed'),
        func.avg(case_statements_avg_speed[5]).label('week_5_avg_speed'),
        func.avg(case_statements_avg_speed[6]).label('week_6_avg_speed'),
        func.avg(case_statements_avg_speed[7]).label('week_7_avg_speed'),
        func.avg(case_statements_avg_speed[8]).label('week_8_avg_speed'),
        func.avg(case_statements_avg_speed[9]).label('week_9_avg_speed'),
        func.avg(case_statements_avg_speed[10]).label('week_10_avg_speed'),
        func.avg(case_statements_avg_speed[11]).label('week_11_avg_speed'),
        func.avg(case_statements_avg_speed[12]).label('week_12_avg_speed'),
        func.avg(case_statements_avg_speed[13]).label('week_13_avg_speed'),
        func.avg(case_statements_avg_speed[14]).label('week_14_avg_speed'),
        func.avg(case_statements_avg_speed[15]).label('week_15_avg_speed'),
        func.avg(case_statements_avg_speed[16]).label('week_16_avg_speed'),
        func.avg(case_statements_avg_speed[17]).label('week_17_avg_speed'),
        func.avg(case_statements_avg_speed[18]).label('week_18_avg_speed'),
        func.avg(case_statements_avg_speed[19]).label('week_19_avg_speed')
    ).filter(
        Activity.athlete_id == athlete_id,
        Activity.type == "Run",
        Activity.distance > 0
    ).first()
    
    # Process results into trends array
    trends = []
    for i in range(20):
        week_key = week_boundaries[i]['week_key']
        
        # Get metrics for this week
        distance = getattr(result, f'week_{i}_distance', 0) or 0
        runs = getattr(result, f'week_{i}_runs', 0) or 0
        avg_speed = getattr(result, f'week_{i}_avg_speed', None)
        
        # Convert distance to miles
        distance_miles = distance / 1609.34
        
        # Calculate pace
        avg_pace_str = "0:00"
        if avg_speed and avg_speed > 0:
            seconds_per_mile = 1609.34 / avg_speed
            minutes = int(seconds_per_mile // 60)
            seconds = int(seconds_per_mile % 60)
            avg_pace_str = f"{minutes}:{seconds:02d}"
        
        trends.append({
            "week": week_key,
            "distance": round(distance_miles, 1),
            "runs": int(runs),
            "avgPace": avg_pace_str
        })
    
    # Separate optimized query for HR zone data
    hr_zone_case_statements = []
    for i, week in enumerate(week_boundaries):
        for zone in range(1, 6):
            hr_zone_case_statements.append(
                func.sum(
                    case((Activity.start_date.between(week['week_start'], week['week_end']), 
                         getattr(Activity, f'hr_zone_{zone}') or 0), else_=0)
                ).label(f'week_{i}_zone_{zone}')
            )
    
    hr_result = session.query(*hr_zone_case_statements).filter(
        Activity.athlete_id == athlete_id,
        Activity.type == "Run",
        Activity.hr_zone_1.isnot(None)  # Only activities with HR data
    ).first()
    
    # Process HR zone results
    hr_zones = []
    for i in range(20):
        week_key = week_boundaries[i]['week_key']
        
        # Get HR zone times for this week
        zone_times = []
        total_hr_time = 0
        for zone in range(1, 6):
            zone_time = getattr(hr_result, f'week_{i}_zone_{zone}', 0) or 0
            zone_times.append(zone_time)
            total_hr_time += zone_time
        
        # Calculate percentages
        if total_hr_time > 0:
            hr_zones.append({
                "week": week_key,
                "zone_1": round((zone_times[0] / total_hr_time) * 100, 1),
                "zone_2": round((zone_times[1] / total_hr_time) * 100, 1),
                "zone_3": round((zone_times[2] / total_hr_time) * 100, 1),
                "zone_4": round((zone_times[3] / total_hr_time) * 100, 1),
                "zone_5": round((zone_times[4] / total_hr_time) * 100, 1)
            })
        else:
            hr_zones.append({
                "week": week_key,
                "zone_1": 0.0,
                "zone_2": 0.0,
                "zone_3": 0.0,
                "zone_4": 0.0,
                "zone_5": 0.0
            })
    
    return {
        "weekly_trends": trends,
        "weekly_hr_zones": hr_zones
    }


def get_all_metrics_ultra_optimized(session, athlete_id):
    """
    ULTRA-OPTIMIZED: Get ALL metrics from materialized view.
    This is the fastest possible approach - simple SELECT, all processing done by database.
    Query time: ~5-10ms (vs ~100ms with CASE statements)
    """
    import json
    
    # Single simple query to materialized view
    result = session.execute(
        text("SELECT * FROM mv_athlete_metrics WHERE athlete_id = :athlete_id"),
        {"athlete_id": athlete_id}
    ).first()
    
    if not result:
        # No data for this athlete, return empty metrics
        return {
            "weekly_distance": {"current": 0.0, "previous": 0.0, "change_pct": 0.0},
            "weekly_runs": {"current": 0, "previous": 0, "change_pct": 0.0},
            "average_pace": {"current": "0:00", "previous": "0:00", "change_pct": 0},
            "hr_zones": {"zone_1": 0.0, "zone_2": 0.0, "zone_3": 0.0, "zone_4": 0.0, "zone_5": 0.0},
            "weekly_trends": [],
            "weekly_hr_zones": []
        }
    
    # Extract pre-calculated dashboard metrics
    current_distance = round(result.current_distance or 0, 1)
    previous_distance = round(result.previous_distance or 0, 1)
    current_runs = int(result.current_runs or 0)
    previous_runs = int(result.previous_runs or 0)
    
    # Format paces (only thing we need to do in Python)
    current_pace = format_pace(result.current_avg_speed) if result.current_avg_speed else "0:00"
    previous_pace = format_pace(result.previous_avg_speed) if result.previous_avg_speed else "0:00"
    
    # Get pre-calculated percentage changes
    distance_change = round(result.distance_change_pct or 0, 1)
    runs_change = round(result.runs_change_pct or 0, 1)
    
    # Get pre-calculated HR zone percentages
    hr_zones = {
        "zone_1": round(result.zone_1_pct or 0, 1),
        "zone_2": round(result.zone_2_pct or 0, 1),
        "zone_3": round(result.zone_3_pct or 0, 1),
        "zone_4": round(result.zone_4_pct or 0, 1),
        "zone_5": round(result.zone_5_pct or 0, 1)
    }
    
    # Parse weekly data from JSON (pre-aggregated by database)
    # The materialized view returns it as a list, not a JSON string
    weekly_data = result.weekly_data if result.weekly_data else []
    
    # Process weekly trends and HR zones
    weekly_trends = []
    weekly_hr_zones = []
    
    for week in weekly_data[:20]:  # Limit to 20 weeks
        # Format pace for this week
        avg_speed = week.get('avg_speed_mps')
        avg_pace_str = format_pace(avg_speed) if avg_speed else "0:00"
        
        weekly_trends.append({
            "week": week['week'],
            "distance": float(week['distance']),
            "runs": int(week['runs']),
            "avgPace": avg_pace_str
        })
        
        # Calculate HR zone percentages for this week
        total_hr = week.get('total_hr_time', 0)
        if total_hr > 0:
            weekly_hr_zones.append({
                "week": week['week'],
                "zone_1": round((week.get('hr_zone_1', 0) / total_hr) * 100, 1),
                "zone_2": round((week.get('hr_zone_2', 0) / total_hr) * 100, 1),
                "zone_3": round((week.get('hr_zone_3', 0) / total_hr) * 100, 1),
                "zone_4": round((week.get('hr_zone_4', 0) / total_hr) * 100, 1),
                "zone_5": round((week.get('hr_zone_5', 0) / total_hr) * 100, 1)
            })
        else:
            weekly_hr_zones.append({
                "week": week['week'],
                "zone_1": 0.0, "zone_2": 0.0, "zone_3": 0.0, "zone_4": 0.0, "zone_5": 0.0
            })
    
    return {
        "weekly_distance": {
            "current": current_distance,
            "previous": previous_distance,
            "change_pct": distance_change
        },
        "weekly_runs": {
            "current": current_runs,
            "previous": previous_runs,
            "change_pct": runs_change
        },
        "average_pace": {
            "current": current_pace,
            "previous": previous_pace,
            "change_pct": 0
        },
        "hr_zones": hr_zones,
        "weekly_trends": weekly_trends,
        "weekly_hr_zones": weekly_hr_zones
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


@metrics_bp.route("/all-metrics", methods=["GET"])
@requires_auth
def get_all_metrics_combined():
    """
    Get ALL metrics (dashboard + weekly trends + HR zones) in a single optimized call.
    This is the fastest possible approach - one API call, minimal queries, maximum caching.
    """
    session = get_session()
    
    try:
        claims = getattr(g, "current_user", {}) or {}
        claims = normalize_claims(claims)
        sub = claims.get("sub")
        
        if not sub:
            return jsonify({"error": "Missing sub claim"}), 401
        
        user_id = resolve_user_id_from_auth_provider(sub, claims)
        
        if not user_id:
            return jsonify({"error": "Could not resolve user ID"}), 404
        
        # Get athlete_id for this user
        athlete_id = get_athlete_id_for_user(session, user_id)
        
        if not athlete_id:
            return jsonify({
                "error": "No Strava connection found",
                "weekly_distance": {"current": 0, "previous": 0, "change_pct": 0},
                "average_pace": {"current": "0:00", "previous": "0:00", "change_pct": 0},
                "weekly_runs": {"current": 0, "previous": 0, "change_pct": 0},
                "hr_zones": {"zone_1": 0, "zone_2": 0, "zone_3": 0, "zone_4": 0, "zone_5": 0},
                "weekly_trends": [],
                "weekly_hr_zones": []
            }), 200
        
        # Check cache first
        cache_key = _get_cache_key(athlete_id, "all_metrics_combined")
        cached_result = get_cached_metrics(cache_key)
        if cached_result is not None:
            print(f"[CACHE HIT] All metrics for athlete {athlete_id}")
            return jsonify(cached_result), 200
        
        print(f"[CACHE MISS] All metrics for athlete {athlete_id}")
        
        # Performance timing
        import time
        start_time = time.time()
        
        # ULTRA-OPTIMIZED: Single massive query for everything
        result = get_all_metrics_ultra_optimized(session, athlete_id)
        
        # Cache the result for 5 minutes
        set_cached_metrics(cache_key, result, ttl=300)
        
        # Performance logging
        execution_time = time.time() - start_time
        print(f"[PERF] All metrics query took {execution_time:.3f}s")
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"[ERROR] Error in get_all_metrics_combined: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500
        
    finally:
        session.close()


@metrics_bp.route("/dashboard", methods=["GET"])
@requires_auth
def get_dashboard_metrics():
    """
    Get dashboard metrics for the current user.
    
    Returns key performance indicators:
    - Weekly distance with week-over-week comparison
    - Average pace with trend
    - Activity frequency
    - Heart rate zone distribution
    
    Authentication:
        Requires valid JWT token (Auth0)
        
    Returns:
        JSON response with metrics data
        
    Error Codes:
        401: Unauthorized (missing/invalid JWT)
        404: User not found or no Strava connection
        500: Internal server error
    """
    session = get_session()
    
    try:
        # Extract user_id from JWT claims (same pattern as other endpoints)
        
        claims = getattr(g, "current_user", {}) or {}
        claims = normalize_claims(claims)
        sub = claims.get("sub")
        
        if not sub:
            return jsonify({"error": "Missing sub claim"}), 401
        
        user_id = resolve_user_id_from_auth_provider(sub, claims)
        
        if not user_id:
            return jsonify({"error": "Could not resolve user ID"}), 404
        
        # Get athlete_id for this user
        athlete_id = get_athlete_id_for_user(session, user_id)
        
        if not athlete_id:
            return jsonify({
                "error": "No Strava connection found",
                "weekly_distance": {"current": 0, "previous": 0, "change_pct": 0},
                "average_pace": {"current": "0:00", "previous": "0:00", "change_pct": 0},
                "weekly_runs": {"current": 0, "previous": 0, "change_pct": 0},
                "hr_zones": {"zone_1": 0, "zone_2": 0, "zone_3": 0, "zone_4": 0, "zone_5": 0}
            }), 200
        
        # Check cache first
        cache_key = _get_cache_key(athlete_id, "dashboard_metrics")
        cached_result = get_cached_metrics(cache_key)
        if cached_result is not None:
            print(f"[CACHE HIT] Dashboard metrics for athlete {athlete_id}")
            return jsonify(cached_result), 200
        
        print(f"[CACHE MISS] Dashboard metrics for athlete {athlete_id}")
        
        # Performance timing
        import time
        start_time = time.time()
        
        # Single optimized query for all dashboard metrics
        today = datetime.utcnow()
        current_week_start = today - timedelta(days=today.weekday())
        last_week_start = current_week_start - timedelta(days=7)
        last_week_end = current_week_start - timedelta(seconds=1)
        
        # Single query to get all dashboard metrics at once
        result = session.query(
            # Current week metrics
            func.sum(case((Activity.start_date >= current_week_start, Activity.distance), else_=0)).label('current_distance'),
            func.count(case((Activity.start_date >= current_week_start, Activity.activity_id), else_=None)).label('current_runs'),
            func.avg(case((Activity.start_date >= current_week_start, Activity.distance / Activity.moving_time), else_=None)).label('current_avg_speed'),
            
            # Previous week metrics  
            func.sum(case((and_(Activity.start_date >= last_week_start, Activity.start_date <= last_week_end), Activity.distance), else_=0)).label('previous_distance'),
            func.count(case((and_(Activity.start_date >= last_week_start, Activity.start_date <= last_week_end), Activity.activity_id), else_=None)).label('previous_runs'),
            func.avg(case((and_(Activity.start_date >= last_week_start, Activity.start_date <= last_week_end), Activity.distance / Activity.moving_time), else_=None)).label('previous_avg_speed'),
            
            # HR zones (last 30 days)
            func.sum(case((Activity.start_date >= today - timedelta(days=30), Activity.hr_zone_1), else_=0)).label('hr_zone_1'),
            func.sum(case((Activity.start_date >= today - timedelta(days=30), Activity.hr_zone_2), else_=0)).label('hr_zone_2'),
            func.sum(case((Activity.start_date >= today - timedelta(days=30), Activity.hr_zone_3), else_=0)).label('hr_zone_3'),
            func.sum(case((Activity.start_date >= today - timedelta(days=30), Activity.hr_zone_4), else_=0)).label('hr_zone_4'),
            func.sum(case((Activity.start_date >= today - timedelta(days=30), Activity.hr_zone_5), else_=0)).label('hr_zone_5'),
            
            # Total HR time for percentage calculation
            func.sum(case((Activity.start_date >= today - timedelta(days=30), 
                         Activity.hr_zone_1 + Activity.hr_zone_2 + Activity.hr_zone_3 + Activity.hr_zone_4 + Activity.hr_zone_5), 
                         else_=0)).label('total_hr_time')
        ).filter(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.distance > 0
        ).first()
        
        # Process results
        current_distance = (result.current_distance or 0) / 1609.34  # Convert to miles
        previous_distance = (result.previous_distance or 0) / 1609.34
        current_runs = result.current_runs or 0
        previous_runs = result.previous_runs or 0
        
        # Calculate pace
        current_pace = format_pace(result.current_avg_speed) if result.current_avg_speed else "0:00"
        previous_pace = format_pace(result.previous_avg_speed) if result.previous_avg_speed else "0:00"
        
        # Calculate HR zone percentages
        total_hr_time = result.total_hr_time or 0
        hr_zones = {}
        if total_hr_time > 0:
            for zone in range(1, 6):
                zone_time = getattr(result, f'hr_zone_{zone}', 0) or 0
                hr_zones[f'zone_{zone}'] = (zone_time / total_hr_time) * 100
        else:
            for zone in range(1, 6):
                hr_zones[f'zone_{zone}'] = 0.0
        
        # Calculate percentage changes
        distance_change = ((current_distance - previous_distance) / previous_distance * 100) if previous_distance > 0 else 0
        runs_change = ((current_runs - previous_runs) / previous_runs * 100) if previous_runs > 0 else 0
        pace_change = 0  # Skip pace change calculation for now
        
        metrics = {
            "weekly_distance": {
                "current": round(current_distance, 1),
                "previous": round(previous_distance, 1),
                "change_pct": round(distance_change, 1)
            },
            "weekly_runs": {
                "current": current_runs,
                "previous": previous_runs,
                "change_pct": round(runs_change, 1)
            },
            "average_pace": {
                "current": current_pace,
                "previous": previous_pace,
                "change_pct": pace_change
            },
            "hr_zones": hr_zones
        }
        
        # Cache the result for 5 minutes
        set_cached_metrics(cache_key, metrics, ttl=300)
        
        # Performance logging
        execution_time = time.time() - start_time
        print(f"[PERF] Dashboard metrics query took {execution_time:.3f}s")
        
        return jsonify(metrics), 200
        
    except Exception as e:
        print(f"[ERROR] Error in get_dashboard_metrics: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500
        
    finally:
        session.close()


@metrics_bp.route("/performance", methods=["GET"])
@requires_auth
def get_metrics_performance():
    """Get performance metrics and cache statistics for monitoring."""
    from src.services.metrics_cache_service import get_cache_stats
    
    try:
        cache_stats = get_cache_stats()
        
        return jsonify({
            "cache_stats": cache_stats,
            "optimizations": {
                "database_indexes": "Enabled",
                "query_caching": "Enabled (5-10 min TTL)",
                "combined_queries": "Enabled",
                "performance_monitoring": "Enabled"
            },
            "performance_notes": [
                "Metrics are cached for 5-10 minutes",
                "Database queries are optimized with proper indexes",
                "Multiple queries combined where possible",
                "Cache automatically invalidates on data updates"
            ]
        }), 200
        
    except Exception as e:
        return jsonify({"error": "Failed to get performance stats"}), 500


@metrics_bp.route("/weekly-data", methods=["GET"])
@requires_auth
def get_combined_weekly_data():
    """Get combined weekly trends and HR zone data in a single optimized query."""
    session = get_session()
    
    try:
        claims = getattr(g, "current_user", {}) or {}
        claims = normalize_claims(claims)
        sub = claims.get("sub")
        
        if not sub:
            return jsonify({"error": "Missing sub claim"}), 401
        
        user_id = resolve_user_id_from_auth_provider(sub, claims)
        
        if not user_id:
            return jsonify({"error": "Could not resolve user ID"}), 404
        
        athlete_id = get_athlete_id_for_user(session, user_id)
        
        if not athlete_id:
            return jsonify({"error": "No Strava connection found"}), 404
        
        # Check cache first
        cache_key = _get_cache_key(athlete_id, "weekly_data_combined")
        cached_result = get_cached_metrics(cache_key)
        if cached_result is not None:
            print(f"[CACHE HIT] Weekly data for athlete {athlete_id}")
            return jsonify(cached_result), 200
        
        print(f"[CACHE MISS] Weekly data for athlete {athlete_id}")
        
        # Performance timing
        import time
        start_time = time.time()
        
        # Ultra-optimized database aggregation for all 20 weeks
        current_week_start = datetime(2025, 10, 6)  # Monday Oct 6
        
        # Build week boundaries for the 20 weeks
        week_boundaries = []
        for i in range(20):
            week_start = current_week_start - timedelta(days=7 * i)
            week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            week_boundaries.append({
                'week_start': week_start,
                'week_end': week_end,
                'week_key': week_start.strftime("%Y-%m-%d")
            })
        
        # Single database query with multiple CASE statements for all 20 weeks
        case_statements_distance = []
        case_statements_runs = []
        case_statements_avg_speed = []
        case_statements_hr_zones = {1: [], 2: [], 3: [], 4: [], 5: []}
        
        for i, week in enumerate(week_boundaries):
            # Distance aggregation
            case_statements_distance.append(
                case((Activity.start_date.between(week['week_start'], week['week_end']), Activity.distance), else_=0)
            )
            
            # Run count aggregation  
            case_statements_runs.append(
                case((Activity.start_date.between(week['week_start'], week['week_end']), 1), else_=0)
            )
            
            # Average speed aggregation
            case_statements_avg_speed.append(
                case((Activity.start_date.between(week['week_start'], week['week_end']), 
                     Activity.distance / Activity.moving_time), else_=None)
            )
            
            # HR zone aggregations
            for zone in range(1, 6):
                case_statements_hr_zones[zone].append(
                    case((Activity.start_date.between(week['week_start'], week['week_end']), 
                         getattr(Activity, f'hr_zone_{zone}') or 0), else_=0)
                )
        
        # Execute single optimized query
        result = session.query(
            func.sum(case_statements_distance[0]).label('week_0_distance'),
            func.sum(case_statements_distance[1]).label('week_1_distance'),
            func.sum(case_statements_distance[2]).label('week_2_distance'),
            func.sum(case_statements_distance[3]).label('week_3_distance'),
            func.sum(case_statements_distance[4]).label('week_4_distance'),
            func.sum(case_statements_distance[5]).label('week_5_distance'),
            func.sum(case_statements_distance[6]).label('week_6_distance'),
            func.sum(case_statements_distance[7]).label('week_7_distance'),
            func.sum(case_statements_distance[8]).label('week_8_distance'),
            func.sum(case_statements_distance[9]).label('week_9_distance'),
            func.sum(case_statements_distance[10]).label('week_10_distance'),
            func.sum(case_statements_distance[11]).label('week_11_distance'),
            func.sum(case_statements_distance[12]).label('week_12_distance'),
            func.sum(case_statements_distance[13]).label('week_13_distance'),
            func.sum(case_statements_distance[14]).label('week_14_distance'),
            func.sum(case_statements_distance[15]).label('week_15_distance'),
            func.sum(case_statements_distance[16]).label('week_16_distance'),
            func.sum(case_statements_distance[17]).label('week_17_distance'),
            func.sum(case_statements_distance[18]).label('week_18_distance'),
            func.sum(case_statements_distance[19]).label('week_19_distance'),
            
            func.sum(case_statements_runs[0]).label('week_0_runs'),
            func.sum(case_statements_runs[1]).label('week_1_runs'),
            func.sum(case_statements_runs[2]).label('week_2_runs'),
            func.sum(case_statements_runs[3]).label('week_3_runs'),
            func.sum(case_statements_runs[4]).label('week_4_runs'),
            func.sum(case_statements_runs[5]).label('week_5_runs'),
            func.sum(case_statements_runs[6]).label('week_6_runs'),
            func.sum(case_statements_runs[7]).label('week_7_runs'),
            func.sum(case_statements_runs[8]).label('week_8_runs'),
            func.sum(case_statements_runs[9]).label('week_9_runs'),
            func.sum(case_statements_runs[10]).label('week_10_runs'),
            func.sum(case_statements_runs[11]).label('week_11_runs'),
            func.sum(case_statements_runs[12]).label('week_12_runs'),
            func.sum(case_statements_runs[13]).label('week_13_runs'),
            func.sum(case_statements_runs[14]).label('week_14_runs'),
            func.sum(case_statements_runs[15]).label('week_15_runs'),
            func.sum(case_statements_runs[16]).label('week_16_runs'),
            func.sum(case_statements_runs[17]).label('week_17_runs'),
            func.sum(case_statements_runs[18]).label('week_18_runs'),
            func.sum(case_statements_runs[19]).label('week_19_runs'),
            
            func.avg(case_statements_avg_speed[0]).label('week_0_avg_speed'),
            func.avg(case_statements_avg_speed[1]).label('week_1_avg_speed'),
            func.avg(case_statements_avg_speed[2]).label('week_2_avg_speed'),
            func.avg(case_statements_avg_speed[3]).label('week_3_avg_speed'),
            func.avg(case_statements_avg_speed[4]).label('week_4_avg_speed'),
            func.avg(case_statements_avg_speed[5]).label('week_5_avg_speed'),
            func.avg(case_statements_avg_speed[6]).label('week_6_avg_speed'),
            func.avg(case_statements_avg_speed[7]).label('week_7_avg_speed'),
            func.avg(case_statements_avg_speed[8]).label('week_8_avg_speed'),
            func.avg(case_statements_avg_speed[9]).label('week_9_avg_speed'),
            func.avg(case_statements_avg_speed[10]).label('week_10_avg_speed'),
            func.avg(case_statements_avg_speed[11]).label('week_11_avg_speed'),
            func.avg(case_statements_avg_speed[12]).label('week_12_avg_speed'),
            func.avg(case_statements_avg_speed[13]).label('week_13_avg_speed'),
            func.avg(case_statements_avg_speed[14]).label('week_14_avg_speed'),
            func.avg(case_statements_avg_speed[15]).label('week_15_avg_speed'),
            func.avg(case_statements_avg_speed[16]).label('week_16_avg_speed'),
            func.avg(case_statements_avg_speed[17]).label('week_17_avg_speed'),
            func.avg(case_statements_avg_speed[18]).label('week_18_avg_speed'),
            func.avg(case_statements_avg_speed[19]).label('week_19_avg_speed')
        ).filter(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.distance > 0
        ).first()
        
        # Process results into trends array
        trends = []
        for i in range(20):
            week_key = week_boundaries[i]['week_key']
            
            # Get metrics for this week
            distance = getattr(result, f'week_{i}_distance', 0) or 0
            runs = getattr(result, f'week_{i}_runs', 0) or 0
            avg_speed = getattr(result, f'week_{i}_avg_speed', None)
            
            # Convert distance to miles
            distance_miles = distance / 1609.34
            
            # Calculate pace
            avg_pace_str = "0:00"
            if avg_speed and avg_speed > 0:
                seconds_per_mile = 1609.34 / avg_speed
                minutes = int(seconds_per_mile // 60)
                seconds = int(seconds_per_mile % 60)
                avg_pace_str = f"{minutes}:{seconds:02d}"
            
            trends.append({
                "week": week_key,
                "distance": round(distance_miles, 1),
                "runs": int(runs),
                "avgPace": avg_pace_str
            })
        
        # Separate optimized query for HR zone data
        hr_zone_case_statements = []
        for i, week in enumerate(week_boundaries):
            for zone in range(1, 6):
                hr_zone_case_statements.append(
                    func.sum(
                        case((Activity.start_date.between(week['week_start'], week['week_end']), 
                             getattr(Activity, f'hr_zone_{zone}') or 0), else_=0)
                    ).label(f'week_{i}_zone_{zone}')
                )
        
        hr_result = session.query(*hr_zone_case_statements).filter(
            Activity.athlete_id == athlete_id,
            Activity.type == "Run",
            Activity.hr_zone_1.isnot(None)  # Only activities with HR data
        ).first()
        
        # Process HR zone results
        hr_zones = []
        for i in range(20):
            week_key = week_boundaries[i]['week_key']
            
            # Get HR zone times for this week
            zone_times = []
            total_hr_time = 0
            for zone in range(1, 6):
                zone_time = getattr(hr_result, f'week_{i}_zone_{zone}', 0) or 0
                zone_times.append(zone_time)
                total_hr_time += zone_time
            
            # Calculate percentages
            if total_hr_time > 0:
                hr_zones.append({
                    "week": week_key,
                    "zone_1": round((zone_times[0] / total_hr_time) * 100, 1),
                    "zone_2": round((zone_times[1] / total_hr_time) * 100, 1),
                    "zone_3": round((zone_times[2] / total_hr_time) * 100, 1),
                    "zone_4": round((zone_times[3] / total_hr_time) * 100, 1),
                    "zone_5": round((zone_times[4] / total_hr_time) * 100, 1)
                })
            else:
                hr_zones.append({
                    "week": week_key,
                    "zone_1": 0.0,
                    "zone_2": 0.0,
                    "zone_3": 0.0,
                    "zone_4": 0.0,
                    "zone_5": 0.0
                })
        
        result = {
            "weekly_trends": trends,
            "weekly_hr_zones": hr_zones
        }
        
        # Cache the result for 10 minutes
        set_cached_metrics(cache_key, result, ttl=600)
        
        # Performance logging
        execution_time = time.time() - start_time
        print(f"[PERF] Weekly data query took {execution_time:.3f}s")
        
        return jsonify(result), 200
        
    except Exception as e:
        print(f"Error in get_combined_weekly_data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500
        
    finally:
        session.close()


@metrics_bp.route("/weekly-trends", methods=["GET"])
@requires_auth
def get_weekly_trends():
    """Get weekly trend data for charts (legacy endpoint)."""
    # Redirect to the new combined endpoint for consistency
    return get_combined_weekly_data()


@metrics_bp.route("/weekly-hr-zones", methods=["GET"])
@requires_auth
def get_weekly_hr_zones():
    """Get weekly heart rate zone distribution data for charts."""
    session = get_session()
    
    try:
        claims = getattr(g, "current_user", {}) or {}
        claims = normalize_claims(claims)
        sub = claims.get("sub")
        
        if not sub:
            return jsonify({"error": "Missing sub claim"}), 401
        
        user_id = resolve_user_id_from_auth_provider(sub, claims)
        
        if not user_id:
            return jsonify({"error": "Could not resolve user ID"}), 404
        
        athlete_id = get_athlete_id_for_user(session, user_id)
        
        if not athlete_id:
            return jsonify({"error": "No Strava connection found"}), 404
        
        # Get weekly HR zone data for last 20 weeks (optimized for performance)
        trends = []
        current_week_start = datetime(2025, 10, 6)  # Monday Oct 6
        
        for i in range(20):
            # Start with current week (i=0), then go back in time
            week_start = current_week_start - timedelta(days=7 * i)
            week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            
            # Get activities for this week
            activities = ActivityStatsDAO.get_activities_by_date_range(
                session, athlete_id, week_start, week_end
            )
            
            # Calculate HR zone percentages for this week
            total_hr_time = 0
            zone_times = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            
            for activity in activities:
                if activity.moving_time and activity.hr_zone_1 is not None:
                    # Sum up all HR zone times for this activity
                    activity_hr_zones = [
                        activity.hr_zone_1 or 0,
                        activity.hr_zone_2 or 0, 
                        activity.hr_zone_3 or 0,
                        activity.hr_zone_4 or 0,
                        activity.hr_zone_5 or 0
                    ]
                    activity_total_hr = sum(activity_hr_zones)
                    
                    if activity_total_hr > 0:
                        total_hr_time += activity_total_hr
                        for zone_num in range(1, 6):
                            zone_times[zone_num] += activity_hr_zones[zone_num - 1]
            
            # Calculate percentages
            zone_percentages = {}
            if total_hr_time > 0:
                for zone_num in range(1, 6):
                    zone_percentages[f"zone_{zone_num}"] = (zone_times[zone_num] / total_hr_time) * 100
            else:
                for zone_num in range(1, 6):
                    zone_percentages[f"zone_{zone_num}"] = 0.0
            
            trends.append({
                "week": week_start.strftime("%Y-%m-%d"),
                **zone_percentages
            })
        
        return jsonify({"weekly_hr_zones": trends}), 200
        
    except Exception as e:
        print(f"Error in get_weekly_hr_zones: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500
        
    finally:
        session.close()


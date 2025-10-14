"""
GYR (Green/Yellow/Red) Metrics Routes Module
============================================

This module provides API endpoints for retrieving GYR (Green/Yellow/Red)
training metric scores. Leverages existing metrics infrastructure for performance.

Endpoints:
----------
GET /api/gyr-metrics/scores
    Returns GYR scores for all training metrics:
    - Total Runs (vs plan)
    - Weekly Pace (vs rolling average)
    - Weekly HR Zones (80/20 adherence)

    Query params:
    - weeks: Number of weeks to return (default: 8)

    Response format:
    {
        "totalRuns": {
            "historicalScores": [
                { "value": 85, "date": "2024-06-11", "status": "yellow" },
                ...
            ],
            "criteria": {
                "green": "90–110% of plan",
                "yellow": "70–90% or 110–130%",
                "red": "<70% or >130%"
            }
        },
        "weeklyPace": { /* similar structure */ },
        "weeklyHRZones": { /* similar structure */ }
    }

Dependencies:
------------
- GYRMetricsService: Business logic for GYR calculations
- metrics infrastructure: Leverages materialized views for performance
- requires_auth: JWT authentication decorator

Performance:
-----------
- Leverages existing ultra-fast metrics infrastructure
- Query time: ~10-15ms (reuses cached metrics data)
- No additional database load

Author: SmartCoach Development Team
Last Updated: October 14, 2025
"""

from flask import Blueprint, jsonify, g, request
from src.utils.auth0_jwt import requires_auth
from src.utils.logger import get_logger

logger = get_logger(__name__)

gyr_metrics_bp = Blueprint("gyr_metrics", __name__)


def get_athlete_id_for_user(session, user_id) -> int | None:
    """
    Helper function to get athlete_id from user_id.

    Args:
        session: SQLAlchemy session
        user_id: Internal user ID (UUID string or UUID object)

    Returns:
        athlete_id (int) or None if not found
    """
    from sqlalchemy import text

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


@gyr_metrics_bp.route("/scores", methods=["GET"])
@requires_auth
def get_gyr_scores():
    """
    Get GYR (Green/Yellow/Red) scores for all training metrics.

    Query Parameters:
        weeks (int): Number of weeks to return (default: 8, max: 20)

    Returns:
        JSON response with GYR scores for each metric type

    Error Codes:
        401: Unauthorized (missing/invalid JWT)
        404: User not found or no Strava connection
        500: Internal server error
    """
    # Import here to avoid circular import issues at module level
    from src.db.db_session import get_session
    from src.services.gyr_metrics_service import GYRMetricsService
    from src.db.dao.user_identity_dao import resolve_user_id_from_auth_provider
    from src.utils.normalize_claims import normalize_claims

    session = get_session()

    try:
        # Get authenticated user
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
            return (
                jsonify(
                    {
                        "error": "No Strava connection found",
                        "totalRuns": {"historicalScores": [], "criteria": {}},
                        "weeklyPace": {"historicalScores": [], "criteria": {}},
                        "weeklyHRZones": {"historicalScores": [], "criteria": {}},
                    }
                ),
                200,
            )

        # Get weeks parameter (default: 8, max: 20)
        weeks = request.args.get("weeks", default=8, type=int)
        weeks = min(max(1, weeks), 20)  # Clamp between 1 and 20

        logger.info(
            f"🎯 Calculating GYR scores for athlete {athlete_id}, user {user_id}, weeks: {weeks}"
        )

        # Calculate GYR scores using service
        import time

        start_time = time.time()

        gyr_scores = GYRMetricsService.calculate_gyr_scores(
            session=session, athlete_id=athlete_id, user_id=str(user_id), weeks=weeks
        )

        execution_time = time.time() - start_time
        logger.info(f"⏱️ GYR scores calculated in {execution_time:.3f}s")

        return jsonify(gyr_scores), 200

    except Exception as e:
        logger.error(f"❌ Error calculating GYR scores: {str(e)}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

    finally:
        session.close()

"""
Metrics Helper Service

Shared service for calculating weekly mileage and longest run from materialized view.
Used by both the metrics API endpoint and plan generation to ensure consistency.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.utils.date_helpers import get_current_week_start

logger = logging.getLogger(__name__)


def get_athlete_id_for_user(session: Session, user_id: str) -> Optional[int]:
    """
    Helper function to get athlete_id from user_id.

    Args:
        session: SQLAlchemy session
        user_id: Internal user ID (UUID string or UUID object)

    Returns:
        athlete_id (int) or None if not found
    """
    result = session.execute(
        text(
            """
            SELECT athlete_id
            FROM public.user_athletes
            WHERE user_id = :uid
            LIMIT 1
            """
        ),
        {"uid": user_id},
    ).fetchone()

    return result.athlete_id if result else None


def calculate_weekly_mileage_from_trends(
    weekly_trends: list[Dict[str, Any]], weeks: int = 4
) -> float:
    """
    Calculate average weekly mileage from weekly trends.
    Matches the frontend calculation exactly.

    Args:
        weekly_trends: List of weekly trend dictionaries from materialized view
        weeks: Number of weeks to average (default: 4)

    Returns:
        Average weekly mileage in miles
    """
    if not weekly_trends:
        return 0.0

    # Get last N weeks (already filtered to exclude current week by metrics endpoint)
    last_weeks = weekly_trends[:weeks]

    if not last_weeks:
        return 0.0

    # Calculate average (same as frontend)
    total = sum(week.get("distance", 0) or 0 for week in last_weeks)
    return round(total / len(last_weeks), 1)


def calculate_longest_run_from_runs(
    longest_runs: list[Dict[str, Any]], weeks: int = 4
) -> float:
    """
    Calculate longest run from longest runs data.
    Matches the frontend calculation exactly.

    Args:
        longest_runs: List of longest run dictionaries from materialized view
        weeks: Number of weeks to look at (default: 4)

    Returns:
        Longest run distance in miles
    """
    if not longest_runs:
        return 0.0

    # Get last N weeks (already filtered to exclude current week by metrics endpoint)
    last_runs = longest_runs[:weeks]

    if not last_runs:
        return 0.0

    # Get max distance (same as frontend)
    max_distance = max([run.get("distance", 0) or 0 for run in last_runs], default=0.0)
    return round(max_distance, 1)


def get_weekly_fitness_from_materialized_view(
    session: Session, user_id: str, athlete_id: Optional[int] = None
) -> Tuple[float, float]:
    """
    Get weekly mileage and longest run from materialized view.
    REUSES the same function that the metrics endpoint uses.

    This ensures consistency between what the UI shows and what plan generation uses.

    Args:
        session: SQLAlchemy database session
        user_id: Internal user ID (UUID string)
        athlete_id: Optional athlete_id (will be looked up if not provided)

    Returns:
        Tuple of (weekly_mileage, longest_run) in miles
    """
    try:
        # Import here to avoid circular imports
        from src.routes.metrics_routes import get_all_metrics_ultra_optimized

        # Get athlete_id if not provided
        if not athlete_id:
            athlete_id = get_athlete_id_for_user(session, user_id)
            if not athlete_id:
                logger.warning(f"No athlete_id found for user {user_id}")
                return 0.0, 0.0

        # REUSE the existing metrics function - same data source, same calculation
        metrics_data = get_all_metrics_ultra_optimized(
            session=session, athlete_id=athlete_id, user_id=user_id, weeks=20
        )

        if not metrics_data:
            logger.warning(f"No metrics data found for athlete {athlete_id}")
            return 0.0, 0.0

        # Extract weekly_trends and longest_runs (already filtered by get_all_metrics_ultra_optimized)
        weekly_trends = metrics_data.get("weekly_trends", [])
        longest_runs = metrics_data.get("longest_runs", [])

        # Calculate using the same helper functions (same calculation as frontend)
        weekly_mileage = calculate_weekly_mileage_from_trends(weekly_trends, weeks=4)
        longest_run = calculate_longest_run_from_runs(longest_runs, weeks=4)

        logger.info(
            f"📊 Fitness from materialized view: {weekly_mileage:.1f} mpw, "
            f"{longest_run:.1f}-mile long run (from last 4 complete weeks, using same source as metrics endpoint)"
        )

        return weekly_mileage, longest_run

    except Exception as e:
        logger.error(
            f"Error fetching fitness from materialized view: {e}", exc_info=True
        )
        return 0.0, 0.0

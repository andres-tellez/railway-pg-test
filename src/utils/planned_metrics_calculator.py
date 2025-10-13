"""
Planned Metrics Calculator
==========================

This module calculates planned miles from training plans for display in metrics dashboard.
Used to show planned weekly targets instead of just actual completed miles.

Author: SmartCoach Development Team
Last Updated: October 13, 2025
"""

from datetime import datetime, timedelta
from sqlalchemy import text
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_planned_miles_for_current_week(session, user_id):
    """
    Get planned miles for the current week (Monday to Sunday) from user's training plan.

    Args:
        session: SQLAlchemy database session
        user_id: User ID to get plan for

    Returns:
        float: Total planned miles for current week, or 0 if no plan found
    """
    try:
        # Calculate current week start (Monday) and end (Sunday)
        today = datetime.now().date()
        days_since_monday = today.weekday()  # Monday = 0
        week_start = today - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)  # Sunday

        logger.info(f"📅 Calculating planned miles for week {week_start} to {week_end}")

        # Get the user's most recent plan
        plan_result = session.execute(
            text(
                """
            SELECT id FROM plans
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 1
        """
            ),
            {"user_id": str(user_id)},
        ).first()

        if not plan_result:
            logger.info("📋 No training plan found for user")
            return 0.0

        plan_id = plan_result[0]

        # Get planned workouts for current week
        workouts_result = session.execute(
            text(
                """
            SELECT miles
            FROM plan_workouts
            WHERE plan_id = :plan_id
            AND date >= :week_start
            AND date <= :week_end
            ORDER BY date
        """
            ),
            {"plan_id": plan_id, "week_start": week_start, "week_end": week_end},
        ).fetchall()

        total_planned_miles = sum(workout[0] for workout in workouts_result)

        logger.info(
            f"📊 Found {len(workouts_result)} planned workouts totaling {total_planned_miles} miles"
        )

        return float(total_planned_miles)

    except Exception as e:
        logger.error(f"❌ Error calculating planned miles: {e}")
        return 0.0


def get_planned_miles_for_week(session, user_id, target_date):
    """
    Get planned miles for a specific week containing the target date.

    Args:
        session: SQLAlchemy database session
        user_id: User ID to get plan for
        target_date: Date to get week for (datetime.date object)

    Returns:
        float: Total planned miles for that week, or 0 if no plan found
    """
    try:
        # Calculate week start (Monday) and end (Sunday) for target date
        days_since_monday = target_date.weekday()  # Monday = 0
        week_start = target_date - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)  # Sunday

        logger.info(f"📅 Calculating planned miles for week {week_start} to {week_end}")

        # Get the user's most recent plan
        plan_result = session.execute(
            text(
                """
            SELECT id FROM plans
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 1
        """
            ),
            {"user_id": str(user_id)},
        ).first()

        if not plan_result:
            return 0.0

        plan_id = plan_result[0]

        # Get planned workouts for the week
        workouts_result = session.execute(
            text(
                """
            SELECT miles
            FROM plan_workouts
            WHERE plan_id = :plan_id
            AND date >= :week_start
            AND date <= :week_end
            ORDER BY date
        """
            ),
            {"plan_id": plan_id, "week_start": week_start, "week_end": week_end},
        ).fetchall()

        total_planned_miles = sum(workout[0] for workout in workouts_result)

        return float(total_planned_miles)

    except Exception as e:
        logger.error(f"❌ Error calculating planned miles for {target_date}: {e}")
        return 0.0


def get_weekly_planned_miles_history(session, user_id, weeks=20):
    """
    Get planned miles for the last N weeks for trend analysis.

    Args:
        session: SQLAlchemy database session
        user_id: User ID to get plan for
        weeks: Number of weeks to look back

    Returns:
        list: List of weekly planned miles data
    """
    try:
        # Calculate start date (N weeks ago)
        today = datetime.now().date()
        days_since_monday = today.weekday()
        current_week_start = today - timedelta(days=days_since_monday)

        weekly_data = []

        # Get planned miles for each week going back
        for i in range(weeks):
            week_start = current_week_start - timedelta(weeks=i)
            week_end = week_start + timedelta(days=6)

            planned_miles = get_planned_miles_for_week(session, user_id, week_start)

            weekly_data.append(
                {
                    "week": week_start.isoformat(),
                    "planned_miles": planned_miles,
                    "week_start": week_start,
                    "week_end": week_end,
                }
            )

        # Reverse to get chronological order (oldest first)
        weekly_data.reverse()

        logger.info(f"📊 Generated {len(weekly_data)} weeks of planned miles data")

        return weekly_data

    except Exception as e:
        logger.error(f"❌ Error calculating weekly planned miles history: {e}")
        return []

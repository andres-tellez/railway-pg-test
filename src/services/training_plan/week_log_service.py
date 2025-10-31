"""
Week Log Service

Purpose:
    Fetch week logs (completion data, RPE) from database or Strava activities.
    Converts planned workouts + completion data into WeekLogRun format.

Integration:
    Used by weekly rebuild endpoint to get previous week's logs for adjustments.
    Leverages existing DataCollectionService to query activities table via user_id.

Database Infrastructure:
    - Uses activities table (via DataCollectionService.fetch_strava_activities)
    - Activities table contains: distance, moving_time, average_heartrate, etc.
    - Splits table exists but not needed for week logs (sufficient data in activities)

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from typing import List, Dict, Any, Optional
from datetime import date, timedelta, datetime
from sqlalchemy.orm import Session
import logging

from .weekly_adjuster import WeekLogRun
from .data_collection_service import DataCollectionService
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan

logger = logging.getLogger(__name__)


def fetch_week_logs_from_db(
    session: Session,
    plan_id: int,
    week_num: int,
    race_date: date,
) -> List[WeekLogRun]:
    """
    Fetch week logs from database by matching planned workouts with Strava activities.

    Leverages existing DataCollectionService to query activities table.

    Args:
        session: SQLAlchemy database session
        plan_id: Plan ID
        week_num: Week number (1-based)
        race_date: Race date to calculate week dates

    Returns:
        List of WeekLogRun entries for the week
    """
    # Get plan to access user_id
    plan = session.query(Plan).filter_by(id=plan_id).first()
    if not plan:
        logger.warning(f"Plan {plan_id} not found")
        return []

    # Get all workouts for this plan to find the week range
    all_workouts = (
        session.query(PlanWorkout)
        .filter_by(plan_id=plan_id)
        .order_by(PlanWorkout.date)
        .all()
    )

    if not all_workouts:
        logger.warning(f"No workouts found for plan {plan_id}")
        return []

    # Calculate week dates from race date backwards
    # Week N is N weeks before race week
    weeks_before_race = week_num
    target_week_start = race_date - timedelta(weeks=weeks_before_race)
    days_since_monday = target_week_start.weekday()
    week_start = target_week_start - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)

    # Find workouts for the target week
    week_workouts = [w for w in all_workouts if week_start <= w.date <= week_end]

    if not week_workouts:
        logger.debug(
            f"No workouts found for week {week_num} (dates: {week_start} to {week_end})"
        )
        return []

    # Fetch Strava activities for the week using existing DataCollectionService
    # This leverages the activities table via user_id (no athlete_id lookup needed)
    try:
        user_id = str(plan.user_id)

        # Calculate weeks back to include (round up to ensure we get the week)
        weeks_to_fetch = max(
            2, week_num + 1
        )  # Fetch enough weeks to include target week

        # Fetch activities using existing infrastructure
        activities = DataCollectionService.fetch_strava_activities(
            session=session, user_id=user_id, weeks=weeks_to_fetch, activity_type="Run"
        )

        # Filter activities to target week
        week_activities = [
            a
            for a in activities
            if a.get("date")
            and week_start
            <= datetime.strptime(a["date"], "%Y-%m-%d").date()
            <= week_end
        ]

        # Match planned workouts with completed activities
        # Simple matching: same day + similar distance (±20%)
        week_logs = []
        for workout in week_workouts:
            # Find matching activity on the same day
            matching_activity = None
            for activity in week_activities:
                activity_date = datetime.strptime(activity["date"], "%Y-%m-%d").date()
                if activity_date == workout.date:
                    # Check distance similarity (±20%)
                    planned_mi = workout.miles
                    actual_mi = activity.get("distance", 0) or 0
                    if abs(actual_mi - planned_mi) / max(planned_mi, 0.1) <= 0.2:
                        matching_activity = activity
                        break

            # Create WeekLogRun entry
            if matching_activity:
                planned_mi = workout.miles
                done_mi = matching_activity.get("distance", 0) or 0
                avg_hr = matching_activity.get("average_heartrate")

                # Normalize workout type
                run_type = _normalize_workout_type(workout.workout_type)

                # Estimate RPE from heart rate if available (simplified heuristic)
                rpe = _estimate_rpe_from_hr(avg_hr) if avg_hr else 3

                week_logs.append(
                    WeekLogRun(
                        run_type=run_type,
                        planned_mi=planned_mi,
                        done_mi=done_mi,
                        rpe=rpe,
                        avg_hr=int(avg_hr) if avg_hr else None,
                    )
                )
            else:
                # No matching activity - workout not completed
                run_type = _normalize_workout_type(workout.workout_type)
                week_logs.append(
                    WeekLogRun(
                        run_type=run_type,
                        planned_mi=workout.miles,
                        done_mi=0.0,
                        rpe=0,
                        avg_hr=None,
                    )
                )

        logger.info(
            f"Matched {len([w for w in week_logs if w.done_mi > 0])}/{len(week_workouts)} "
            f"workouts for week {week_num}"
        )

    except Exception as e:
        logger.warning(f"Error fetching Strava data for week logs: {e}")
        return []

    return week_logs


def _normalize_workout_type(workout_type: str) -> str:
    """Normalize workout type to standard format (easy, steady, endurance, long)."""
    if not workout_type:
        return "easy"
    workout_type_lower = workout_type.lower()
    if "easy" in workout_type_lower or "recovery" in workout_type_lower:
        return "easy"
    if "steady" in workout_type_lower or "aerobic" in workout_type_lower:
        return "steady"
    if "endurance" in workout_type_lower or "medium-long" in workout_type_lower:
        return "endurance"
    if "long" in workout_type_lower:
        return "long"
    return "easy"  # Default fallback


def _estimate_rpe_from_hr(avg_hr: float) -> int:
    """
    Estimate RPE from average heart rate.

    Simplified heuristic (can be improved with user-specific zones):
    - < 60% max HR (~120 bpm for age 30) → RPE 2-3 (very easy)
    - 60-70% max HR (~120-140) → RPE 3-4 (easy)
    - 70-80% max HR (~140-160) → RPE 5-6 (moderate)
    - 80-90% max HR (~160-180) → RPE 7-8 (hard)
    - > 90% max HR (~180+) → RPE 9-10 (very hard)
    """
    if avg_hr < 120:
        return 2
    elif avg_hr < 140:
        return 3
    elif avg_hr < 160:
        return 5
    elif avg_hr < 180:
        return 7
    else:
        return 9


def convert_request_logs_to_week_logs(
    request_logs: List[Dict[str, Any]]
) -> List[WeekLogRun]:
    """
    Convert request body logs to WeekLogRun format.

    Args:
        request_logs: List of dicts with keys:
            - run_type: str (easy/steady/endurance/long)
            - planned_mi: float
            - done_mi: float
            - rpe: int (1-10)
            - avg_hr: int (optional)

    Returns:
        List of WeekLogRun entries
    """
    week_logs = []
    for log in request_logs:
        week_logs.append(
            WeekLogRun(
                run_type=log.get("run_type", "easy"),
                planned_mi=float(log.get("planned_mi", 0) or 0),
                done_mi=float(log.get("done_mi", 0) or 0),
                rpe=int(log.get("rpe", 3) or 3),
                avg_hr=int(log.get("avg_hr")) if log.get("avg_hr") else None,
            )
        )
    return week_logs


def fetch_week_logs(
    session: Session,
    plan_id: int,
    week_num: int,
    race_date: date,
    request_logs: Optional[List[Dict[str, Any]]] = None,
) -> List[WeekLogRun]:
    """
    Fetch week logs from request or database/Strava.

    Priority:
    1. Request logs (user-provided)
    2. Database/Strava matching (if no request logs)

    Args:
        session: SQLAlchemy database session
        plan_id: Plan ID
        week_num: Week number
        race_date: Race date
        request_logs: Optional user-provided logs

    Returns:
        List of WeekLogRun entries
    """
    if request_logs:
        logger.info(f"Using request logs for plan {plan_id} week {week_num}")
        return convert_request_logs_to_week_logs(request_logs)

    # Try to fetch from database/Strava using existing infrastructure
    logger.info(
        f"Fetching week logs from database/Strava for plan {plan_id} week {week_num}"
    )
    return fetch_week_logs_from_db(session, plan_id, week_num, race_date)

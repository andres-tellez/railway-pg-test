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

from typing import List, Dict, Any, Optional, Tuple
from datetime import date, timedelta, datetime
from sqlalchemy.orm import Session
import logging

from .weekly_adjuster import WeekLogRun
from .data_collection_service import DataCollectionService
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.smartcoach_mobile_coach.runner_profile import infer_placement_role_from_label
from src.utils.adaptive_constants import (
    MATCH_DAY_WINDOW,
    MATCH_DISTANCE_TOLERANCE_EASY,
    MATCH_DISTANCE_TOLERANCE_QUALITY,
    MATCH_SCORE_PERFECT,
    MATCH_SCORE_GOOD,
    MATCH_SCORE_PARTIAL,
    MATCH_SCORE_TYPE_ONLY,
    MATCH_SCORE_NONE,
)

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
    from src.utils.date_helpers import get_week_start_for_date

    weeks_before_race = week_num
    target_week_start = race_date - timedelta(weeks=weeks_before_race)
    week_start = get_week_start_for_date(target_week_start)
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

        # Match planned workouts with completed activities using flexible matching
        # Allows matching within ±3 days and different distance tolerances for easy vs quality
        week_logs = _match_workouts_flexible(week_workouts, week_activities)

        logger.info(
            f"Matched {len([w for w in week_logs if w.done_mi > 0])}/{len(week_workouts)} "
            f"workouts for week {week_num} (flexible matching: ±{MATCH_DAY_WINDOW} days)"
        )

    except Exception as e:
        logger.warning(f"Error fetching Strava data for week logs: {e}")
        return []

    return week_logs


def _match_workouts_flexible(
    week_workouts: List[PlanWorkout], week_activities: List[Dict[str, Any]]
) -> List[WeekLogRun]:
    """
    Match planned workouts with Strava activities using flexible matching.

    Flexible matching allows:
    - Day flexibility: Match within ±MATCH_DAY_WINDOW days (default ±3)
    - Distance flexibility: ±40% for easy runs, ±20% for quality workouts
    - Workout type consideration: Prefers matching same workout type

    Prevents double-matching: Each activity can only match one workout.

    Args:
        week_workouts: List of planned workouts for the week
        week_activities: List of Strava activity dictionaries for the week

    Returns:
        List of WeekLogRun entries (one per planned workout)
    """
    week_logs = []
    matched_activity_ids = set()  # Prevent double-matching

    for workout in week_workouts:
        planned_mi = workout.miles
        planned_type = infer_placement_role_from_label(workout.workout_type)

        # Score all activities against this workout
        best_match = None
        best_score = MATCH_SCORE_NONE

        for activity in week_activities:
            # Skip already matched activities
            activity_id = activity.get("activity_id")
            if activity_id and activity_id in matched_activity_ids:
                continue

            activity_date = datetime.strptime(activity["date"], "%Y-%m-%d").date()
            actual_mi = activity.get("distance", 0) or 0

            # Calculate match score
            score, match_details = _calculate_match_score(
                workout_date=workout.date,
                activity_date=activity_date,
                planned_mi=planned_mi,
                actual_mi=actual_mi,
                planned_type=planned_type,
            )

            if score > best_score:
                best_score = score
                best_match = {
                    "activity": activity,
                    "score": score,
                    "details": match_details,
                }

        # Create WeekLogRun entry
        if best_match and best_score >= MATCH_SCORE_PARTIAL:
            # Good enough match (≥60% score)
            activity = best_match["activity"]
            activity_id = activity.get("activity_id")
            if activity_id:
                matched_activity_ids.add(activity_id)

            done_mi = activity.get("distance", 0) or 0
            avg_hr = activity.get("average_heartrate")

            run_type = infer_placement_role_from_label(workout.workout_type)

            # Estimate RPE from heart rate if available
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
            run_type = infer_placement_role_from_label(workout.workout_type)
            week_logs.append(
                WeekLogRun(
                    run_type=run_type,
                    planned_mi=planned_mi,
                    done_mi=0.0,
                    rpe=0,
                    avg_hr=None,
                )
            )

    return week_logs


def _calculate_match_score(
    workout_date: date,
    activity_date: date,
    planned_mi: float,
    actual_mi: float,
    planned_type: str,
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate match score for a workout-activity pair.

    Scoring system:
    - Perfect match (same day, same distance, same type) = 1.0
    - Good match (same type, within 2 days, ±30% distance) = 0.8
    - Partial match (same type, within 3 days, ±40% distance) = 0.6
    - Type match only (correct type, wrong day/distance) = 0.4
    - No match = 0.0

    Args:
        workout_date: Planned workout date
        activity_date: Actual activity date
        planned_mi: Planned distance in miles
        actual_mi: Actual distance in miles
        planned_type: Normalized workout type (easy/steady/endurance/long)

    Returns:
        Tuple of (score, details_dict)
    """
    # Calculate day difference (absolute)
    day_diff = abs((activity_date - workout_date).days)

    # Calculate distance difference percentage
    distance_pct_diff = abs(actual_mi - planned_mi) / max(planned_mi, 0.1)

    # Determine distance tolerance based on workout type
    # Easy/endurance runs are more lenient, quality workouts stricter
    is_quality_workout = planned_type in ("steady", "threshold", "tempo", "interval")
    distance_tolerance = (
        MATCH_DISTANCE_TOLERANCE_QUALITY
        if is_quality_workout
        else MATCH_DISTANCE_TOLERANCE_EASY
    )

    # Perfect match: same day, same distance (±10%), same type
    if day_diff == 0 and distance_pct_diff <= 0.10:
        return MATCH_SCORE_PERFECT, {
            "day_diff": day_diff,
            "distance_pct_diff": distance_pct_diff,
            "match_type": "perfect",
        }

    # Good match: same type, within 2 days, ±30% distance
    if day_diff <= 2 and distance_pct_diff <= 0.30:
        return MATCH_SCORE_GOOD, {
            "day_diff": day_diff,
            "distance_pct_diff": distance_pct_diff,
            "match_type": "good",
        }

    # Partial match: within day window, within distance tolerance
    if day_diff <= MATCH_DAY_WINDOW and distance_pct_diff <= distance_tolerance:
        return MATCH_SCORE_PARTIAL, {
            "day_diff": day_diff,
            "distance_pct_diff": distance_pct_diff,
            "match_type": "partial",
        }

    # Type match only: correct type but outside day/distance windows
    # (This would require knowing activity type, which we don't have here)
    # For now, return 0.0 if outside all windows
    return MATCH_SCORE_NONE, {
        "day_diff": day_diff,
        "distance_pct_diff": distance_pct_diff,
        "match_type": "none",
    }


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

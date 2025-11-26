"""
Recalculate HR Zones Service

Service to recalculate HR zones for existing workouts when max HR changes.
"""

import logging
from sqlalchemy.orm import Session
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.db.dao.user_profile_dao import get_user_profile
from src.db.dao.plan_workouts_dao import update_workout
from src.services.training_plan.plan_storage_service import PlanStorageService

logger = logging.getLogger(__name__)


def recalculate_hr_zones_for_plan(session: Session, plan_id: int) -> dict:
    """
    Recalculate HR zones for all workouts in a plan.

    This is useful when:
    - User syncs max HR from Strava
    - User manually updates max HR in profile
    - HR zone calculation logic changes

    Args:
        session: Database session
        plan_id: Plan ID

    Returns:
        Dict with counts: {"updated": int, "skipped": int, "errors": int}
    """
    # Get plan
    plan = session.query(Plan).filter_by(id=plan_id).first()
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")

    # Get user profile (with updated max_hr)
    user_profile = get_user_profile(session, str(plan.user_id))
    if not user_profile:
        raise ValueError(f"User profile not found for plan {plan_id}")

    # Get all workouts for this plan
    workouts = (
        session.query(PlanWorkout)
        .filter_by(plan_id=plan_id)
        .order_by(PlanWorkout.date)
        .all()
    )

    if not workouts:
        logger.warning(f"No workouts found for plan {plan_id}")
        return {"updated": 0, "skipped": 0, "errors": 0}

    updated_count = 0
    skipped_count = 0
    error_count = 0

    for workout in workouts:
        try:
            # Skip if no run_type_key (rest days, etc.)
            if not workout.run_type_key:
                # Try to infer from workout_type
                workout_type_lower = (workout.workout_type or "").lower()
                if "threshold" in workout_type_lower or "tempo" in workout_type_lower:
                    run_type_key = "threshold"
                elif "steady" in workout_type_lower or "aerobic" in workout_type_lower:
                    run_type_key = "steady"
                elif "long" in workout_type_lower or "endurance" in workout_type_lower:
                    run_type_key = "long"
                elif "easy" in workout_type_lower or "recovery" in workout_type_lower:
                    run_type_key = "easy"
                else:
                    skipped_count += 1
                    continue
            else:
                run_type_key = workout.run_type_key

            # Calculate new HR zone
            new_target_hr = PlanStorageService._calculate_hr_zone(
                run_type_key, user_profile
            )

            # Update workout
            update_workout(session, workout.id, {"target_hr": new_target_hr})
            updated_count += 1

        except Exception as e:
            logger.error(f"Error recalculating HR zone for workout {workout.id}: {e}")
            error_count += 1

    session.commit()

    logger.info(
        f"Recalculated HR zones for plan {plan_id}: "
        f"{updated_count} updated, {skipped_count} skipped, {error_count} errors"
    )

    return {
        "updated": updated_count,
        "skipped": skipped_count,
        "errors": error_count,
        "total": len(workouts),
    }


def recalculate_hr_zones_for_user(session: Session, user_id: str) -> dict:
    """
    Recalculate HR zones for all active plans for a user.

    Args:
        session: Database session
        user_id: User ID

    Returns:
        Dict with plan_id -> result counts
    """
    # Get all active plans for user
    plans = session.query(Plan).filter_by(user_id=user_id, is_active=True).all()

    if not plans:
        logger.info(f"No active plans found for user {user_id}")
        return {}

    results = {}
    for plan in plans:
        try:
            result = recalculate_hr_zones_for_plan(session, plan.id)
            results[plan.id] = result
        except Exception as e:
            logger.error(f"Error recalculating HR zones for plan {plan.id}: {e}")
            results[plan.id] = {"error": str(e)}

    return results


# db/dao/plan_workouts_dao.py
from datetime import date
from sqlalchemy.orm import Session
from src.db.models.plan_workouts import PlanWorkout


def insert_batch(session: Session, workouts: list[dict]) -> None:
    """Insert multiple workouts in a batch operation."""
    if not workouts:
        return

    try:
        # Use bulk_insert_mappings for efficiency
        session.bulk_insert_mappings(PlanWorkout, workouts)
        # Flush to ensure the data is written to the database
        session.flush()
        print(f"✅ Successfully inserted {len(workouts)} workouts to database")
    except Exception as e:
        print(f"❌ Error inserting workouts: {e}")
        session.rollback()
        raise


def list_by_plan(session: Session, plan_id: int) -> list[PlanWorkout]:
    return (
        session.query(PlanWorkout)
        .filter_by(plan_id=plan_id)
        .order_by(PlanWorkout.date)
        .all()
    )


def delete_by_plan(session: Session, plan_id: int) -> None:
    session.query(PlanWorkout).filter_by(plan_id=plan_id).delete()


def update_workout(
    session: Session, workout_id: int, updates: dict
) -> PlanWorkout | None:
    """Update a single workout by ID."""
    import logging
    logger = logging.getLogger(__name__)
    
    workout = session.query(PlanWorkout).filter_by(id=workout_id).first()
    if not workout:
        logger.warning(f"[DAO] update_workout: Workout {workout_id} not found")
        return None
    
    # Log what we're updating (especially pace_ranges)
    if "pace_ranges" in updates:
        logger.info(
            f"[DAO] update_workout: Setting pace_ranges for workout {workout_id}: {updates['pace_ranges']}"
        )
    
    for key, value in updates.items():
        if hasattr(workout, key):
            old_value = getattr(workout, key, None)
            setattr(workout, key, value)
            if key == "pace_ranges":
                logger.info(
                    f"[DAO] update_workout: Successfully set pace_ranges on workout {workout_id}. "
                    f"Old: {old_value}, New: {value}"
                )
        else:
            logger.warning(
                f"[DAO] update_workout: Workout {workout_id} does not have attribute '{key}'"
            )
    
    session.flush()
    
    # Verify the value was set after flush
    if "pace_ranges" in updates:
        actual_value = getattr(workout, "pace_ranges", None)
        logger.info(
            f"[DAO] update_workout: Verified pace_ranges on workout {workout_id} after flush: {actual_value}"
        )
    
    return workout


def get_workouts_for_week(
    session: Session,
    plan_id: int,
    week_start: date,
    week_end: date,
) -> list[PlanWorkout]:
    """Get all workouts for a specific week (date range)."""
    return (
        session.query(PlanWorkout)
        .filter(
            PlanWorkout.plan_id == plan_id,
            PlanWorkout.date >= week_start,
            PlanWorkout.date <= week_end,
        )
        .order_by(PlanWorkout.date)
        .all()
    )

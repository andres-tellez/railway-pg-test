# db/dao/plan_workouts_dao.py
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

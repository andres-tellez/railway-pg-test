from sqlalchemy.orm import Session
from src.db.models.plan_workouts import PlanWorkout


def insert_batch(session: Session, workouts: list[dict]) -> None:
    session.bulk_insert_mappings(PlanWorkout, workouts)


def list_by_plan(session: Session, plan_id: int) -> list[PlanWorkout]:
    return (
        session.query(PlanWorkout)
        .filter_by(plan_id=plan_id)
        .order_by(PlanWorkout.date)
        .all()
    )


def delete_by_plan(session: Session, plan_id: int) -> None:
    session.query(PlanWorkout).filter_by(plan_id=plan_id).delete()

# db/dao/plans_py

from sqlalchemy.orm import Session
from src.db.models.plans import Plan


def create_plan(session: Session, plan_data: dict) -> Plan:
    plan = Plan(**plan_data)
    session.add(plan)
    session.flush()  # Ensures plan.id is populated
    return plan


def get_plan(session: Session, plan_id: int) -> Plan | None:
    return session.query(Plan).filter_by(id=plan_id).one_or_none()


def list_plans_for_user(session: Session, user_id: str) -> list[Plan]:
    return (
        session.query(Plan)
        .filter_by(user_id=user_id)
        .order_by(Plan.created_at.desc())
        .all()
    )


def get_plan_with_workouts(
    session: Session, plan_id: int, user_id: str | None = None
) -> dict | None:
    query = session.query(Plan).filter(Plan.id == plan_id)
    if user_id:
        query = query.filter(Plan.user_id == user_id)

    plan = query.first()
    if not plan:
        return None

    return {
        "id": plan.id,
        "user_id": str(plan.user_id),
        "plan_name": plan.plan_name,
        "race_date": plan.race_date.isoformat() if plan.race_date else None,
        "race_distance": plan.race_distance,
        "notes": plan.notes,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "workouts": [
            {
                "id": w.id,
                "date": w.date.isoformat(),
                "workout_type": w.workout_type,
                "description": w.description,
                "miles": w.miles,
                "intensity": w.intensity,
            }
            for w in plan.workouts
        ],
    }

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
        "race_name": plan.race_name,
        "race_location": plan.race_location,
        "race_metadata": plan.race_metadata,
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
                "target_zone": w.target_zone,
                "target_hr": w.target_hr,
                "focus": w.focus,
                "segments": w.segments,
            }
            for w in plan.workouts
        ],
    }


def get_active_plan(session: Session, user_id: str) -> Plan | None:
    """Get the currently active plan for a user."""
    return session.query(Plan).filter_by(user_id=user_id, is_active=True).first()


def set_plan_active(session: Session, plan_id: int, user_id: str) -> bool:
    """Set a specific plan as active and deactivate all others for the user."""
    # First, verify the plan belongs to the user
    plan = get_plan(session, plan_id)
    if not plan or str(plan.user_id) != user_id:
        return False

    # Deactivate all plans for this user
    session.query(Plan).filter_by(user_id=user_id).update({"is_active": False})

    # Activate the specified plan
    plan.is_active = True
    session.commit()

    return True


def delete_plan(session: Session, plan_id: int, user_id: str) -> bool:
    """Delete a plan (only if it belongs to the user)."""
    plan = get_plan(session, plan_id)
    if not plan or str(plan.user_id) != user_id:
        return False

    session.delete(plan)
    session.commit()

    return True

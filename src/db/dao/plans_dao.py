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

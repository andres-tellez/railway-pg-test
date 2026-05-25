# db/dao/plans_py

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models.activities import Activity
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.plans import Plan
from src.db.models.user_phase_goals import UserPhaseGoal
from src.db.models.weekly_decision_log import WeeklyDecisionLog
from src.db.models.weekly_metrics import WeeklyMetrics


def _plan_user_id_key(user_id: str) -> UUID | str:
    """``plans.user_id`` is UUID on PostgreSQL; ORM compares reliably with UUID, not plain str."""
    try:
        return UUID(str(user_id))
    except (ValueError, TypeError, AttributeError):
        return str(user_id)


_ACTIVITY_PLAN_SCORING_CLEAR = {
    Activity.matched_plan_workout_id: None,
    Activity.planned_type: None,
    Activity.executed_type: None,
    Activity.zone_compliance_pct: None,
    Activity.pct_above_zone: None,
    Activity.pct_below_zone: None,
    Activity.run_score: None,
    Activity.scoring_detail: None,
    Activity.planned_miles: None,
    Activity.actual_miles: None,
    Activity.completion_pct: None,
}


def create_plan(session: Session, plan_data: dict) -> Plan:
    print("PLAN DICT KEYS:", plan_data.keys())
    print("SNAPSHOT IN PLAN_DICT:", "context_snapshot" in plan_data)
    plan = Plan(**plan_data)
    print("PLAN OBJECT:", plan.__dict__)
    # Note: this is the ORM's default SELECT for Plan, not the INSERT executed on flush.
    print(str(session.query(Plan).statement))
    session.add(plan)
    try:
        session.flush()  # Ensures plan.id is populated (INSERT runs here, not at commit)
    except Exception as e:
        print("DB COMMIT ERROR:", repr(e))
        raise
    return plan


def get_plan(session: Session, plan_id: int) -> Plan | None:
    return session.query(Plan).filter_by(id=plan_id).one_or_none()


def list_plans_for_user(session: Session, user_id: str) -> list[Plan]:
    uid = _plan_user_id_key(user_id)
    return (
        session.query(Plan)
        .filter_by(user_id=uid)
        .order_by(Plan.created_at.desc())
        .all()
    )


def get_plan_with_workouts(
    session: Session, plan_id: int, user_id: str | None = None
) -> dict | None:
    query = session.query(Plan).filter(Plan.id == plan_id)
    if user_id:
        query = query.filter(Plan.user_id == _plan_user_id_key(user_id))

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
    uid = _plan_user_id_key(user_id)
    return session.query(Plan).filter_by(user_id=uid, is_active=True).first()


def get_active_or_most_recent_plan(session: Session, user_id: str) -> Plan | None:
    """
    Plan row used across weekly-plan / recommendations when an active flag exists.

    Prefers ``is_active=True`` (newest among actives); otherwise falls back to the
    most recently created plan — mirroring :func:`src.services.plan.weekly_plan.build_weekly_plan_payload`.
    """
    uid = _plan_user_id_key(user_id)
    active = (
        session.query(Plan)
        .filter(Plan.user_id == uid, Plan.is_active.is_(True))
        .order_by(Plan.created_at.desc())
        .first()
    )
    if active is not None:
        return active
    return (
        session.query(Plan)
        .filter(Plan.user_id == uid)
        .order_by(Plan.created_at.desc())
        .first()
    )


def set_plan_active(session: Session, plan_id: int, user_id: str) -> bool:
    """Set a specific plan as active and deactivate all others for the user."""
    # First, verify the plan belongs to the user
    plan = get_plan(session, plan_id)
    if not plan or str(plan.user_id) != user_id:
        return False

    # Deactivate all plans for this user
    uid = _plan_user_id_key(user_id)
    session.query(Plan).filter_by(user_id=uid).update({"is_active": False})

    # Activate the specified plan
    plan.is_active = True
    session.commit()

    return True


def delete_plan(session: Session, plan_id: int, user_id: str) -> bool:
    """
    Delete a plan (only if it belongs to the user).

    Also removes plan-scoped rows that are not FK-cascaded from ``plans``:

    * ``weekly_metrics`` / ``weekly_decision_log`` (no DB FK to ``plans``)
    * ``user_phase_goals`` for this plan (explicit delete for SQLite tests
      where foreign keys are relaxed)
    * Plan-vs-actual **scoring columns** on ``activities`` that still pointed
      at this plan's ``plan_workouts`` (runs remain; link + scores cleared)

    ``plan_workouts`` are removed via ORM cascade when the ``Plan`` row is
    deleted. ``activities.matched_plan_workout_id`` would otherwise be cleared
    by ``ON DELETE SET NULL`` after workouts disappear; we clear scoring first
    so no row briefly references deleted workouts with stale denormalized data.
    """
    plan = get_plan(session, plan_id)
    if not plan or str(plan.user_id) != user_id:
        return False

    workout_ids = [
        row[0]
        for row in session.query(PlanWorkout.id)
        .filter(PlanWorkout.plan_id == plan_id)
        .all()
    ]
    if workout_ids:
        session.query(Activity).filter(
            Activity.matched_plan_workout_id.in_(workout_ids)
        ).update(
            _ACTIVITY_PLAN_SCORING_CLEAR,
            synchronize_session=False,
        )

    session.query(WeeklyMetrics).filter(WeeklyMetrics.plan_id == plan_id).delete(
        synchronize_session=False
    )
    session.query(WeeklyDecisionLog).filter(
        WeeklyDecisionLog.plan_id == plan_id
    ).delete(synchronize_session=False)
    session.query(UserPhaseGoal).filter(UserPhaseGoal.plan_id == plan_id).delete(
        synchronize_session=False
    )

    session.delete(plan)
    session.commit()

    return True

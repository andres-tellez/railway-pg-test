"""Plan delete removes plan-scoped metrics, logs, phase goals, and activity scoring."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from src.db.dao import plan_workouts_dao, plans_dao
from src.db.dao.weekly_decision_log_dao import create_decision_log
from src.db.dao.weekly_metrics_dao import create_weekly_metrics
from src.db.models.activities import Activity
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.user_identity import UserIdentity
from src.db.models.user_phase_goals import (
    GOAL_SOURCE_USER_STATED,
    GOAL_STATUS_ACTIVE,
    UserPhaseGoal,
)
from src.db.models.weekly_decision_log import WeeklyDecisionLog
from src.db.models.weekly_metrics import WeeklyMetrics


def test_delete_plan_clears_metrics_decision_log_phase_goals_and_activity_scoring(
    test_db_session,
):
    user_id = uuid.uuid4()
    test_db_session.add(
        UserIdentity(user_id=user_id, email="plan-delete-cleanup@example.com")
    )
    test_db_session.commit()

    athlete_id = 4_242_001
    test_db_session.add(UserAthleteLink(user_id=str(user_id), athlete_id=athlete_id))
    test_db_session.commit()

    plan = plans_dao.create_plan(
        test_db_session,
        {
            "user_id": user_id,
            "plan_name": "Cleanup Test Plan",
            "race_date": date(2026, 10, 1),
            "race_distance": "Marathon",
            "notes": "",
            "created_by": "test",
        },
    )
    test_db_session.commit()

    plan_workouts_dao.insert_batch(
        test_db_session,
        [
            {
                "plan_id": plan.id,
                "date": date(2026, 9, 1),
                "workout_type": "Easy",
                "description": "Run",
                "miles": 5.0,
                "intensity": "z2",
            },
        ],
    )
    test_db_session.commit()
    workout = test_db_session.query(PlanWorkout).filter_by(plan_id=plan.id).one()

    create_weekly_metrics(
        test_db_session, plan.id, 1, date(2026, 9, 1), volume_score=70
    )
    create_decision_log(
        test_db_session,
        plan.id,
        1,
        date(2026, 9, 1),
        "test_decision",
        "reason",
        {},
        {},
        0.5,
        "Base",
        8,
    )
    test_db_session.add(
        UserPhaseGoal(
            user_id=user_id,
            plan_id=plan.id,
            phase="Base",
            goal_text="Stay easy",
            status=GOAL_STATUS_ACTIVE,
            source=GOAL_SOURCE_USER_STATED,
        )
    )
    test_db_session.add(
        Activity(
            activity_id=999_888_777,
            athlete_id=athlete_id,
            user_id=user_id,
            name="Easy run",
            type="Run",
            start_date=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            matched_plan_workout_id=workout.id,
            planned_type="easy",
            executed_type="easy",
            run_score="green",
            zone_compliance_pct=90.0,
            planned_miles=5.0,
            actual_miles=5.0,
            completion_pct=95.0,
            conv_distance=5.0,
            moving_time=2400,
        )
    )
    test_db_session.commit()

    assert test_db_session.query(WeeklyMetrics).filter_by(plan_id=plan.id).count() == 1
    assert (
        test_db_session.query(WeeklyDecisionLog).filter_by(plan_id=plan.id).count() == 1
    )
    assert test_db_session.query(UserPhaseGoal).filter_by(plan_id=plan.id).count() == 1

    assert plans_dao.delete_plan(test_db_session, plan.id, str(user_id)) is True

    assert test_db_session.query(WeeklyMetrics).filter_by(plan_id=plan.id).count() == 0
    assert (
        test_db_session.query(WeeklyDecisionLog).filter_by(plan_id=plan.id).count() == 0
    )
    assert test_db_session.query(UserPhaseGoal).filter_by(plan_id=plan.id).count() == 0
    assert test_db_session.query(PlanWorkout).filter_by(plan_id=plan.id).count() == 0
    assert test_db_session.query(Plan).filter_by(id=plan.id).count() == 0

    reloaded = test_db_session.query(Activity).filter_by(activity_id=999_888_777).one()
    assert reloaded.matched_plan_workout_id is None
    assert reloaded.planned_type is None
    assert reloaded.run_score is None
    assert reloaded.conv_distance == 5.0

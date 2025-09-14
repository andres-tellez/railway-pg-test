import uuid
from datetime import date

from src.db.dao import plans_dao, plan_workouts_dao
from src.db.models.user_identity import UserIdentity


def test_insert_and_list_workouts(test_db_session):
    # 🔑 Create user first
    user_id = uuid.uuid4()
    test_db_session.add(UserIdentity(user_id=user_id, email="runner@example.com"))
    test_db_session.commit()

    # Create a plan for that user
    plan = plans_dao.create_plan(
        test_db_session,
        {
            "user_id": user_id,
            "plan_name": "Half Marathon Training",
            "race_date": date(2025, 11, 1),
            "race_distance": "Half",
            "notes": "Prep for November race",
            "created_by": "gpt",
        },
    )
    test_db_session.commit()

    # Insert workouts into the plan
    workouts = [
        {
            "plan_id": plan.id,
            "date": date(2025, 10, 1),
            "workout_type": "Long Run",
            "description": "10 miles easy pace",
            "miles": 10.0,
            "intensity": "Easy",
        },
        {
            "plan_id": plan.id,
            "date": date(2025, 10, 3),
            "workout_type": "Tempo",
            "description": "5 miles at tempo pace",
            "miles": 5.0,
            "intensity": "Hard",
        },
    ]
    plan_workouts_dao.insert_batch(test_db_session, workouts)
    test_db_session.commit()

    # Verify workouts were inserted
    results = plan_workouts_dao.list_by_plan(test_db_session, plan.id)
    assert len(results) == 2
    assert results[0].workout_type in ["Long Run", "Tempo"]


def test_delete_by_plan(test_db_session):
    # 🔑 Create user first
    user_id = uuid.uuid4()
    test_db_session.add(UserIdentity(user_id=user_id, email="deleteme@example.com"))
    test_db_session.commit()

    # Create a plan for that user
    plan = plans_dao.create_plan(
        test_db_session,
        {
            "user_id": user_id,
            "plan_name": "5K Training",
            "race_date": date(2025, 10, 1),
            "race_distance": "5K",
            "notes": "Short race",
            "created_by": "gpt",
        },
    )
    test_db_session.commit()

    # Insert one workout
    workouts = [
        {
            "plan_id": plan.id,
            "date": date(2025, 9, 20),
            "workout_type": "Intervals",
            "description": "8x400m",
            "miles": 3.0,
            "intensity": "Hard",
        }
    ]
    plan_workouts_dao.insert_batch(test_db_session, workouts)
    test_db_session.commit()

    # Ensure workout exists
    assert len(plan_workouts_dao.list_by_plan(test_db_session, plan.id)) == 1

    # Delete workouts by plan
    plan_workouts_dao.delete_by_plan(test_db_session, plan.id)
    test_db_session.commit()

    # Verify deletion
    assert len(plan_workouts_dao.list_by_plan(test_db_session, plan.id)) == 0

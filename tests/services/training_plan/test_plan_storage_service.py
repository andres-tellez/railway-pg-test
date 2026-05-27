"""
Tests for Layer 6: Plan Storage Service

Tests saving validated plans to database.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from src.services.training_plan.plan_storage_service import PlanStorageService
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.user_identity import UserIdentity


def _validated_plan():
    """Create a validated plan structure from Layer 5."""
    # Race date 16 weeks from now
    race_date = (datetime.now() + timedelta(weeks=16)).strftime("%Y-%m-%d")

    return {
        "plan_name": "16 Week Marathon Plan",
        "plan_summary": "A comprehensive training plan",
        "weeks": [
            {
                "week_number": 1,
                "phase": "Base Building",
                "weekly_mileage": 20.0,
                "week_notes": "Start easy",
                "workouts": [
                    {
                        "day": "Monday",
                        "workout_type": "Easy Run",
                        "distance_miles": 3.0,
                        "pace_guidance": "Easy pace",
                        "workout_description": "Easy 3 mile run",
                    },
                    {
                        "day": "Wednesday",
                        "workout_type": "Easy Run",
                        "distance_miles": 4.0,
                        "pace_guidance": "Easy pace",
                        "workout_description": "Easy 4 mile run",
                    },
                    {
                        "day": "Saturday",
                        "workout_type": "Long Run",
                        "distance_miles": 8.0,
                        "pace_guidance": "Easy pace",
                        "workout_description": "Long run",
                    },
                ],
            }
        ],
        "race_week_strategy": "Taper guidance",
        "nutrition_tips": "Eat well",
        "injury_prevention_tips": "Stay healthy",
    }


def _plan_request():
    """Create a plan request with race details."""
    race_date = (datetime.now() + timedelta(weeks=16)).strftime("%Y-%m-%d")
    return {
        "race_date": race_date,
        "race_name": "Boston Marathon",
        "race_location": "Boston, MA",
        "primary_goal": "Just Finish",
        "training_days": ["Mon", "Wed", "Sat"],
        "notes": "First marathon",
    }


class TestPlanStorageService:
    def test_save_validated_plan_creates_plan_record(self, test_db_session):
        """Test that saving creates a Plan record in database."""
        # Follow pattern from test_plans_dao.py: use uuid.uuid4() instead of hardcoded UUID
        user_id = uuid.uuid4()
        test_db_session.add(UserIdentity(user_id=user_id, email="test1@example.com"))
        test_db_session.commit()

        validated_plan = _validated_plan()
        plan_request = _plan_request()

        # Service accepts string, so convert
        plan_id = PlanStorageService.save_validated_plan(
            test_db_session, str(user_id), validated_plan, plan_request
        )

        assert plan_id is not None

        # Verify plan was created
        plan = test_db_session.query(Plan).filter_by(id=plan_id).first()
        assert plan is not None
        assert plan.plan_name == validated_plan["plan_name"]
        assert plan.user_id == user_id  # Direct UUID comparison like test_plans_dao.py
        assert plan.race_date is not None
        assert plan.primary_goal == plan_request["primary_goal"]

    def test_save_validated_plan_creates_workouts(self, test_db_session):
        """Test that workouts are saved to plan_workouts table."""
        user_id = uuid.uuid4()
        test_db_session.add(UserIdentity(user_id=user_id, email="test2@example.com"))
        test_db_session.commit()

        validated_plan = _validated_plan()
        plan_request = _plan_request()

        plan_id = PlanStorageService.save_validated_plan(
            test_db_session, str(user_id), validated_plan, plan_request
        )

        # Verify workouts were created
        workouts = test_db_session.query(PlanWorkout).filter_by(plan_id=plan_id).all()
        assert len(workouts) > 0
        assert len(workouts) == len(validated_plan["weeks"][0]["workouts"])

        # Check first workout
        workout = workouts[0]
        assert workout.plan_id == plan_id
        assert workout.workout_type in ["Easy Run", "Long Run"]
        assert workout.miles > 0
        assert workout.description is not None

    def test_save_plan_deactivates_existing_active_plans(self, test_db_session):
        """Test that saving a new plan deactivates previous active plans."""
        # Follow pattern from test_plans_dao.py: use uuid.uuid4()
        user_id = uuid.uuid4()
        test_db_session.add(UserIdentity(user_id=user_id, email="test3@example.com"))

        # Create an existing active plan (using UUID object directly)
        existing_plan = Plan(user_id=user_id, plan_name="Old Plan", is_active=True)
        test_db_session.add(existing_plan)
        test_db_session.commit()

        validated_plan = _validated_plan()
        plan_request = _plan_request()

        plan_id = PlanStorageService.save_validated_plan(
            test_db_session,
            str(user_id),  # Service accepts string
            validated_plan,
            plan_request,
        )

        # Verify old plan is deactivated
        test_db_session.refresh(existing_plan)
        assert existing_plan.is_active is False

        # Verify new plan is active
        new_plan = test_db_session.query(Plan).filter_by(id=plan_id).first()
        assert new_plan.is_active is True

    def test_save_plan_calculates_correct_workout_dates(self, test_db_session):
        """Test that workout dates are calculated correctly from week numbers."""
        user_id = uuid.uuid4()
        test_db_session.add(UserIdentity(user_id=user_id, email="test4@example.com"))
        test_db_session.commit()

        validated_plan = _validated_plan()
        plan_request = _plan_request()

        race_date = datetime.strptime(plan_request["race_date"], "%Y-%m-%d").date()

        plan_id = PlanStorageService.save_validated_plan(
            test_db_session, str(user_id), validated_plan, plan_request
        )

        # Get workouts and verify dates
        workouts = (
            test_db_session.query(PlanWorkout)
            .filter_by(plan_id=plan_id)
            .order_by(PlanWorkout.date)
            .all()
        )

        # Workouts should have valid dates
        assert len(workouts) > 0
        for workout in workouts:
            assert workout.date is not None
            # Workouts should be before or on race week (allow race week workouts)
            assert (
                workout.date <= race_date or abs((workout.date - race_date).days) <= 7
            )

    def test_save_plan_handles_transaction_rollback_on_error(self, test_db_session):
        """Test that transaction is rolled back on error."""
        user_id = uuid.uuid4()
        test_db_session.add(UserIdentity(user_id=user_id, email="test5@example.com"))
        test_db_session.commit()

        validated_plan = _validated_plan()
        plan_request = _plan_request()

        # Corrupt the plan to cause an error
        validated_plan["weeks"][0]["workouts"][0]["distance_miles"] = -5.0  # Invalid

        with pytest.raises(Exception):  # Should raise some error
            PlanStorageService.save_validated_plan(
                test_db_session, str(user_id), validated_plan, plan_request
            )

        # Verify nothing was saved (compare UUID objects directly like test_plans_dao.py)
        plans = test_db_session.query(Plan).filter_by(user_id=user_id).all()
        assert len(plans) == 0


class TestPlanStorageRunTypeKeyValidation:
    def test_validate_row_accepts_placement_roles(self):
        for key in ("easy", "steady", "endurance", "long"):
            row = {"run_type_key": key, "segments": {}, "miles": 5.0}
            PlanStorageService._validate_row(row)
            assert row["run_type_key"] == key

    def test_validate_row_normalizes_long_run_alias(self):
        row = {"run_type_key": "long_run", "segments": {}, "miles": 12.0}
        PlanStorageService._validate_row(row)
        assert row["run_type_key"] == "long"

    def test_validate_row_rejects_taxonomy_quality_keys(self):
        row = {"run_type_key": "tempo", "segments": {}, "miles": 6.0}
        with pytest.raises(ValueError, match="Invalid run_type_key"):
            PlanStorageService._validate_row(row)

    def test_validate_row_rejects_unknown_keys(self):
        row = {"run_type_key": "Race", "segments": {}, "miles": 26.2}
        with pytest.raises(ValueError, match="Invalid run_type_key"):
            PlanStorageService._validate_row(row)

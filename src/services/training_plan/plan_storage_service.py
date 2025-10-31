"""
Layer 6: Plan Storage Service

Purpose:
    Save validated training plan to database.
    Handle plan record creation, workout insertion, and plan activation.

Responsibilities:
    - Create Plan record in database
    - Create PlanWorkout records (batch insert)
    - Deactivate previous active plans
    - Handle database transactions and rollback

Dependencies:
    - Validated plan from Layer 5 (PlanValidationService)
    - Database models (Plan, PlanWorkout)
    - SQLAlchemy session

Testing:
    See tests/services/training_plan/test_plan_storage_service.py

Author: SmartCoach Development Team
Last Updated: October 29, 2025
"""

import logging
from uuid import UUID
from typing import Dict, Any, List
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session

from src.db.dao.plans_dao import create_plan
from src.db.dao.plan_workouts_dao import insert_batch
from src.db.models.plans import Plan

logger = logging.getLogger(__name__)

# Day name to weekday mapping (0=Monday, 6=Sunday)
DAY_TO_WEEKDAY = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
    "Mon": 0,
    "Tue": 1,
    "Wed": 2,
    "Thu": 3,
    "Fri": 4,
    "Sat": 5,
    "Sun": 6,
}


class PlanStorageService:
    """Service for storing training plans in the database."""

    @staticmethod
    def save_validated_plan(
        session: Session,
        user_id: str,
        validated_plan: Dict[str, Any],
        plan_request: Dict[str, Any],
    ) -> int:
        """
        Save validated training plan to database.

        Args:
            session: SQLAlchemy database session
            user_id: UUID string of the user
            validated_plan: Validated plan from Layer 5 (must have "validated_plan" key)
            plan_request: Original plan request with race details

        Returns:
            plan_id: ID of created plan

        Raises:
            ValueError: If plan is invalid or data is missing
            Exception: Database errors (transaction will be rolled back)
        """
        logger.info(f"Saving validated plan for user {user_id}")

        try:
            # Extract validated plan (Layer 5 returns {"validated_plan": ...})
            if "validated_plan" in validated_plan:
                plan_data = validated_plan["validated_plan"]
            else:
                plan_data = validated_plan  # Assume already validated

            # Parse race date
            race_date_str = plan_request.get("race_date")
            if not race_date_str:
                raise ValueError("race_date is required in plan_request")

            if isinstance(race_date_str, str):
                race_date = datetime.strptime(race_date_str, "%Y-%m-%d").date()
            elif isinstance(race_date_str, date):
                race_date = race_date_str
            else:
                raise ValueError(f"Invalid race_date format: {race_date_str}")

            # Convert user_id to UUID if string
            user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

            # Prepare plan record
            plan_dict = {
                "user_id": user_uuid,
                "plan_name": plan_data.get("plan_name", f"Marathon Plan - {race_date}"),
                "race_date": race_date,
                "race_distance": plan_request.get("race_distance", "Marathon"),
                "race_name": plan_request.get("race_name"),
                "race_location": plan_request.get("race_location"),
                "primary_goal": plan_request.get("primary_goal"),
                "target_time": plan_request.get("target_time"),
                "training_days": plan_request.get("training_days"),
                "notes": plan_request.get("notes"),
                "is_active": True,
            }

            # Deactivate existing active plans
            session.query(Plan).filter_by(user_id=user_uuid, is_active=True).update(
                {"is_active": False}
            )

            # Create plan record
            plan = create_plan(session, plan_dict)
            session.flush()  # Get plan.id
            plan_id = plan.id

            logger.debug(f"Created plan record {plan_id}")

            # Convert weeks/workouts to dated workout records
            workouts_to_insert = PlanStorageService._convert_workouts_to_db_format(
                plan_id, plan_data, race_date
            )

            if workouts_to_insert:
                # Insert workouts in batch
                insert_batch(session, workouts_to_insert)
                logger.info(
                    f"Saved {len(workouts_to_insert)} workouts for plan {plan_id}"
                )

            # Commit transaction
            session.commit()
            logger.info(f"Successfully saved plan {plan_id} for user {user_id}")

            return plan_id

        except Exception as e:
            session.rollback()
            logger.error(f"Error saving plan for user {user_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def _convert_workouts_to_db_format(
        plan_id: int, plan_data: Dict[str, Any], race_date: date
    ) -> List[Dict[str, Any]]:
        """
        Convert plan weeks/workouts structure to dated workout records.

        Args:
            plan_id: ID of the plan
            plan_data: Plan data with weeks array
            race_date: Race date to calculate workout dates from

        Returns:
            List of workout dictionaries ready for database insertion
        """
        workouts_to_insert = []
        weeks = plan_data.get("weeks", [])

        if not weeks:
            logger.warning("Plan has no weeks - no workouts to save")
            return workouts_to_insert

        # Sort weeks by week_number
        sorted_weeks = sorted(weeks, key=lambda w: w.get("week_number", 0))

        if not sorted_weeks:
            return workouts_to_insert

        max_week_num = max(w.get("week_number", 0) for w in sorted_weeks)

        for week in sorted_weeks:
            week_num = week.get("week_number", 0)
            week_workouts = week.get("workouts", [])

            # Calculate week start date: work backwards from race date
            # Week N should be N weeks before race (approximately)
            # So week 1 is ~(max_week_num - 1) weeks before race
            weeks_before_race = max_week_num - week_num
            week_start = race_date - timedelta(weeks=weeks_before_race)

            # Adjust to Monday of that week
            days_since_monday = week_start.weekday()  # 0=Monday, 6=Sunday
            week_start_monday = week_start - timedelta(days=days_since_monday)

            for workout in week_workouts:
                day_name = workout.get("day", "Monday")
                weekday = DAY_TO_WEEKDAY.get(day_name, 0)  # Default to Monday

                # Calculate workout date
                workout_date = week_start_monday + timedelta(days=weekday)

                # Validate and extract distance
                distance_miles = float(workout.get("distance_miles", 0.0))
                if distance_miles < 0:
                    raise ValueError(
                        f"Invalid distance_miles: {distance_miles} (must be non-negative)"
                    )

                # Map workout fields to database format
                workout_db = {
                    "plan_id": plan_id,
                    "date": workout_date,
                    "workout_type": workout.get("workout_type", "Easy Run"),
                    "description": workout.get(
                        "workout_description", workout.get("description", "")
                    ),
                    "miles": distance_miles,
                    "intensity": workout.get(
                        "pace_guidance", "Easy"
                    ),  # Use pace_guidance as intensity
                    "target_zone": None,  # Optional field
                    "target_hr": None,  # Optional field
                    "focus": None,  # Optional field
                    "segments": None,  # Optional JSON field
                }

                workouts_to_insert.append(workout_db)

        return workouts_to_insert

    @staticmethod
    def save_plan(
        session: Session, user_id: str, validated_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Alias for save_validated_plan (backwards compatibility).

        Note: This method signature doesn't include plan_request, so it attempts
        to extract race details from validated_plan. For new code, use save_validated_plan.
        """
        # Extract plan_request from validated_plan if possible
        plan_data = validated_plan.get("validated_plan", validated_plan)
        weeks = plan_data.get("weeks", [])

        # Estimate race date from weeks (not ideal, but works for compatibility)
        num_weeks = len(weeks) if weeks else 16
        estimated_race_date = (datetime.now() + timedelta(weeks=num_weeks)).strftime(
            "%Y-%m-%d"
        )

        plan_request = {
            "race_date": estimated_race_date,
            "primary_goal": "Just Finish",
        }

        plan_id = PlanStorageService.save_validated_plan(
            session, user_id, validated_plan, plan_request
        )

        return {
            "plan_id": plan_id,
            "workouts_created": (
                len(plan_data.get("weeks", [{}])[0].get("workouts", []))
                if plan_data.get("weeks")
                else 0
            ),
            "status": "SUCCESS",
        }

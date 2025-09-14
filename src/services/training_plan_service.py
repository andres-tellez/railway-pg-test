# src/services/training_plan_service.py

import json
import uuid
from datetime import date, datetime
from sqlalchemy.orm import Session

from src.db.dao import plans_dao, plan_workouts_dao
from src.db.models.user_identity import UserIdentity
from src.db.models.plans import Plan
from src.services.gpt_client import call_gpt  # implement this wrapper


def generate_plan(
    session: Session, user_id: uuid.UUID, race_date: date, race_distance: str
) -> Plan:
    """
    Generate a personalized training plan for a user.
    - Gathers user profile & past activities
    - Calls GPT for a structured JSON plan
    - Validates JSON
    - Persists Plan + PlanWorkouts to DB
    """

    # Step 1: Load user (validate exists)
    user = session.query(UserIdentity).filter_by(user_id=user_id).one_or_none()
    if not user:
        raise ValueError(f"No user found with id={user_id}")

    # TODO: Step 2: Gather activities (for now, stub)
    activities_summary = {
        "weekly_miles": 20,
        "longest_run": 8,
        "recent_races": ["10K"],
    }

    # Step 3: Build GPT prompt
    prompt = f"""
    You are a running coach. Generate a JSON training plan in U.S. units (miles, minutes, days).
    Target race: {race_distance} on {race_date}.
    User weekly mileage: {activities_summary['weekly_miles']} miles.
    Longest run recently: {activities_summary['longest_run']} miles.
    Recent races: {', '.join(activities_summary['recent_races'])}.

    JSON schema:
    {{
      "plan_name": "string",
      "notes": "string",
      "workouts": [
        {{
          "date": "YYYY-MM-DD",
          "workout_type": "Rest | Easy | Long Run | Tempo | Intervals",
          "description": "string",
          "miles": float,
          "intensity": "Easy | Tempo | Interval | Long"
        }}
      ]
    }}
    """

    # Step 4: Call GPT
    response_text = call_gpt(prompt)  # must return JSON string
    plan_json = json.loads(response_text)

    # Step 5: Validate
    validate_plan_json(plan_json, race_date)

    # Step 6: Insert into plans table
    plan_data = {
        "user_id": user_id,
        "plan_name": plan_json["plan_name"],
        "race_date": race_date,
        "race_distance": race_distance,
        "notes": plan_json.get("notes", ""),
        "created_by": "gpt",
    }
    plan = plans_dao.create_plan(session, plan_data)

    # Step 7: Insert workouts
    workouts_data = []
    for w in plan_json["workouts"]:
        workouts_data.append(
            {
                "plan_id": plan.id,
                "date": date.fromisoformat(w["date"]),
                "workout_type": w["workout_type"],
                "description": w["description"],
                "miles": float(w["miles"]),
                "intensity": w["intensity"],
            }
        )

    plan_workouts_dao.insert_batch(session, workouts_data)

    session.commit()
    return plan


# -------------------------
# Validation
# -------------------------


class PlanValidationError(Exception):
    pass


def validate_plan_json(plan_json: dict, race_date: date):
    """Validate GPT training plan output before DB insert."""

    workouts = plan_json.get("workouts", [])
    if not workouts:
        raise PlanValidationError("Plan must include workouts")

    # Ensure at least one Rest day
    workout_types = [w.get("workout_type") for w in workouts]
    if "Rest" not in workout_types:
        raise PlanValidationError("Plan must include at least one Rest day")

    seen_dates = set()
    for w in workouts:
        # Workout type validation
        if w.get("workout_type") not in {
            "Rest",
            "Easy",
            "Long Run",
            "Tempo",
            "Intervals",
        }:
            raise PlanValidationError(f"Invalid workout_type: {w.get('workout_type')}")

        # Miles validation
        miles = w.get("miles")
        if miles is None or not isinstance(miles, (int, float)) or miles < 0:
            raise PlanValidationError(f"Invalid miles value: {miles}")

        # Date validation
        try:
            workout_date = datetime.strptime(w["date"], "%Y-%m-%d").date()
        except Exception:
            raise PlanValidationError(
                f"Invalid date format: {w.get('date')} (expected YYYY-MM-DD)"
            )

        if workout_date in seen_dates:
            raise PlanValidationError(f"Duplicate workout date: {workout_date}")
        seen_dates.add(workout_date)

        if workout_date > race_date:
            raise PlanValidationError(
                f"Workout date {workout_date} is after race date {race_date}"
            )

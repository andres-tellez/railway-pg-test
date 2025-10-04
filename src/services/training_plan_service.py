# src/services/training_plan_service.py

import os
import json
import uuid
from datetime import date, datetime
from sqlalchemy.orm import Session
from src.db.dao import plans_dao, plan_workouts_dao
from src.db.models.user_identity import UserIdentity
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.services.gpt_client import call_gpt  # Reserved wrapper for OpenAI calls
from src.services.training_plan_data_assembler import assemble_training_plan_data
from src.utils.gpt_ops import generate_training_plan
from src.utils.training_plan_validation import validate_plan_json

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_plan(
    session: Session, user_id: uuid.UUID, race_date: date, race_distance: str
) -> Plan:
    """
    Generate a personalized training plan and persist it to the DB.

    Args:
        session (Session): Active SQLAlchemy session.
        user_id (UUID): Unique identifier for the user.
        race_date (date): Target race date (plan must end before this).
        race_distance (str): Race type (e.g., "Marathon", "Half Marathon").

    Returns:
        Plan: Newly created Plan object (fetched after save).
    """

    # 1. Load runner data
    data_bundle = assemble_training_plan_data(session, user_id)
    if not data_bundle.get("user_profile"):
        raise ValueError("No user profile found")

    # 2. Build GPT prompt from runner history
    prompt = build_training_plan_prompt(data_bundle, start_date=datetime.today().date())

    # 🔧 NEW: Extract training_days
    training_days = data_bundle["user_profile"].get("training_days", [])
    # Normalize to uppercase abbreviations (MON, WED, etc.)
    training_days = [d.upper() for d in training_days]

    # 3. Generate and validate plan JSON via GPT
    plan_json = fetch_validated_training_plan(
        prompt, race_date=race_date, training_days=training_days
    )

    # 4. Patch in race metadata
    plan_json["race_date"] = str(race_date)
    plan_json["race_distance"] = race_distance

    # 5. Save using DAO-based DB persistence
    plan_id = save_plan_to_db(plan_json, str(user_id), session)
    return plans_dao.get_plan(session, plan_id)


# -------------------------
# Validation Layer
# -------------------------


class PlanValidationError(Exception):
    """Custom exception for invalid GPT training plan output."""


def validate_plan_json(plan_json: dict, race_date: date, training_days: list[str]):
    """
    Validate GPT training plan output before committing to the database.

    Rules enforced:
    - Must include at least one workout.
    - Must include at least one "Rest" day.
    - All workout types must be valid.
    - Mileage must be a positive number.
    - Dates must be unique and <= race_date.

    Args:
        plan_json (dict): Parsed JSON training plan.
        race_date (date): Target race date for validation.

    Raises:
        PlanValidationError: If any rule is violated.
    """

    if training_days is None:
        training_days = []
    allowed_days = set(training_days)

    # 🔧 Ensure race_date is a datetime.date, even if passed as string
    if isinstance(race_date, str):
        race_date = datetime.strptime(race_date, "%Y-%m-%d").date()

    print("\n================ VALIDATION START ================\n")
    print(json.dumps(plan_json, indent=2))  # 🔍 show full plan before validation
    print("\n=================================================\n")

    workouts = plan_json.get("workouts", [])
    if not workouts:
        print("❌ Validation failed: Plan must include workouts")
        raise PlanValidationError("Plan must include workouts")

    # Ensure at least one Rest day
    workout_types = [w.get("workout_type") for w in workouts]
    if "Rest" not in workout_types:
        print("❌ Validation failed: No Rest day found")
        raise PlanValidationError("Plan must include at least one Rest day")

    allowed_days = set(training_days)
    for w in workouts:
        workout_date = datetime.strptime(w["date"], "%Y-%m-%d").date()
        workout_day = workout_date.strftime("%a").upper()

        if w["workout_type"] != "Rest" and workout_day not in allowed_days:
            raise PlanValidationError(
                f"Workout on invalid day: {workout_date.strftime('%A')} ({w['date']})"
            )

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
            print(f"❌ Invalid workout_type: {w.get('workout_type')}")
            raise PlanValidationError(f"Invalid workout_type: {w.get('workout_type')}")

        # Miles validation
        miles = w.get("miles")
        if miles is None or not isinstance(miles, (int, float)) or miles < 0:
            print(f"❌ Invalid miles value: {miles}")
            raise PlanValidationError(f"Invalid miles value: {miles}")

        # Date validation
        try:
            workout_date = datetime.strptime(w["date"], "%Y-%m-%d").date()
        except Exception:
            print(f"❌ Invalid date format: {w.get('date')}")
            raise PlanValidationError(
                f"Invalid date format: {w.get('date')} (expected YYYY-MM-DD)"
            )

        if workout_date in seen_dates:
            print(f"❌ Duplicate workout date: {workout_date}")
            raise PlanValidationError(f"Duplicate workout date: {workout_date}")
        seen_dates.add(workout_date)

        if workout_date > race_date:
            print(f"❌ Workout date {workout_date} is after race date {race_date}")
            raise PlanValidationError(
                f"Workout date {workout_date} is after race date {race_date}"
            )

    print("✅ Validation passed\n")


def build_training_plan_prompt(data: dict, start_date: date | None = None) -> str:
    """
    Build a natural-language summary of runner profile, training summaries,
    and activities. Used for GPT input.

    Args:
        data (dict): Bundle with keys:
            - user_profile
            - weekly_summaries
            - activities
        start_date (date | None): The date when the training plan should begin.

    Returns:
        str: Formatted prompt string.
    """
    user = data.get("user_profile", {})
    summaries = data.get("weekly_summaries", [])
    activities = data.get("activities", [])

    # Runner profile section
    profile_section = [
        "Runner Profile:",
        f"- Level: {user.get('runner_level')}",
        f"- Goal: {user.get('main_goal')} ({user.get('race_distance')} on {user.get('race_date')})",
        f"- Training days: {', '.join(user.get('training_days', []))}",
        f"- Height: {user.get('height')}, Weight: {user.get('weight')} lbs",
        f"- Motivation: {', '.join(user.get('motivation', []))}",
        f"- Past races: {', '.join(user.get('past_races', []))}",
    ]
    profile_text = "\n".join(filter(None, profile_section))

    training_days = user.get("training_days", [])
    normalized_training_days = [d.upper() for d in training_days]
    start_day_abbr = start_date.strftime("%a").upper() if start_date else None
    start_on_training_day = start_day_abbr in normalized_training_days

    days_instruction = ""
    if training_days:
        days_instruction = (
            f"\n\nIMPORTANT: Only assign workouts on these days: {', '.join(training_days)}. "
            f"Do NOT assign workouts on any other days."
        )

    # Schema requirements
    schema_instructions = (
        "\n\nYou must respond with a JSON object containing:\n"
        "- plan_name (string)\n"
        "- notes (string)\n"
        "- workouts (non-empty list of objects)\n\n"
        "Each workout must include:\n"
        "- date (YYYY-MM-DD)\n"
        "- miles (number ≥ 0)\n"
        "- workout_type (one of: Rest, Easy, Long Run, Tempo, Intervals)\n"
        "- intensity (string)\n"
        "- description (string)\n"
        "Ensure at least one Rest day is included."
    )

    # 🔧 Add start day behavior instruction (after schema_instructions is defined)
    if start_date:
        if start_on_training_day:
            schema_instructions += (
                f"\n- The training plan starts on {start_date.strftime('%A, %B %d')}, "
                "which is a training day. Assign a workout on this day."
            )
        else:
            schema_instructions += (
                f"\n- The training plan starts on {start_date.strftime('%A, %B %d')}, "
                "which is a non-training day. Assign a rest day on this day."
            )

    # Weekly summaries
    summaries_text = "Weekly Training Summaries:\n" + "\n".join(
        f"- {s}" for s in summaries
    )

    # Recent activities
    activity_lines = []
    for a in activities:
        splits = ", ".join(s["split_time"] for s in a.get("splits", []))
        pace = f"{60 / a['avg_speed']:.2f} min/mi" if a.get("avg_speed") else "N/A"
        activity_lines.append(
            f"- {a['activity_date']} {a['activity_name']} "
            f"({a['distance']}mi, avg HR {a['avg_hr']}, pace {pace})"
            + (f"\n  Splits: {splits}" if splits else "")
        )
    activities_text = "Recent Activities:\n" + "\n".join(activity_lines)

    # Final prompt
    return "\n\n".join(
        [
            profile_text + days_instruction,
            summaries_text,
            activities_text,
            schema_instructions,
        ]
    )


def fetch_validated_training_plan(
    prompt: str, race_date: date = None, training_days: list[str] = None
) -> dict:
    """
    Calls GPT to generate a training plan and ensures the result is schema-compliant.
    Retries once with clarification if validation fails.

    Args:
        prompt (str): Structured prompt built from user data.
        race_date (date): Target race date to enforce workout cutoff.
        training_days (list[str]): List of valid training days (e.g., ["MON", "WED", ...])

    Returns:
        dict: Clean, validated training plan JSON.

    Raises:
        RuntimeError: If GPT response is invalid after retry.
    """
    # --- First attempt ---
    plan = generate_training_plan(prompt)
    try:
        validate_plan_json(plan, race_date=race_date, training_days=training_days)
        return plan
    except PlanValidationError as e:
        print("❌ GPT validation failed:", e)
        print("Retrying with clarification...")

    clarification = (
        "\n\nNOTE: Your last response was invalid. "
        "Please ensure:\n"
        "- Dates are unique and ≤ race_date\n"
        "- Only assign workouts on the user's allowed training days\n"
        "- Include at least 1 rest day and 1 workout\n"
        "- Only use types: Rest, Easy, Long Run, Tempo, Intervals\n"
        "Respond ONLY with corrected JSON."
    )

    # --- Retry once ---
    retry_prompt = prompt + clarification
    plan_retry = generate_training_plan(retry_prompt)
    try:
        validate_plan_json(plan_retry, race_date=race_date, training_days=training_days)
        return plan_retry
    except PlanValidationError as e:
        raise RuntimeError(f"GPT output failed validation after retry: {e}")


from datetime import datetime
import uuid


def save_plan_to_db(plan_json: dict, user_id: str, session: Session) -> int:
    """
    Persist the generated plan and its workouts into the database.

    Args:
        plan_json (dict): Validated plan JSON from GPT.
        user_id (str): The user UUID as string.
        session (Session): Active SQLAlchemy session.

    Returns:
        int: The ID of the saved plan.
    """
    # 1. Save the plan
    plan_data = {
        "user_id": uuid.UUID(user_id),  # 🔑 Ensure UUID type
        "plan_name": plan_json.get("plan_name", "Untitled Plan"),
        "notes": plan_json.get("notes", ""),
        "race_date": (
            datetime.strptime(plan_json["race_date"], "%Y-%m-%d").date()
            if plan_json.get("race_date")
            else None
        ),
        "race_distance": plan_json.get("race_distance"),
    }

    plan = plans_dao.create_plan(session, plan_data)

    # 2. Save workouts in batch
    workouts_data = []
    for w in plan_json.get("workouts", []):
        workouts_data.append(
            {
                "plan_id": plan.id,
                "date": datetime.strptime(
                    w["date"], "%Y-%m-%d"
                ).date(),  # 🔑 parse to date
                "miles": float(w["miles"]),
                "workout_type": w["workout_type"],
                "intensity": w["intensity"],
                "description": w["description"],
            }
        )

    if workouts_data:
        plan_workouts_dao.insert_batch(session, workouts_data)

    session.commit()
    return plan.id


from src.db.dao.plans_dao import get_plan_with_workouts


def get_plan(plan_id: int, session, user_id: str | None = None):
    return get_plan_with_workouts(session, plan_id, user_id)

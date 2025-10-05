# src/services/training_plan_service.py

import os
import json
import uuid
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from src.db.dao import plans_dao, plan_workouts_dao
from src.db.models.user_identity import UserIdentity
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.services.gpt_client import call_gpt  # Reserved wrapper for OpenAI calls
from src.services.training_plan_data_assembler import assemble_training_plan_data
from src.utils.gpt_ops import generate_training_plan, generate_training_plan_chunk
from src.utils.training_plan_validation import validate_plan_json

# Handle both old and new OpenAI API versions
try:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except ImportError:
    # Fallback for older openai versions
    import openai

    openai.api_key = os.getenv("OPENAI_API_KEY")
    client = None


def generate_plan_chunked(
    session: Session, user_id: uuid.UUID, race_date: date, race_distance: str
) -> Plan:
    """
    Generate a training plan in chunks to avoid response length limits.
    """
    print(f"🏃‍♂️ Generating chunked training plan for {race_distance} on {race_date}")

    # 1. Load runner data
    data_bundle = assemble_training_plan_data(session, user_id)
    if not data_bundle.get("user_profile"):
        raise ValueError("No user profile found")

    start_date = datetime.today().date()
    total_days = (race_date - start_date).days
    total_weeks = (total_days + 6) // 7  # Round up to ensure we cover the full duration

    print(f"📅 Plan duration: {total_days} days ({total_weeks} weeks)")
    print(f"📅 From {start_date} to {race_date}")

    # Create the plan record first
    plan_data = {
        "user_id": user_id,
        "plan_name": f"Marathon Training Plan - {race_distance}",
        "notes": f"Complete training plan for {race_distance} on {race_date}",
        "race_date": race_date,
        "race_distance": race_distance,
    }
    plan = plans_dao.create_plan(session, plan_data)
    print(f"✅ Created plan ID: {plan.id}")

    # Generate in smaller chunks with overlap to prevent gaps
    chunk_weeks = 4  # Smaller chunks
    all_workouts = []

    for chunk_start_week in range(0, total_weeks, chunk_weeks - 1):  # 1-week overlap
        chunk_end_week = min(chunk_start_week + chunk_weeks, total_weeks)
        chunk_start_date = start_date + timedelta(weeks=chunk_start_week)

        # Ensure the last chunk goes up to (but not past) the race date
        if chunk_end_week >= total_weeks:
            chunk_end_date = race_date - timedelta(days=1)  # End day before race
        else:
            chunk_end_date = start_date + timedelta(weeks=chunk_end_week)

        print(f"📦 Generating chunk {chunk_start_week//chunk_weeks + 1}: weeks {chunk_start_week+1}-{chunk_end_week}")

        # Build prompt for this chunk
        chunk_prompt = build_chunked_training_plan_prompt(
            data_bundle, chunk_start_date, chunk_end_date, chunk_start_week, chunk_end_week, total_weeks
        )

        # Generate workouts for this chunk
        try:
            chunk_workouts = generate_training_plan_chunk(chunk_prompt)
            all_workouts.extend(chunk_workouts)
            print(f"✅ Generated {len(chunk_workouts)} workouts for chunk {chunk_start_week//chunk_weeks + 1}")
        except Exception as e:
            print(f"❌ Error generating chunk {chunk_start_week//chunk_weeks + 1}: {e}")
            # Continue with next chunk
            continue

    # Save all workouts to database (deduplicated)
    if all_workouts:
        # Remove duplicates based on date (in case of overlapping chunks)
        unique_workouts = {}
        for w in all_workouts:
            workout_date = datetime.strptime(w["date"], "%Y-%m-%d").date()
            if workout_date not in unique_workouts:
                unique_workouts[workout_date] = w

        workouts_data = []
        for w in unique_workouts.values():
            # Handle structured workout data
            workout_data = {
                "plan_id": plan.id,
                "date": datetime.strptime(w["date"], "%Y-%m-%d").date(),
                "miles": float(w["miles"]),
                "workout_type": w["workout_type"],
                "intensity": w["intensity"],
                "target_zone": w.get("target_zone", ""),
                "target_hr": w.get("target_hr", ""),
                "focus": w.get("focus", ""),
                "segments": w.get("segments"),  # JSON array or null
            }

            # Keep description for backward compatibility, but prefer structured data
            if "description" in w:
                workout_data["description"] = w["description"]
            elif w.get("segments"):
                # Generate description from segments for simple display
                segment_names = [s.get("name", "") for s in w["segments"] if s.get("name")]
                workout_data["description"] = " | ".join(segment_names) if segment_names else ""
            else:
                workout_data["description"] = w.get("focus", "")

            workouts_data.append(workout_data)

        plan_workouts_dao.insert_batch(session, workouts_data)
        print(f"✅ Saved {len(workouts_data)} unique workouts to database")

    return plan

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

    # Use chunked generation for better reliability with long training plans
    return generate_plan_chunked(session, user_id, race_date, race_distance)


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


def build_chunked_training_plan_prompt(
    data: dict, chunk_start_date: date, chunk_end_date: date,
    chunk_start_week: int, chunk_end_week: int, total_weeks: int
) -> str:
    """
    Build a prompt for generating a specific chunk of the training plan.
    """
    user = data.get("user_profile", {})
    summaries = data.get("weekly_summaries", [])[:6]  # Limit summaries for chunks
    activities = data.get("activities", [])[:8]       # Limit activities for chunks

    # Runner profile section (concise)
    profile_section = [
        "Runner Profile:",
        f"- Level: {user.get('runner_level')}",
        f"- Goal: {user.get('main_goal')} ({user.get('race_distance')})",
        f"- Training days: {', '.join(user.get('training_days', []))}",
        f"- Weight: {user.get('weight')} lbs",
    ]
    profile_text = "\n".join(filter(None, profile_section))

    # Phase-specific instructions
    phase_instruction = ""
    if chunk_start_week < total_weeks * 0.4:
        phase_instruction = "BASE BUILDING PHASE: Focus on easy runs, building endurance, some tempo work"
    elif chunk_start_week < total_weeks * 0.8:
        phase_instruction = "BUILD PHASE: Increase intensity, add intervals, longer tempo runs"
    else:
        phase_instruction = "TAPER PHASE: Reduce volume, maintain intensity, prepare for race"

    # Recent activities (very concise)
    activity_lines = []
    for a in activities:
        pace = f"{60 / a['avg_speed']:.2f} min/mi" if a.get("avg_speed") else "N/A"
        activity_lines.append(f"- {a['activity_date']}: {a['distance']}mi, {pace}")
    activities_text = "Recent Activities:\n" + "\n".join(activity_lines)

    # Schema for chunk with structured workout data
    schema_instructions = (
        f"\n\nGenerate training plan for weeks {chunk_start_week+1}-{chunk_end_week} "
        f"({chunk_start_date.strftime('%Y-%m-%d')} to {chunk_end_date.strftime('%Y-%m-%d')}):\n"
        f"- {phase_instruction}\n"
        f"- IMPORTANT: This is a TRAINING plan leading to race on February 15, 2026\n"
        f"- DO NOT include any race simulations or mock races in this chunk\n"
        f"- DO NOT create large gaps between workouts (max 2-3 days between runs)\n"
        f"- Ensure consistent weekly training schedule throughout the period\n"
        f"- Return JSON with workouts array\n"
        f"- Each workout must include:\n"
        f"  * date (YYYY-MM-DD)\n"
        f"  * miles (number ≥ 0)\n"
        f"  * workout_type (one of: Rest, Easy, Long Run, Tempo, Intervals)\n"
        f"  * intensity (string)\n"
        f"  * target_zone (heart rate zone: Zone 1-5 or 'Recovery' for rest)\n"
        f"  * target_hr (heart rate range in bpm, e.g., '130-150 bpm')\n"
        f"  * focus (string describing the workout purpose)\n"
        f"  * segments (array of workout segments for complex workouts, null for simple workouts)\n"
        f"- For simple workouts (Easy, Long Run): segments = null\n"
        f"- For complex workouts (Tempo, Intervals): segments array with:\n"
        f"  * name (string: 'Warm-up', 'Main Set', 'Interval 1', etc.)\n"
        f"  * distance (string: '1 mile', '800m', '4 miles', etc.)\n"
        f"  * target_zone (string: 'Zone 2', 'Zone 4', etc.)\n"
        f"  * notes (string: 'Easy pace', 'Tempo pace', '90 sec rest', etc.)\n"
        f"- Heart rate zones: Zone 1 (recovery), Zone 2-3 (easy), Zone 4 (hard), Zone 5 (very hard)\n"
        f"- Training days: {', '.join(user.get('training_days', []))}"
    )

    return "\n\n".join([
        profile_text,
        activities_text,
        schema_instructions
    ])

def build_training_plan_prompt(data: dict, start_date: date | None = None, race_date: date | None = None) -> str:
    """
    Build a natural-language summary of runner profile, training summaries,
    and activities. Used for GPT input.

    Args:
        data (dict): Bundle with keys:
            - user_profile
            - weekly_summaries
            - activities
        start_date (date | None): The date when the training plan should begin.
        race_date (date | None): The target race date - plan should end before this date.

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

    # 🎯 CRITICAL: Add plan duration instructions
    if race_date and start_date:
        days_until_race = (race_date - start_date).days
        weeks_until_race = days_until_race // 7

        schema_instructions += (
            f"\n\n🎯 CRITICAL: Generate FIRST 8 WEEKS of training plan from {start_date.strftime('%A, %B %d, %Y')} to {(start_date + timedelta(weeks=8)).strftime('%A, %B %d, %Y')}\n"
            f"- Generate ONLY the first 8 weeks (base building phase)\n"
            f"- Include workouts for EVERY day in these 8 weeks\n"
            f"- Focus on base building: easy runs, long runs, some tempo\n"
            f"- Do NOT try to generate the full 19 weeks in one response"
        )

    # Weekly summaries (concise for token efficiency)
    summaries_text = "Weekly Training Summaries:\n" + "\n".join(
        f"- {s}" for s in summaries[:8]  # Limit to 8 most recent weeks
    )

    # Recent activities (concise for token efficiency)
    activity_lines = []
    for a in activities[:10]:  # Limit to 10 most recent activities
        pace = f"{60 / a['avg_speed']:.2f} min/mi" if a.get("avg_speed") else "N/A"
        activity_lines.append(
            f"- {a['activity_date']}: {a['distance']}mi, {pace}, HR {a['avg_hr']}"
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

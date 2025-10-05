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
from src.utils.gpt_ops import generate_training_plan_chunk
# Note: Using local validate_plan_json function instead of imported one
# The imported function is for old format with "weeks" structure

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
    
    # Convert enum objects to strings
    training_days_raw = data_bundle.get("user_profile", {}).get("training_days", [])
    training_days = [str(day) for day in training_days_raw] if training_days_raw else []

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
            data_bundle, chunk_start_date, chunk_end_date, chunk_start_week, chunk_end_week, total_weeks, training_days
        )

        # Generate workouts for this chunk
        try:
            chunk_workouts = generate_training_plan_chunk(chunk_prompt)
            
            # Validate chunk before adding to all_workouts
            chunk_plan_json = {"workouts": chunk_workouts}
            validate_plan_json(chunk_plan_json, race_date, training_days)
            
            all_workouts.extend(chunk_workouts)
            print(f"✅ Generated and validated {len(chunk_workouts)} workouts for chunk {chunk_start_week//chunk_weeks + 1}")
        except Exception as e:
            print(f"❌ Error generating or validating chunk {chunk_start_week//chunk_weeks + 1}: {e}")
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

        # Final validation of the complete plan before saving
        final_plan_json = {"workouts": list(unique_workouts.values())}
        validate_plan_json(final_plan_json, race_date, training_days)
        
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
    print(f"🔍 VALIDATION: Allowed training days: {allowed_days}")
    
    for w in workouts:
        workout_date = datetime.strptime(w["date"], "%Y-%m-%d").date()
        workout_day = workout_date.strftime("%a").upper()
        
        print(f"🔍 VALIDATION: Checking workout on {workout_date.strftime('%A')} ({w['date']}) - Type: {w['workout_type']}")

        if w["workout_type"] != "Rest" and workout_day not in allowed_days:
            error_msg = f"❌ TRAINING DAYS VIOLATION: Workout scheduled on {workout_date.strftime('%A')} ({w['date']}) but training days are: {', '.join(allowed_days)}"
            print(error_msg)
            raise PlanValidationError(error_msg)

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


def quality_control_audit_plan(session: Session, user_id: uuid.UUID) -> dict:
    """
    Comprehensive quality control audit of a user's training plan.
    
    Returns:
        dict: Audit results with violations and recommendations
    """
    from src.db.models.plans import Plan
    from src.db.models.plan_workouts import PlanWorkout
    from sqlalchemy.orm import joinedload
    
    print("🔍 Starting Quality Control Audit...")
    
    # Get user's training days
    data_bundle = assemble_training_plan_data(session, user_id)
    training_days_raw = data_bundle.get("user_profile", {}).get("training_days", [])
    training_days = [str(day) for day in training_days_raw] if training_days_raw else []
    
    # Get the latest plan
    plan = (
        session.query(Plan)
        .options(joinedload(Plan.workouts))
        .filter_by(user_id=str(user_id))
        .order_by(Plan.created_at.desc())
        .first()
    )
    
    if not plan:
        return {"status": "no_plan", "message": "No training plan found"}
    
    workouts = sorted(plan.workouts, key=lambda w: w.date)
    
    # Audit results
    violations = []
    warnings = []
    recommendations = []
    
    allowed_days = set(training_days)
    print(f"🔍 AUDIT: Allowed training days: {allowed_days}")
    
    # Check each workout
    for workout in workouts:
        workout_day = workout.date.strftime("%a")
        
        # Check training days violation
        if workout.workout_type != "Rest" and workout_day not in allowed_days:
            violation = {
                "date": str(workout.date),
                "day": workout_day,
                "type": "training_days_violation",
                "workout_type": workout.workout_type,
                "message": f"Workout on {workout_day} but training days are: {', '.join(allowed_days)}"
            }
            violations.append(violation)
            print(f"❌ VIOLATION: {violation['message']}")
    
    # Generate recommendations
    if violations:
        recommendations.append("Regenerate the training plan to fix training days violations")
        recommendations.append("Consider using stricter validation during plan generation")
    
    # Check for missing workouts on training days
    from datetime import timedelta
    start_date = workouts[0].date if workouts else plan.created_at.date()
    end_date = workouts[-1].date if workouts else plan.race_date
    
    current_date = start_date
    while current_date <= end_date:
        day_name = current_date.strftime("%a")
        if day_name in allowed_days:
            # Check if there's a workout on this training day
            has_workout = any(w.date == current_date for w in workouts)
            if not has_workout:
                warning = {
                    "date": str(current_date),
                    "day": day_name,
                    "type": "missing_workout",
                    "message": f"Missing workout on training day {day_name}"
                }
                warnings.append(warning)
        current_date += timedelta(days=1)
    
    audit_result = {
        "status": "completed",
        "plan_id": plan.id,
        "race_date": str(plan.race_date),
        "total_workouts": len(workouts),
        "training_days": training_days,
        "violations": violations,
        "warnings": warnings,
        "recommendations": recommendations,
        "violation_count": len(violations),
        "warning_count": len(warnings)
    }
    
    print(f"🔍 AUDIT COMPLETE: {len(violations)} violations, {len(warnings)} warnings")
    
    return audit_result


def build_chunked_training_plan_prompt(
    data: dict, chunk_start_date: date, chunk_end_date: date,
    chunk_start_week: int, chunk_end_week: int, total_weeks: int, training_days: list[str]
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
        f"- Training days: {', '.join(training_days) if training_days else 'NOT SET'}",
        f"- Weight: {user.get('weight')} lbs",
    ]
    profile_text = "\n".join(filter(None, profile_section))

    # Phase-specific instructions with proper taper logic
    phase_instruction = ""
    if chunk_start_week < total_weeks * 0.4:
        phase_instruction = (
            "BASE BUILDING PHASE: Focus on aerobic base development through easy runs (Zone 2-3). "
            "Build weekly mileage gradually (10% rule). Include 1-2 tempo runs per week at marathon pace. "
            "Long runs should be 20-25% of weekly mileage. Priority: Volume over intensity."
        )
    elif chunk_start_week < total_weeks * 0.8:
        phase_instruction = (
            "BUILD PHASE: Increase intensity while maintaining base. Add speed work: "
            "intervals (5K-10K pace), longer tempo runs, hill work. Maintain 80/20 easy/hard ratio. "
            "Peak long runs (20-22 miles for marathon). Focus on race-specific training."
        )
    elif chunk_end_week >= total_weeks - 1:
        # Final week before race - strict taper
        phase_instruction = (
            "FINAL TAPER WEEK: Drastically reduce volume (30-50% of peak), easy runs only, "
            "NO long runs, NO hard efforts, NO intervals, NO tempo runs. Focus on freshness and recovery. "
            "Day before race should be REST or 1-2 mile easy shake-out only. "
            "Maintain running frequency but reduce duration and intensity significantly."
        )
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
        f"- Follow 80/20 rule: 80% easy runs (Zone 2-3), 20% hard efforts (Zone 4-5)\n"
        f"- Apply 10% rule: Don't increase weekly mileage by more than 10% from previous week\n"
        f"- Hard days hard, easy days easy - never consecutive hard days\n"
        f"- Include proper recovery days - rest is when adaptation happens\n"
        f"- For marathon training: Long runs should be 20-30% of weekly mileage\n"
        f"- Progressive overload: Gradually increase volume OR intensity, never both simultaneously\n"
        f"\n"
        f"🚨 CRITICAL TRAINING DAYS CONSTRAINT 🚨\n"
        f"ONLY schedule workouts on these specific days: {', '.join(training_days) if training_days else 'NOT SET'}\n"
        f"DO NOT schedule any workouts on other days (Sun, Tue, Fri)\n"
        f"Each week should have workouts on: {', '.join(training_days) if training_days else 'NOT SET'}\n"
        f"Rest days should be scheduled on non-training days\n"
        f"\n"
        f"- Return JSON with workouts array\n"
        f"- Each workout must include:\n"
        f"  * date (YYYY-MM-DD) - MUST be on training days only: {', '.join(training_days) if training_days else 'NOT SET'}\n"
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
        f"- Heart rate zones: Zone 1 (recovery), Zone 2-3 (easy), Zone 4 (hard), Zone 5 (very hard)"
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

# @file training_plan_validation.py
# @component PlanValidation
# @description: Validation logic for GPT-generated training plan JSON
# @features:
#   - Structural schema checks
#   - Date validation and uniqueness
#   - Workout type and intensity enforcement
#   - Logical rule checks (rest + workout required)
# @integration-points: training_plan_service.py
# @usage: Called before saving GPT plan to DB
# @prerequisites: Expects well-formed JSON structure from GPT

from datetime import datetime
from typing import List, Dict

# --- Constants ---
VALID_WORKOUT_TYPES = {"Rest", "Easy", "Long Run", "Tempo", "Intervals"}
VALID_INTENSITIES = {"None", "Low", "Moderate", "High"}


def validate_plan_json(plan_json: dict, race_date: str = None) -> List[str]:
    """
    Validates a GPT-generated training plan JSON before saving to DB.

    Args:
        plan_json (dict): Structured training plan.
        race_date (str): Optional cutoff date (YYYY-MM-DD) for workout dates.

    Returns:
        List[str]: List of validation errors. Empty if valid.
    """
    errors = []

    if "weeks" not in plan_json:
        return ["Missing 'weeks' in response"]

    if not isinstance(plan_json["weeks"], list):
        return ["'weeks' must be a list"]

    all_dates = set()
    workout_count = 0
    rest_count = 0

    for week in plan_json["weeks"]:
        if "workouts" not in week:
            errors.append("Week is missing 'workouts' field")
            continue

        if not isinstance(week["workouts"], list):
            errors.append("Workouts must be a list")
            continue

        for w in week["workouts"]:
            # --- Required fields ---
            for field in ["date", "workout_type", "miles"]:
                if field not in w:
                    errors.append(f"Missing '{field}' in workout")
                    continue

            # --- Date validation ---
            date_str = w.get("date")
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                if date_str in all_dates:
                    errors.append(f"Duplicate workout date: {date_str}")
                all_dates.add(date_str)

                if race_date:
                    race_cutoff = datetime.strptime(race_date, "%Y-%m-%d").date()
                    if date_obj > race_cutoff:
                        errors.append(
                            f"Workout on {date_str} is after race date ({race_date})"
                        )
            except Exception:
                errors.append(f"Invalid date format: {date_str}")

            # --- Workout type ---
            workout_type = w.get("workout_type")
            if workout_type not in VALID_WORKOUT_TYPES:
                errors.append(f"Invalid workout_type: {workout_type}")

            # --- Miles must be non-negative float ---
            miles = w.get("miles")
            if not isinstance(miles, (int, float)) or miles < 0:
                errors.append(f"Invalid miles: {miles}")

            # --- Intensity optional but validated if present ---
            intensity = w.get("intensity")
            if intensity and intensity not in VALID_INTENSITIES:
                errors.append(f"Invalid intensity: {intensity}")

            # --- Track counts ---
            if workout_type == "Rest":
                rest_count += 1
            else:
                workout_count += 1

    # --- Final logical constraints ---
    if workout_count == 0:
        errors.append("Plan must include at least one non-rest workout")
    if rest_count == 0:
        errors.append("Plan must include at least one rest day")

    return errors

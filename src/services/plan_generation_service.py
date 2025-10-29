# src/services/plan_generation_service.py

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any
from sqlalchemy.orm import Session

from src.utils.gpt_ops import get_gpt_response, parse_date_safe
from src.db.models.plan_workouts import PlanWorkout
from src.db.models.user_profile import UserProfile
from src.db.dao import plan_workouts_dao

logger = logging.getLogger(__name__)


def fetch_user_context(session: Session, user_id: str) -> Dict[str, Any]:
    """Fetch user profile and Strava activity data for GPT context."""
    # Get user profile
    profile = session.query(UserProfile).filter_by(user_id=user_id).first()

    context = {
        "user_profile": (
            {
                "age_group": profile.age_group if profile else None,
                "weight": profile.weight if profile else None,
                "height": (
                    {
                        "feet": profile.height_feet if profile else None,
                        "inches": profile.height_inches if profile else None,
                    }
                    if profile
                    else None
                ),
            }
            if profile
            else {}
        ),
        "strava_data": {
            "recent_weekly_mileage": 0,  # TODO: Calculate from Strava activities
            "longest_recent_run": 0,  # TODO: Calculate from Strava activities
            "base_level": "Unknown",  # TODO: Assess from activity history
        },
    }

    # TODO: Add actual Strava data fetching logic here
    # For now, return safe defaults for "Just Finish" goal

    return context


def generate_plan_with_gpt(
    plan_data: Dict[str, Any], user_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate training plan using GPT with Jack Daniels methodology."""

    # Build the prompt for GPT
    prompt = build_gpt_prompt(plan_data, user_context)

    # Call GPT to generate the plan
    logger.info("Calling GPT to generate training plan...")
    response = get_gpt_response(prompt, require_json=True)

    # Parse the JSON response
    import json

    plan_json = json.loads(response)

    logger.info(f"Generated plan with {len(plan_json.get('workouts', []))} workouts")

    return plan_json


def build_gpt_prompt(plan_data: Dict[str, Any], user_context: Dict[str, Any]) -> str:
    """Build the GPT prompt for generating a training plan."""

    race_date_str = plan_data["race_date"]
    race_date = (
        datetime.strptime(race_date_str, "%Y-%m-%d").date()
        if isinstance(race_date_str, str)
        else race_date_str
    )

    # Calculate weeks available
    today = date.today()
    weeks_available = (race_date - today).days // 7

    # Determine start date (next Monday or closest Monday to today)
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    start_date = today + timedelta(days=days_until_monday)

    prompt = f"""Generate a {weeks_available}-week marathon training plan using Jack Daniels methodology.

Race Details:
- Race Date: {race_date.strftime('%B %d, %Y')}
- Race Distance: {plan_data.get('race_distance', 'Marathon')}
- Race Name: {plan_data.get('race_name', 'N/A')}
- Race Location: {plan_data.get('race_location', 'N/A')}

Training Goal: {plan_data.get('primary_goal', 'Just Finish')}
Marathon Experience: {plan_data.get('marathon_experience', 'First')}
"""

    if plan_data.get("target_time"):
        prompt += f"- Target Time: {plan_data.get('target_time')}\n"

    prompt += f"""
Training Days: {', '.join(plan_data.get('training_days', []))}

User Context:
- Age Group: {user_context.get('user_profile', {}).get('age_group', 'Unknown')}
- Weight: {user_context.get('user_profile', {}).get('weight', 'Unknown')} lbs
- Height: {user_context.get('user_profile', {}).get('height', {}).get('feet', 'Unknown')}'{user_context.get('user_profile', {}).get('height', {}).get('inches', '')}"
- Weekly Mileage: {user_context.get('strava_data', {}).get('recent_weekly_mileage', 0)} miles
- Longest Run: {user_context.get('strava_data', {}).get('longest_recent_run', 0)} miles

Generate a complete training plan starting {start_date.strftime('%B %d, %Y')}.

Return JSON in this format:
{{
  "plan_name": "Marathon Training Plan - [Race Name]",
  "start_date": "{start_date.strftime('%Y-%m-%d')}",
  "race_date": "{race_date.strftime('%Y-%m-%d')}",
  "workouts": [
    {{
      "date": "YYYY-MM-DD",
      "workout_type": "Easy Run",
      "description": "X miles at easy pace (60-70% max heart rate)",
      "miles": 3.0,
      "intensity": "Easy",
      "target_zone": "Z1-Z2",
      "focus": "Build aerobic base"
    }}
  ]
}}

Important:
- Schedule workouts ONLY on the specified training days
- Progressively increase long run distance
- Include 2-3 quality workouts per week
- Taper in the final 2 weeks
- No workouts in race week (only easy runs or rest)
"""

    return prompt


def save_workouts(
    session: Session, plan_id: int, workouts: List[Dict[str, Any]]
) -> None:
    """Save generated workouts to the database."""

    workouts_to_insert = []
    for workout in workouts:
        workout_date = (
            datetime.strptime(workout["date"], "%Y-%m-%d").date()
            if isinstance(workout["date"], str)
            else workout["date"]
        )

        workouts_to_insert.append(
            {
                "plan_id": plan_id,
                "date": workout_date,
                "workout_type": workout.get("workout_type", "Easy Run"),
                "description": workout.get("description", ""),
                "miles": float(workout.get("miles", 0)),
                "intensity": workout.get("intensity", "Easy"),
                "target_zone": workout.get("target_zone"),
                "target_hr": workout.get("target_hr"),
                "focus": workout.get("focus"),
                "segments": workout.get("segments"),  # JSON field
            }
        )

    # Insert workouts
    plan_workouts_dao.insert_batch(session, workouts_to_insert)
    session.commit()

    logger.info(f"Saved {len(workouts_to_insert)} workouts to plan {plan_id}")


def create_training_plan(
    session: Session, user_id: str, plan_data: Dict[str, Any]
) -> int:
    """Create a new training plan with workouts.

    Returns:
        plan_id of the newly created plan
    """

    try:
        # Fetch user context (profile + Strava data)
        user_context = fetch_user_context(session, user_id)

        # Generate plan with GPT
        gpt_plan = generate_plan_with_gpt(plan_data, user_context)

        # Create plan record
        from src.db.dao.plans_dao import create_plan
        from src.db.models.plans import Plan

        # Prepare plan data
        race_date = plan_data["race_date"]
        if isinstance(race_date, str):
            race_date = datetime.strptime(race_date, "%Y-%m-%d").date()

        plan_dict = {
            "user_id": user_id,
            "plan_name": gpt_plan.get(
                "plan_name", f"Marathon Training Plan - {race_date}"
            ),
            "race_date": race_date,
            "race_distance": plan_data.get("race_distance", "Marathon"),
            "race_name": plan_data.get("race_name"),
            "race_location": plan_data.get("race_location"),
            "primary_goal": plan_data.get("primary_goal"),
            "marathon_experience": plan_data.get("marathon_experience"),
            "target_time": plan_data.get("target_time"),
            "training_days": plan_data.get("training_days"),
            "notes": plan_data.get("notes"),
            "is_active": True,
        }

        # Create the plan
        plan = create_plan(session, plan_dict)
        session.flush()  # Get the plan_id

        # Deactivate any existing active plans for this user
        session.query(Plan).filter_by(user_id=user_id, is_active=True).update(
            {"is_active": False}
        )

        # Save workouts
        save_workouts(session, plan.id, gpt_plan.get("workouts", []))

        session.commit()

        logger.info(f"Created training plan {plan.id} for user {user_id}")

        return plan.id

    except Exception as e:
        session.rollback()
        logger.error(f"Error creating training plan: {e}")
        raise

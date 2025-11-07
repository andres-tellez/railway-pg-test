"""
Script to show next week's plan before and after analysis from this week.

This demonstrates how flexible matching affects the analysis and resulting adjustments.
"""

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Load environment variables FIRST (before any imports that need DATABASE_URL)
from dotenv import load_dotenv

project_root = Path(__file__).parent
env_local_path = project_root / ".env.local"
if env_local_path.exists():
    load_dotenv(env_local_path, override=True)
else:
    env_staging_path = project_root / ".env.staging"
    if env_staging_path.exists():
        load_dotenv(env_staging_path, override=True)
    else:
        load_dotenv()  # Try default .env

# Add project root to path
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.services.training_plan.weekly_rebuild_service import WeeklyRebuildService
from src.utils.date_helpers import get_next_monday, DAY_NAMES_FULL
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def format_workout_for_display(workout: dict) -> str:
    """Format a workout dict for display in table."""
    day = workout.get("day", "?")
    workout_type = workout.get("workout_type", "?")
    miles = workout.get("miles", 0)
    target_zone = workout.get("target_zone", "")

    # Shorten workout type names
    type_map = {
        "Easy": "Easy",
        "Steady": "Steady",
        "Endurance": "Endurance",
        "Long": "Long",
    }
    type_short = type_map.get(workout_type, workout_type)

    # Format target zone (remove "Target Pace Zone: " prefix if present)
    zone_display = (
        target_zone.replace("Target Pace Zone: ", "").strip() if target_zone else "-"
    )

    return f"{day:12} | {type_short:10} | {miles:5.1f} mi | {zone_display}"


def get_user_plan(session):
    """Get the active plan for the user (assumes single active plan)."""
    # Get first active plan (you may need to filter by user_id)
    plan = session.query(Plan).filter_by(is_active=True).first()
    if not plan:
        print("ERROR: No active plan found")
        sys.exit(1)
    return plan


def main():
    print("=" * 80)
    print("NEXT WEEK PLAN COMPARISON (Before vs After Analysis)")
    print("=" * 80)
    print()

    session = SessionLocal()

    try:
        # Get user's plan
        plan = get_user_plan(session)
        print(f"Plan ID: {plan.id}")
        print(f"Race Date: {plan.race_date}")
        print()

        # Calculate next week (when scheduler runs on Sunday, next week starts Monday)
        today = date.today()
        next_monday = get_next_monday(today)

        # Find next week number by finding which week contains next_monday
        all_workouts = (
            session.query(PlanWorkout)
            .filter_by(plan_id=plan.id)
            .order_by(PlanWorkout.date)
            .all()
        )

        # Find the week that contains next_monday
        next_week_num = None
        for workout in all_workouts:
            # Calculate week number (weeks before race)
            from datetime import timedelta

            weeks_before_race = (plan.race_date - workout.date).days // 7

            # Check if workout date is in the week containing next_monday
            from src.utils.date_helpers import get_week_start_for_date

            workout_week_start = get_week_start_for_date(workout.date)
            next_week_start = get_week_start_for_date(next_monday)

            if workout_week_start == next_week_start:
                next_week_num = weeks_before_race
                break

        if next_week_num is None:
            print("ERROR: Could not find next week in plan")
            sys.exit(1)

        print(f"This Week (completed): {today.strftime('%Y-%m-%d')} (Sunday)")
        print(
            f"Next Week (Monday-Sunday): {next_monday.strftime('%Y-%m-%d')} - {(next_monday + timedelta(days=6)).strftime('%Y-%m-%d')}"
        )
        print(f"Next Week Number: {next_week_num}")
        print()

        # Get original workouts for next week (before rebuild)
        next_week_workouts = [
            w
            for w in all_workouts
            if next_monday <= w.date <= (next_monday + timedelta(days=6))
        ]

        print("STEP 1: Original Plan for Next Week (Before Analysis)")
        print("-" * 80)
        if not next_week_workouts:
            print("No workouts found for next week")
        else:
            print(f"{'Day':12} | {'Type':10} | {'Miles':7} | Target Pace Zone")
            print("-" * 80)
            for workout in sorted(next_week_workouts, key=lambda w: w.date):
                day_name = DAY_NAMES_FULL[workout.date.weekday()]
                print(
                    f"{day_name:12} | {workout.workout_type or 'Easy':10} | {workout.miles or 0:7.1f} | {workout.target_zone or '-'}"
                )
        print()

        # Run rebuild to see what changes
        print("STEP 2: Analyzing this week's performance (with flexible matching)...")
        print("-" * 80)

        rebuild_service = WeeklyRebuildService()
        rebuild_result = rebuild_service.rebuild_week(
            session=session,
            plan_id=plan.id,
            week_num=next_week_num,
        )

        # Extract original and updated workouts from rebuild result
        original_workouts = rebuild_result.get("original_workouts", [])
        updated_workouts = rebuild_result.get("updated_workouts", [])
        adjustment_decision = rebuild_result.get("adjustment_decision")

        print()
        print("STEP 3: Analysis Results")
        print("-" * 80)
        if adjustment_decision:
            print(f"Decision Type: {adjustment_decision.decision_type}")
            print(f"Volume Change: {adjustment_decision.volume_change_pct:.1f}%")
            print(
                f"Pace Adjustment: {adjustment_decision.pace_adjustment_sec:.1f} sec/mile"
            )
            if hasattr(adjustment_decision, "disable_quality_workouts"):
                print(
                    f"Quality Workouts Disabled: {adjustment_decision.disable_quality_workouts}"
                )
        else:
            print("No adjustment decision (first week or no previous week data)")
        print()

        print("STEP 4: Updated Plan for Next Week (After Analysis)")
        print("-" * 80)
        if not updated_workouts:
            print("No workouts found after rebuild")
        else:
            print(f"{'Day':12} | {'Type':10} | {'Miles':7} | Target Pace Zone")
            print("-" * 80)
            for workout in sorted(updated_workouts, key=lambda w: w.get("date", "")):
                day_name = workout.get("day", "?")
                workout_type = workout.get("workout_type", "?")
                miles = workout.get("miles", 0)
                target_zone = workout.get("target_zone", "-")
                print(
                    f"{day_name:12} | {workout_type:10} | {miles:7.1f} | {target_zone}"
                )
        print()

        # Compare changes
        print("STEP 5: Changes Summary")
        print("-" * 80)

        # Create maps by day for easier comparison
        original_by_day = {w.get("day", "?"): w for w in original_workouts}
        updated_by_day = {w.get("day", "?"): w for w in updated_workouts}

        changes_found = False
        for day in DAY_NAMES_FULL:
            original = original_by_day.get(day)
            updated = updated_by_day.get(day)

            if original and updated:
                # Check for changes
                changes = []
                if original.get("miles", 0) != updated.get("miles", 0):
                    changes.append(
                        f"Distance: {original.get('miles', 0):.1f} -> {updated.get('miles', 0):.1f} mi"
                    )
                if original.get("workout_type", "") != updated.get("workout_type", ""):
                    changes.append(
                        f"Type: {original.get('workout_type', '')} -> {updated.get('workout_type', '')}"
                    )
                if original.get("target_zone", "") != updated.get("target_zone", ""):
                    orig_zone = (
                        original.get("target_zone", "")
                        .replace("Target Pace Zone: ", "")
                        .strip()
                    )
                    upd_zone = (
                        updated.get("target_zone", "")
                        .replace("Target Pace Zone: ", "")
                        .strip()
                    )
                    if orig_zone != upd_zone:
                        changes.append(f"Pace Zone: {orig_zone} -> {upd_zone}")

                if changes:
                    changes_found = True
                    print(f"{day}:")
                    for change in changes:
                        print(f"  - {change}")
            elif original:
                print(f"{day}: Workout removed")
                changes_found = True
            elif updated:
                print(f"{day}: New workout added")
                changes_found = True

        if not changes_found:
            print("No changes detected - plan remains the same")

        print()
        print("=" * 80)
        print("Analysis complete!")
        print("=" * 80)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()

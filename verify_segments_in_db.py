#!/usr/bin/env python3
"""
Verify that workout segments are being saved to plan_workouts table.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first (before any imports that use them)
env_path = Path(__file__).parent / ".env.local"
load_dotenv(env_path)

from datetime import date, timedelta
from src.db.db_session import get_db
from src.db.dao.plan_workouts_dao import get_workouts_for_week
from src.utils.date_helpers import get_previous_completed_week_range, get_next_monday
import json


def verify_segments():
    """Check if segments exist in plan_workouts for the next week."""
    db = next(get_db())

    try:
        # Get the active plan (assuming plan_id = 1 for now, adjust if needed)
        plan_id = 1  # TODO: Get from environment or user input if needed

        # Calculate next week (Mon-Sun)
        today = date.today()
        next_monday = get_next_monday(today)
        next_sunday = next_monday + timedelta(days=6)

        print(f"Checking plan_workouts for Plan ID: {plan_id}")
        print(f"Next week range: {next_monday} to {next_sunday}")
        print("-" * 80)

        # Fetch workouts for next week
        workouts = get_workouts_for_week(db, plan_id, next_monday, next_sunday)

        if not workouts:
            print("WARNING: No workouts found for next week!")
            return

        print(f"Found {len(workouts)} workouts for next week:\n")

        for workout in workouts:
            segments = workout.segments
            has_segments = segments is not None

            print(f"Date: {workout.date} ({workout.date.strftime('%A')})")
            print(f"Type: {workout.workout_type}")
            print(f"Distance: {workout.miles:.1f} mi")
            print(f"Has Segments: {'YES' if has_segments else 'NO'}")

            if has_segments:
                # Parse segments if it's a string (SQLite)
                if isinstance(segments, str):
                    try:
                        segments = json.loads(segments)
                    except json.JSONDecodeError:
                        print("  WARNING: Segments is a string but not valid JSON")
                        print(f"  Raw value: {segments[:100]}...")
                        print()
                        continue

                # Display segment structure
                if isinstance(segments, dict):
                    steps = segments.get("steps", [])
                    target_type = segments.get("targetType", "N/A")
                    units = segments.get("units", "N/A")

                    print(f"  Structure: {len(steps)} steps")
                    print(f"  Target Type: {target_type}")
                    print(f"  Units: {units}")
                    print(f"  Steps breakdown:")

                    for i, step in enumerate(steps, 1):
                        name = step.get("name", "Unknown")
                        value = step.get("value", 0)
                        duration_type = step.get("durationType", "N/A")
                        target = step.get("target", {})
                        intensity = step.get("intensity", "N/A")

                        # Format target pace
                        if isinstance(target, dict):
                            low = target.get("low", 0)
                            high = target.get("high", 0)
                            if low and high:
                                # Convert seconds to MM:SS/mi
                                low_min = int(low // 60)
                                low_sec = int(low % 60)
                                high_min = int(high // 60)
                                high_sec = int(high % 60)
                                if low_min == high_min and low_sec == high_sec:
                                    pace_str = f"{low_min}:{low_sec:02d}/mi"
                                else:
                                    pace_str = f"{low_min}:{low_sec:02d}-{high_min}:{high_sec:02d}/mi"
                            else:
                                pace_str = "N/A"
                        else:
                            pace_str = str(target) if target else "N/A"

                        print(
                            f"    {i}. {name}: {value:.2f} {duration_type.lower()} @ {pace_str} ({intensity})"
                        )
                else:
                    print(f"  WARNING: Segments is not a dict: {type(segments)}")
            else:
                print("  WARNING: No segments data stored")

            print()

        print("-" * 80)
        print(
            f"Summary: {sum(1 for w in workouts if w.segments)}/{len(workouts)} workouts have segments"
        )

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    verify_segments()

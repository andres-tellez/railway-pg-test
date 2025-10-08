import sys

sys.path.append(".")
from src.services.training_plan_service import generate_plan_with_b_plus_validation
from src.db.db_session import get_session
from datetime import date
import uuid

# Test Jack Daniels plan generation
session = get_session()
user_id = uuid.UUID("d63757b0-1b02-4d05-8fd2-a04fccf91630")  # Your user ID
race_date = date(2025, 11, 15)  # November 15, 2025
race_distance = "Marathon"

print("TESTING JACK DANIELS RUNNING FORMULA TRAINING PLAN")
print("=" * 60)
print(f"User ID: {user_id}")
print(f"Race: {race_distance} on {race_date}")
print("=" * 60)

try:
    plan = generate_plan_with_b_plus_validation(
        session, user_id, race_date, race_distance
    )
    print(f"\\nSUCCESS! Plan generated successfully!")
    print(f"Plan ID: {plan.id}")
    print(f"Created: {plan.created_at}")
    print(f"Grade: {plan.overall_grade}")
    print(f"Score: {plan.score}/100")
    print(f"Safety: {plan.safety_rating}")

    # Show some workout details
    workouts = plan.workouts[:15]  # First 15 workouts
    print(f"\\nFirst 15 workouts:")
    for w in workouts:
        day_name = w.date.strftime("%a")
        print(
            f"  {w.date} ({day_name}): {w.miles} miles {w.workout_type} - {w.focus} ({w.intensity})"
        )

    # Show long runs
    long_runs = [w for w in plan.workouts if w.workout_type == "Long Run"]
    print(f"\\nLong Runs ({len(long_runs)} total):")
    for w in long_runs:
        day_name = w.date.strftime("%a")
        print(f"  {w.date} ({day_name}): {w.miles} miles - {w.focus}")

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
finally:
    session.close()

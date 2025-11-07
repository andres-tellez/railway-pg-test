"""Check run types assigned to each day."""

import sys
import os
import importlib.util

# Load modules directly to avoid DB dependencies
spec_weekly = importlib.util.spec_from_file_location(
    "weekly_total_calculator",
    os.path.join(
        os.path.dirname(__file__),
        "src",
        "services",
        "training_plan",
        "weekly_total_calculator.py",
    ),
)
weekly_module = importlib.util.module_from_spec(spec_weekly)
spec_weekly.loader.exec_module(weekly_module)

spec_pass3 = importlib.util.spec_from_file_location(
    "pass3_workout_distribution",
    os.path.join(
        os.path.dirname(__file__),
        "src",
        "services",
        "training_plan",
        "pass3_workout_distribution.py",
    ),
)
pass3_module = importlib.util.module_from_spec(spec_pass3)
spec_pass3.loader.exec_module(pass3_module)

calculate_weekly_totals_from_long_runs = (
    weekly_module.calculate_weekly_totals_from_long_runs
)
Pass3WorkoutDistribution = pass3_module.Pass3WorkoutDistribution

# Test with 4 days: Mon, Wed, Thu, Sat
weeks_lr = [
    {"week_number": 1, "phase": "Base", "long_run_miles": 15.0},
    {"week_number": 2, "phase": "Base", "long_run_miles": 16.0},
    {"week_number": 3, "phase": "Build", "long_run_miles": 17.0},
]

print("Checking run types assigned to each day")
print("=" * 70)

training_days = ["Mon", "Wed", "Thu", "Sat"]
runs_per_week = len(training_days)

# Calculate weekly totals
weeks_with_totals = calculate_weekly_totals_from_long_runs(weeks_lr, runs_per_week)

# Generate workouts
pass3 = Pass3WorkoutDistribution()
pass3_result = pass3.run(weeks_with_totals, training_days)

print("\nWeek | Mon | Wed | Thu | Sat")
print("-" * 50)

for w in pass3_result["weeks"]:
    workouts_by_day = {wk["day"]: wk for wk in w["workouts"]}

    mon = workouts_by_day.get("Mon", {})
    wed = workouts_by_day.get("Wed", {})
    thu = workouts_by_day.get("Thu", {})
    sat = workouts_by_day.get("Sat", {})

    mon_str = (
        f"{mon.get('distance_miles', 0):.1f} mi ({mon.get('workout_type', 'N/A')})"
    )
    wed_str = (
        f"{wed.get('distance_miles', 0):.1f} mi ({wed.get('workout_type', 'N/A')})"
    )
    thu_str = (
        f"{thu.get('distance_miles', 0):.1f} mi ({thu.get('workout_type', 'N/A')})"
    )
    sat_str = (
        f"{sat.get('distance_miles', 0):.1f} mi ({sat.get('workout_type', 'N/A')})"
    )

    print(
        f"{w['week_number']:>4} | {mon_str:>25} | {wed_str:>25} | {thu_str:>25} | {sat_str:>25}"
    )

print("\n" + "=" * 70)
print("Expected pattern:")
print("  Monday:    Easy Run (shortest, recovery after Saturday's long run)")
print("  Wednesday: Easy/Tempo or Medium Run (medium)")
print("  Thursday:  Medium Run (longest weekday run)")
print("  Saturday:  Long Run")

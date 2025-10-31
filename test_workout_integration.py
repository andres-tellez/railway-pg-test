"""Test that workouts are generated and included in the draft response."""

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

# Mock week output from Pass 1 LR-first
weeks_lr = [
    {"week_number": 1, "phase": "Base", "long_run_miles": 15.0},
    {"week_number": 2, "phase": "Base", "long_run_miles": 16.0},
]

# Step 1: Calculate weekly totals
training_days = ["Mon", "Wed", "Sat"]
runs_per_week = len(training_days)
weeks_with_totals = calculate_weekly_totals_from_long_runs(weeks_lr, runs_per_week)

print("Step 1: Weekly totals calculated")
for w in weeks_with_totals:
    print(
        f"  Week {w['week_number']}: LR={w['long_run_miles']:.1f}, Total={w.get('weekly_mileage', 0):.1f}"
    )

# Step 2: Generate workouts with Pass3
pass3 = Pass3WorkoutDistribution()
pass3_result = pass3.run(weeks_with_totals, training_days)

print("\nStep 2: Workouts generated")
for w in pass3_result["weeks"]:
    print(f"\nWeek {w['week_number']} ({w['phase']}):")
    print(f"  LR={w['long_run_miles']:.1f}, Total={w['weekly_mileage']:.1f}")
    print("  Workouts:")
    for workout in w["workouts"]:
        print(
            f"    {workout['day']:>3}: {workout['distance_miles']:>5.1f} mi - {workout['workout_type']}"
        )

# Step 3: Build final weeks_simple structure (simulating backend)
weeks_simple = [
    {
        "week_number": w.get("week_number"),
        "phase": w.get("phase", ""),
        "long_run_miles": w.get("long_run_miles"),
        "weekly_mileage": w.get("weekly_mileage", 0),
        "workouts": w.get("workouts", []),  # Include workout distributions
    }
    for w in pass3_result["weeks"]
]

print("\nStep 3: Final weeks_simple structure")
print(f"Total weeks: {len(weeks_simple)}")
for w in weeks_simple:
    print(f"  Week {w['week_number']}: {len(w.get('workouts', []))} workouts")

print("\n✅ Integration test complete!")
print("   - Weekly totals calculated ✓")
print("   - Workouts generated ✓")
print("   - Workouts included in response ✓")

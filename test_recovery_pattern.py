"""Test recovery pattern: Monday (shortest) → Wednesday (medium) → Thursday (longest)."""

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
]

print("Testing recovery pattern with 4 days (Mon, Wed, Thu, Sat)")
print("=" * 70)

training_days = ["Mon", "Wed", "Thu", "Sat"]
runs_per_week = len(training_days)

# Calculate weekly totals
weeks_with_totals = calculate_weekly_totals_from_long_runs(weeks_lr, runs_per_week)

print("\nStep 1: Weekly totals calculated")
for w in weeks_with_totals:
    print(
        f"  Week {w['week_number']}: LR={w['long_run_miles']:.1f}, Total={w.get('weekly_mileage', 0):.1f}"
    )

# Generate workouts
pass3 = Pass3WorkoutDistribution()
pass3_result = pass3.run(weeks_with_totals, training_days)

print("\nStep 2: Workouts generated (recovery pattern)")
print("-" * 70)
for w in pass3_result["weeks"]:
    print(f"\nWeek {w['week_number']} ({w['phase']}):")
    print(f"  LR={w['long_run_miles']:.1f}, Total={w['weekly_mileage']:.1f}")
    print("  Workouts:")

    # Sort by day order for display
    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    workouts_sorted = sorted(
        w["workouts"],
        key=lambda x: day_order.index(x["day"]) if x["day"] in day_order else 99,
    )

    for workout in workouts_sorted:
        day = workout["day"]
        miles = workout["distance_miles"]
        wtype = workout["workout_type"]
        print(f"    {day:>3}: {miles:>5.1f} mi - {wtype}")

# Verify pattern: Mon < Wed < Thu
print("\n" + "=" * 70)
print("Verification: Recovery Pattern")
print("-" * 70)

for w in pass3_result["weeks"]:
    workouts_by_day = {wk["day"]: wk["distance_miles"] for wk in w["workouts"]}

    mon = workouts_by_day.get("Mon", 0)
    wed = workouts_by_day.get("Wed", 0)
    thu = workouts_by_day.get("Thu", 0)
    sat = workouts_by_day.get("Sat", 0)

    print(f"Week {w['week_number']}:")
    print(f"  Monday:    {mon:.1f} mi")
    print(f"  Wednesday: {wed:.1f} mi")
    print(f"  Thursday:  {thu:.1f} mi")
    print(f"  Saturday:  {sat:.1f} mi (LR)")

    # Verify: Monday should be shortest, Thursday should be longest
    if mon <= wed <= thu:
        print(
            f"  ✅ Pattern correct: Mon ({mon:.1f}) ≤ Wed ({wed:.1f}) ≤ Thu ({thu:.1f})"
        )
    else:
        print(
            f"  ❌ Pattern incorrect: Mon ({mon:.1f}) vs Wed ({wed:.1f}) vs Thu ({thu:.1f})"
        )

print("\n✅ Test complete!")

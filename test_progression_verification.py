"""Test that distances increase: Mon < Wed < Thu."""

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

# Test with multiple weeks including recovery weeks
weeks_lr = [
    {"week_number": 1, "phase": "Base", "long_run_miles": 15.0},
    {"week_number": 2, "phase": "Build", "long_run_miles": 17.0},
    {"week_number": 3, "phase": "Build", "long_run_miles": 12.0},  # Cutback
    {
        "week_number": 4,
        "phase": "Recovery",
        "long_run_miles": 15.0,
        "weekly_mileage": 38.0,
    },  # Recovery week
]

print("Testing progression: Mon < Wed < Thu")
print("=" * 70)

training_days = ["Mon", "Wed", "Thu", "Sat"]
runs_per_week = len(training_days)

# Calculate weekly totals for non-recovery weeks
weeks_input = []
for w in weeks_lr:
    if w.get("phase") == "Recovery":
        # Recovery week already has totals
        weeks_input.append(w)
    else:
        weeks_input.append(w)

# Calculate totals for weeks that need it
weeks_with_totals = calculate_weekly_totals_from_long_runs(
    [
        w
        for w in weeks_input
        if w.get("phase") != "Recovery" or not w.get("weekly_mileage")
    ],
    runs_per_week,
)

# Merge recovery weeks that already have totals
recovery_weeks = {
    i: w
    for i, w in enumerate(weeks_input)
    if w.get("phase") == "Recovery" and w.get("weekly_mileage")
}
for i, w in recovery_weeks.items():
    if i < len(weeks_with_totals):
        weeks_with_totals.insert(i, w)

# Generate workouts
pass3 = Pass3WorkoutDistribution()
pass3_result = pass3.run(weeks_with_totals, training_days)

print("\nWeek | Phase | Mon | Wed | Thu | Sat | Progression")
print("-" * 70)

all_correct = True
for w in pass3_result["weeks"]:
    workouts_by_day = {wk["day"]: wk["distance_miles"] for wk in w["workouts"]}

    mon = workouts_by_day.get("Mon", 0)
    wed = workouts_by_day.get("Wed", 0)
    thu = workouts_by_day.get("Thu", 0)
    sat = workouts_by_day.get("Sat", 0)

    progression_ok = mon < wed < thu
    if not progression_ok:
        all_correct = False

    status = "✅" if progression_ok else "❌"

    print(
        f"{w['week_number']:>4} | {w['phase']:>6} | {mon:>3.1f} | {wed:>3.1f} | {thu:>3.1f} | {sat:>3.1f} | {status}"
    )

print("\n" + "=" * 70)
if all_correct:
    print("✅ All weeks show proper progression: Mon < Wed < Thu")
else:
    print("❌ Some weeks don't show proper progression")

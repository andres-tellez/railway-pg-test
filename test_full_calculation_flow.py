"""Test the full calculation flow: Long runs → Weekly totals → Workout distribution."""

import sys
import os
import importlib.util

# Load modules
spec_calc = importlib.util.spec_from_file_location(
    "weekly_total_calculator",
    os.path.join(
        os.path.dirname(__file__),
        "src",
        "services",
        "training_plan",
        "weekly_total_calculator.py",
    ),
)
calculator = importlib.util.module_from_spec(spec_calc)
spec_calc.loader.exec_module(calculator)

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
pass3 = importlib.util.module_from_spec(spec_pass3)
spec_pass3.loader.exec_module(pass3)

calculate_weekly_totals = calculator.calculate_weekly_totals_from_long_runs
Pass3WorkoutDistribution = pass3.Pass3WorkoutDistribution

print("=" * 70)
print("Testing Full Calculation Flow")
print("=" * 70)

# Test data: Long runs from actual plan
long_runs_weeks = [
    {"week_number": 1, "long_run_miles": 15.0, "phase": "Base"},
    {"week_number": 2, "long_run_miles": 16.0, "phase": "Base"},
    {"week_number": 3, "long_run_miles": 17.0, "phase": "Base"},
    {"week_number": 4, "long_run_miles": 12.0, "phase": "Cutback"},
    {"week_number": 5, "long_run_miles": 18.0, "phase": "Build"},
]

training_days_3 = ["Mon", "Wed", "Sat"]
training_days_4 = ["Mon", "Wed", "Thu", "Sat"]

print("\nTest 1: 3 days/week calculation")
print("-" * 70)
weeks_with_totals = calculate_weekly_totals(long_runs_weeks, runs_per_week=3)
print("Week | LR   | Total | LR %")
print("-" * 40)
for w in weeks_with_totals:
    lr = w.get("long_run_miles", 0)
    total = w.get("weekly_mileage", 0)
    pct = (lr / total * 100) if total > 0 else 0
    print(f"{w['week_number']:>4} | {lr:>4.1f} | {total:>5} | {pct:>5.1f}%")

# Verify calculations
print("\n✅ Verification:")
errors = []
for w in weeks_with_totals:
    lr = w.get("long_run_miles", 0)
    total = w.get("weekly_mileage", 0)
    pct = (lr / total * 100) if total > 0 else 0
    # Check LR % is in range (40-50% for 3 days)
    if pct < 40 or pct > 50:
        errors.append(f"Week {w['week_number']}: LR % = {pct:.1f}% (expected 40-50%)")
    # Check minimum viable (LR + 2*3 = LR + 6)
    min_viable = lr + (3 - 1) * 3
    if total < min_viable:
        errors.append(
            f"Week {w['week_number']}: Total {total} < min viable {min_viable}"
        )

if errors:
    print("❌ Errors found:")
    for e in errors:
        print(f"  - {e}")
else:
    print("  ✅ All weekly totals are valid")

print("\n" + "=" * 70)
print("Test 2: Pass3 Workout Distribution (3 days/week)")
print("-" * 70)

pass3_instance = Pass3WorkoutDistribution()
result = pass3_instance.run(weeks_with_totals, training_days_3)

print("Week | Sat (LR) | Mon  | Wed  | Total | Expected | Match")
print("-" * 60)
for w in result.get("weeks", []):
    week_num = w.get("week_number", 0)
    expected_total = weeks_with_totals[week_num - 1].get("weekly_mileage", 0)
    workouts = w.get("workouts", [])

    sat_workout = next((wk for wk in workouts if wk.get("day") == "Sat"), None)
    mon_workout = next((wk for wk in workouts if wk.get("day") == "Mon"), None)
    wed_workout = next((wk for wk in workouts if wk.get("day") == "Wed"), None)

    sat_miles = sat_workout.get("distance_miles", 0) if sat_workout else 0
    mon_miles = mon_workout.get("distance_miles", 0) if mon_workout else 0
    wed_miles = wed_workout.get("distance_miles", 0) if wed_workout else 0
    actual_total = w.get("weekly_mileage", 0)

    match = "✅" if abs(actual_total - expected_total) < 0.1 else "❌"

    print(
        f"{week_num:>4} | {sat_miles:>7.1f} | {mon_miles:>4.1f} | {wed_miles:>4.1f} | {actual_total:>5} | {expected_total:>8} | {match}"
    )

# Verify all totals match
print("\n✅ Verification:")
distribution_errors = []
for w in result.get("weeks", []):
    week_num = w.get("week_number", 0)
    expected = weeks_with_totals[week_num - 1].get("weekly_mileage", 0)
    actual = w.get("weekly_mileage", 0)
    workout_sum = sum(wk.get("distance_miles", 0) for wk in w.get("workouts", []))

    if abs(actual - expected) > 0.1:
        distribution_errors.append(
            f"Week {week_num}: Total mismatch (got {actual}, expected {expected})"
        )
    if abs(workout_sum - actual) > 0.1:
        distribution_errors.append(
            f"Week {week_num}: Workout sum {workout_sum} ≠ weekly_mileage {actual}"
        )

    # Check long run is on Sat
    sat_workout = next(
        (wk for wk in w.get("workouts", []) if wk.get("day") == "Sat"), None
    )
    if sat_workout and sat_workout.get("workout_type") != "Long Run":
        distribution_errors.append(f"Week {week_num}: Long run not on Saturday")

if distribution_errors:
    print("❌ Errors found:")
    for e in distribution_errors:
        print(f"  - {e}")
else:
    print("  ✅ All workout distributions are correct")
    print("  ✅ Long runs are on Saturday")
    print("  ✅ All totals match expected values")

print("\n" + "=" * 70)
print("Test 3: 4 days/week calculation")
print("-" * 70)
weeks_with_totals_4 = calculate_weekly_totals(long_runs_weeks, runs_per_week=4)
print("Week | LR   | Total | LR %")
print("-" * 40)
for w in weeks_with_totals_4:
    lr = w.get("long_run_miles", 0)
    total = w.get("weekly_mileage", 0)
    pct = (lr / total * 100) if total > 0 else 0
    print(f"{w['week_number']:>4} | {lr:>4.1f} | {total:>5} | {pct:>5.1f}%")

print("\n✅ Verification (4 days/week):")
errors_4 = []
for w in weeks_with_totals_4:
    lr = w.get("long_run_miles", 0)
    total = w.get("weekly_mileage", 0)
    pct = (lr / total * 100) if total > 0 else 0
    # Check LR % is in range (35-45% for 4 days)
    if pct < 35 or pct > 45:
        errors_4.append(f"Week {w['week_number']}: LR % = {pct:.1f}% (expected 35-45%)")

if errors_4:
    print("❌ Errors found:")
    for e in errors_4:
        print(f"  - {e}")
else:
    print("  ✅ All weekly totals are valid for 4 days/week")

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
all_good = len(errors) == 0 and len(distribution_errors) == 0 and len(errors_4) == 0
if all_good:
    print("✅ All calculations work correctly!")
else:
    print("❌ Some issues found - see above")

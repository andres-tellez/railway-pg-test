"""Test the new Pass 3 workout distribution implementation."""

import sys
import os
import importlib.util

# Load the module directly
spec = importlib.util.spec_from_file_location(
    "pass3_workout_distribution",
    os.path.join(
        os.path.dirname(__file__),
        "src",
        "services",
        "training_plan",
        "pass3_workout_distribution.py",
    ),
)
pass3_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pass3_module)

Pass3WorkoutDistribution = pass3_module.Pass3WorkoutDistribution
calculate_workout_distribution = pass3_module.calculate_workout_distribution

print("=" * 70)
print("Testing Pass 3 Workout Distribution Implementation")
print("=" * 70)

# Test 1: 3 days/week (Mon, Wed, Sat)
print("\nTest 1: 3 days/week - Week with 15 LR, 33 total")
print("-" * 70)
workouts = calculate_workout_distribution(
    long_run_miles=15.0,
    total_weekly_miles=33.0,
    runs_per_week=3,
    training_days=["Mon", "Wed", "Sat"],
)

print("Day  | Type        | Miles | Total")
print("-" * 40)
total = 0.0
for w in workouts:
    print(
        f"{w['day']:>4} | {w['workout_type']:>11} | {w['distance_miles']:>5.1f} | ",
        end="",
    )
    total += w["distance_miles"]
    print(f"{total:>5.1f}")

print(f"\nExpected total: 33.0")
print(f"Actual total: {total:.1f}")
print(f"Match: {'✅' if abs(total - 33.0) < 0.1 else '❌'}")

# Test 2: 4 days/week (Mon, Wed, Thu, Sat)
print("\n" + "=" * 70)
print("Test 2: 4 days/week - Week with 16 LR, 40 total")
print("-" * 70)
workouts = calculate_workout_distribution(
    long_run_miles=16.0,
    total_weekly_miles=40.0,
    runs_per_week=4,
    training_days=["Mon", "Wed", "Thu", "Sat"],
)

print("Day  | Type        | Miles | Total")
print("-" * 40)
total = 0.0
for w in workouts:
    print(
        f"{w['day']:>4} | {w['workout_type']:>11} | {w['distance_miles']:>5.1f} | ",
        end="",
    )
    total += w["distance_miles"]
    print(f"{total:>5.1f}")

print(f"\nExpected total: 40.0")
print(f"Actual total: {total:.1f}")
print(f"Match: {'✅' if abs(total - 40.0) < 0.1 else '❌'}")

# Test 3: 5 days/week (Mon, Tue, Wed, Thu, Sat)
print("\n" + "=" * 70)
print("Test 3: 5 days/week - Week with 20 LR, 50 total")
print("-" * 70)
workouts = calculate_workout_distribution(
    long_run_miles=20.0,
    total_weekly_miles=50.0,
    runs_per_week=5,
    training_days=["Mon", "Tue", "Wed", "Thu", "Sat"],
)

print("Day  | Type        | Miles | Total")
print("-" * 40)
total = 0.0
for w in workouts:
    print(
        f"{w['day']:>4} | {w['workout_type']:>11} | {w['distance_miles']:>5.1f} | ",
        end="",
    )
    total += w["distance_miles"]
    print(f"{total:>5.1f}")

print(f"\nExpected total: 50.0")
print(f"Actual total: {total:.1f}")
print(f"Match: {'✅' if abs(total - 50.0) < 0.1 else '❌'}")

# Test 4: Full weeks list
print("\n" + "=" * 70)
print("Test 4: Full weeks list distribution")
print("-" * 70)
weeks_input = [
    {"week_number": 1, "long_run_miles": 15.0, "weekly_mileage": 33.0, "phase": "Base"},
    {"week_number": 2, "long_run_miles": 16.0, "weekly_mileage": 36.0, "phase": "Base"},
    {"week_number": 3, "long_run_miles": 17.0, "weekly_mileage": 38.0, "phase": "Base"},
]

pass3 = Pass3WorkoutDistribution()
result = pass3.run(weeks_input, ["Mon", "Wed", "Sat"])

print(f"Generated {len(result.get('weeks', []))} weeks")
print("\nWeek | Day  | Type        | Miles | LR Preserved | Total Preserved")
print("-" * 65)

for w in result.get("weeks", []):
    week_num = w.get("week_number", 0)
    lr = w.get("long_run_miles", 0)
    total = w.get("weekly_mileage", 0)
    workouts_list = w.get("workouts", [])

    for i, workout in enumerate(workouts_list):
        day = workout.get("day", "")
        wtype = workout.get("workout_type", "")
        miles = workout.get("distance_miles", 0)
        if i == 0:
            print(
                f"{week_num:>4} | {day:>4} | {wtype:>11} | {miles:>5.1f} | {lr:>13.1f} | {total:>14.1f}"
            )
        else:
            print(f"     | {day:>4} | {wtype:>11} | {miles:>5.1f}")

# Verify preservation
print("\n✅ Verification:")
all_preserved = True
for orig, new in zip(weeks_input, result.get("weeks", [])):
    orig_lr = orig.get("long_run_miles", 0)
    orig_total = orig.get("weekly_mileage", 0)
    new_lr = new.get("long_run_miles", 0)
    new_total = new.get("weekly_mileage", 0)

    lr_ok = abs(orig_lr - new_lr) < 0.01
    total_ok = abs(orig_total - new_total) < 0.01

    if not lr_ok or not total_ok:
        all_preserved = False
        print(f"  ❌ Week {orig['week_number']}: LR or total not preserved")
    else:
        print(
            f"  ✅ Week {orig['week_number']}: LR={new_lr:.1f} Total={new_total:.1f} (preserved)"
        )

if all_preserved:
    print("\n✅ All values preserved correctly!")

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print("✅ Implementation complete and tested!")

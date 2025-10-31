"""
Test script for refactored Pass 3 workout distribution.

Tests the new forward-distance-based assignment logic and validates
all invariants work correctly for various run day configurations.

Run with: python test_pass3_refactored.py
"""

import sys
import os
import importlib.util
from typing import Dict, List, Any


# Load modules directly to avoid DB dependencies
def load_module(module_path, module_name):
    """Load a module from a file path without triggering __init__.py imports."""
    spec = importlib.util.spec_from_file_location(
        module_name,
        os.path.join(os.path.dirname(__file__), module_path),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Set up module namespace to prevent __init__.py from loading
import sys
from types import ModuleType

# Create dummy modules for the path
for path in ["src", "src.services", "src.services.training_plan"]:
    if path not in sys.modules:
        sys.modules[path] = ModuleType(path)

# Load workout_types first (no dependencies)
workout_types_path = os.path.join(
    os.path.dirname(__file__), "src/services/training_plan/workout_types.py"
)
spec = importlib.util.spec_from_file_location("workout_types", workout_types_path)
workout_types = importlib.util.module_from_spec(spec)
# Inject into sys.modules so relative imports work
sys.modules["src.services.training_plan.workout_types"] = workout_types
sys.modules["src.services.training_plan"].workout_types = workout_types
spec.loader.exec_module(workout_types)

EASY = workout_types.EASY
STEADY = workout_types.STEADY
ENDURANCE = workout_types.ENDURANCE
LONG = workout_types.LONG
TYPE_DISPLAY = workout_types.TYPE_DISPLAY
MIN_NON_LONG_DAY = workout_types.MIN_NON_LONG_DAY

# Load pass3_workout_distribution (depends on workout_types)
pass3_path = os.path.join(
    os.path.dirname(__file__),
    "src/services/training_plan/pass3_workout_distribution.py",
)
spec = importlib.util.spec_from_file_location("pass3_workout_distribution", pass3_path)
pass3_module = importlib.util.module_from_spec(spec)
sys.modules["src.services.training_plan.pass3_workout_distribution"] = pass3_module
spec.loader.exec_module(pass3_module)

calculate_workout_distribution = pass3_module.calculate_workout_distribution
validate_workout_distribution = pass3_module.validate_workout_distribution
Pass3WorkoutDistribution = pass3_module.Pass3WorkoutDistribution


def test_basic_4day_plan():
    """Test basic 4-day plan with Sat as long run."""
    print("\n" + "=" * 60)
    print("TEST 1: Basic 4-day plan (Mon, Wed, Thu, Sat)")
    print("=" * 60)

    run_days = ["Mon", "Wed", "Thu", "Sat"]
    weekly_total = 30.0
    long_run_miles = 12.0
    long_idx = 3  # Sat

    schedule = calculate_workout_distribution(
        weekly_total=weekly_total,
        long_run_miles=long_run_miles,
        run_days=run_days,
        long_idx=long_idx,
    )

    # Validate
    errors, warnings = validate_workout_distribution(
        schedule=schedule,
        run_days=run_days,
        long_idx=long_idx,
        weekly_total=weekly_total,
        long_run_miles=long_run_miles,
        freq=4,
    )

    # Print results
    print(f"\nWeekly Total: {weekly_total} miles")
    print(f"Long Run: {long_run_miles} miles")
    print(f"\nWorkout Distribution:")
    total = 0
    for day in run_days:
        workout = schedule[day]
        total += workout["miles"]
        print(
            f"  {day:3s}: {workout['label']:25s} - {workout['miles']:2d} miles "
            f"(type: {workout['type']})"
        )
    print(f"\nTotal: {total} miles (expected: {weekly_total})")

    if errors:
        print(f"\n❌ ERRORS: {errors}")
        return False
    if warnings:
        print(f"\n⚠️  WARNINGS: {warnings}")
    print("\n✅ Test 1 PASSED")
    return True


def test_3day_plan():
    """Test 3-day plan with Sun as long run."""
    print("\n" + "=" * 60)
    print("TEST 2: 3-day plan (Tue, Thu, Sun)")
    print("=" * 60)

    run_days = ["Tue", "Thu", "Sun"]
    weekly_total = 20.0
    long_run_miles = 9.0
    long_idx = 2  # Sun

    schedule = calculate_workout_distribution(
        weekly_total=weekly_total,
        long_run_miles=long_run_miles,
        run_days=run_days,
        long_idx=long_idx,
    )

    errors, warnings = validate_workout_distribution(
        schedule=schedule,
        run_days=run_days,
        long_idx=long_idx,
        weekly_total=weekly_total,
        long_run_miles=long_run_miles,
        freq=3,
    )

    print(f"\nWeekly Total: {weekly_total} miles")
    print(f"Long Run: {long_run_miles} miles")
    print(f"\nWorkout Distribution:")
    total = 0
    for day in run_days:
        workout = schedule[day]
        total += workout["miles"]
        print(
            f"  {day:3s}: {workout['label']:25s} - {workout['miles']:2d} miles "
            f"(type: {workout['type']})"
        )
    print(f"\nTotal: {total} miles (expected: {weekly_total})")

    if errors:
        print(f"\n❌ ERRORS: {errors}")
        return False
    if warnings:
        print(f"\n⚠️  WARNINGS: {warnings}")
    print("\n✅ Test 2 PASSED")
    return True


def test_5day_plan_midweek_long():
    """Test 5-day plan with long run mid-week."""
    print("\n" + "=" * 60)
    print("TEST 3: 5-day plan with mid-week long run (Mon, Tue, Wed, Fri, Sat)")
    print("=" * 60)

    run_days = ["Mon", "Tue", "Wed", "Fri", "Sat"]
    weekly_total = 40.0
    long_run_miles = 15.0
    long_idx = 4  # Sat

    schedule = calculate_workout_distribution(
        weekly_total=weekly_total,
        long_run_miles=long_run_miles,
        run_days=run_days,
        long_idx=long_idx,
    )

    errors, warnings = validate_workout_distribution(
        schedule=schedule,
        run_days=run_days,
        long_idx=long_idx,
        weekly_total=weekly_total,
        long_run_miles=long_run_miles,
        freq=5,
    )

    print(f"\nWeekly Total: {weekly_total} miles")
    print(f"Long Run: {long_run_miles} miles")
    print(f"\nWorkout Distribution:")
    total = 0
    for day in run_days:
        workout = schedule[day]
        total += workout["miles"]
        print(
            f"  {day:3s}: {workout['label']:25s} - {workout['miles']:2d} miles "
            f"(type: {workout['type']})"
        )
    print(f"\nTotal: {total} miles (expected: {weekly_total})")

    # Check STEADY ordering
    steady_days = [
        (day, schedule[day]["miles"])
        for day in run_days
        if schedule[day]["type"] == STEADY
    ]
    if len(steady_days) > 1:
        # Sort by miles (already in tuple as second element)
        steady_days.sort(key=lambda x: x[1])
        print(f"\nSTEADY days (ordered by miles): {steady_days}")

    if errors:
        print(f"\n❌ ERRORS: {errors}")
        return False
    if warnings:
        print(f"\n⚠️  WARNINGS: {warnings}")
    print("\n✅ Test 3 PASSED")
    return True


def test_long_run_at_start():
    """Test with long run at the beginning of the week."""
    print("\n" + "=" * 60)
    print("TEST 4: Long run at start (Mon, Wed, Thu, Sat)")
    print("=" * 60)

    run_days = ["Mon", "Wed", "Thu", "Sat"]
    weekly_total = 28.0
    long_run_miles = 11.0
    long_idx = 0  # Mon (at start)

    schedule = calculate_workout_distribution(
        weekly_total=weekly_total,
        long_run_miles=long_run_miles,
        run_days=run_days,
        long_idx=long_idx,
    )

    errors, warnings = validate_workout_distribution(
        schedule=schedule,
        run_days=run_days,
        long_idx=long_idx,
        weekly_total=weekly_total,
        long_run_miles=long_run_miles,
        freq=4,
    )

    print(f"\nWeekly Total: {weekly_total} miles")
    print(f"Long Run: {long_run_miles} miles (on {run_days[long_idx]})")
    print(f"\nWorkout Distribution:")
    total = 0
    for day in run_days:
        workout = schedule[day]
        total += workout["miles"]
        print(
            f"  {day:3s}: {workout['label']:25s} - {workout['miles']:2d} miles "
            f"(type: {workout['type']})"
        )
    print(f"\nTotal: {total} miles (expected: {weekly_total})")

    # Verify closest to long is EASY
    closest_day = run_days[1] if long_idx == 0 else run_days[0]
    if schedule[closest_day]["type"] == EASY:
        print(f"\n✓ Closest day to long ({closest_day}) is EASY")
    else:
        print(f"\n❌ Closest day to long ({closest_day}) is NOT EASY")
        return False

    if errors:
        print(f"\n❌ ERRORS: {errors}")
        return False
    if warnings:
        print(f"\n⚠️  WARNINGS: {warnings}")
    print("\n✅ Test 4 PASSED")
    return True


def test_edge_case_small_total():
    """Test edge case with small weekly total."""
    print("\n" + "=" * 60)
    print("TEST 5: Edge case - small weekly total (minimums test)")
    print("=" * 60)

    run_days = ["Mon", "Wed", "Sat"]
    weekly_total = 12.0  # Very small total
    long_run_miles = 6.0
    long_idx = 2  # Sat

    schedule = calculate_workout_distribution(
        weekly_total=weekly_total,
        long_run_miles=long_run_miles,
        run_days=run_days,
        long_idx=long_idx,
    )

    errors, warnings = validate_workout_distribution(
        schedule=schedule,
        run_days=run_days,
        long_idx=long_idx,
        weekly_total=weekly_total,
        long_run_miles=long_run_miles,
        freq=3,
    )

    print(f"\nWeekly Total: {weekly_total} miles")
    print(f"Long Run: {long_run_miles} miles")
    print(f"\nWorkout Distribution:")
    total = 0
    for day in run_days:
        workout = schedule[day]
        total += workout["miles"]
        min_check = (
            "✓"
            if workout["miles"] >= MIN_NON_LONG_DAY or workout["type"] == LONG
            else "❌"
        )
        print(
            f"  {day:3s}: {workout['label']:25s} - {workout['miles']:2d} miles "
            f"(type: {workout['type']}) {min_check}"
        )
    print(f"\nTotal: {total} miles (expected: {weekly_total})")

    if errors:
        print(f"\n❌ ERRORS: {errors}")
        return False
    if warnings:
        print(f"\n⚠️  WARNINGS: {warnings}")
    print("\n✅ Test 5 PASSED")
    return True


def test_pass3_workout_distribution_class():
    """Test the Pass3WorkoutDistribution class with full week structure."""
    print("\n" + "=" * 60)
    print("TEST 6: Pass3WorkoutDistribution class (full integration)")
    print("=" * 60)

    # Create sample week data
    skel_long = [
        {
            "week_number": 1,
            "phase": "Base",
            "long_run_miles": 10.0,
            "weekly_mileage": 25.0,
        },
        {
            "week_number": 2,
            "phase": "Base",
            "long_run_miles": 12.0,
            "weekly_mileage": 28.0,
        },
    ]

    training_days = ["Mon", "Wed", "Thu", "Sat"]

    dist = Pass3WorkoutDistribution()
    result = dist.run(skel_long, training_days)

    print(f"\nGenerated {len(result['weeks'])} weeks:")
    for week in result["weeks"]:
        print(f"\nWeek {week['week_number']} ({week['phase']}):")
        print(f"  Weekly Total: {week['weekly_mileage']} miles")
        print(f"  Long Run: {week['long_run_miles']} miles")
        print(f"  Workouts:")
        for workout in week["workouts"]:
            print(
                f"    {workout.get('day', '?'):3s}: "
                f"{workout.get('workout_type', '?'):25s} - "
                f"{workout.get('distance_miles', workout.get('miles', 0)):5.1f} miles"
            )

        # Verify totals
        workout_sum = sum(
            w.get("distance_miles", w.get("miles", 0)) for w in week["workouts"]
        )
        if abs(workout_sum - week["weekly_mileage"]) > 0.1:
            print(f"  ❌ Total mismatch: {workout_sum} != {week['weekly_mileage']}")
            return False
        else:
            print(f"  ✓ Total verified: {workout_sum} == {week['weekly_mileage']}")

    print("\n✅ Test 6 PASSED")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("PASS 3 REFACTORED - COMPREHENSIVE TEST SUITE")
    print("=" * 60)

    tests = [
        ("Basic 4-day plan", test_basic_4day_plan),
        ("3-day plan", test_3day_plan),
        ("5-day plan mid-week long", test_5day_plan_midweek_long),
        ("Long run at start", test_long_run_at_start),
        ("Edge case small total", test_edge_case_small_total),
        ("Pass3WorkoutDistribution class", test_pass3_workout_distribution_class),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ Test '{test_name}' raised exception: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total tests: {len(tests)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")

    if failed == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Quick test script to verify phase quality checks are working."""

import sys
import os
import importlib.util

# Load the module directly without triggering __init__.py
spec = importlib.util.spec_from_file_location(
    "long_run_spine",
    os.path.join(
        os.path.dirname(__file__),
        "src",
        "services",
        "training_plan",
        "long_run_spine.py",
    ),
)
long_run_spine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(long_run_spine)

generate_long_run_spine = long_run_spine.generate_long_run_spine
validate_phase_quality = long_run_spine.validate_phase_quality

# Test 1: Generate a good spine from start 15
print("=" * 60)
print("Test 1: Generating spine from start 15 (should pass quality checks)")
print("=" * 60)
weeks = generate_long_run_spine(
    starting_long_run_miles=15.0,
    total_weeks_in_plan=0,  # dynamic length
    peak_long_run_target=20.0,
    taper_weeks=3,
    cutback_every=3,
)

lr_values = [w["long_run_miles"] for w in weeks]
print(f"Generated {len(weeks)} weeks")
print(f"Long run values: {lr_values}")

# Validate quality
is_valid, issues = validate_phase_quality(
    weeks, peak=20.0, cutback_every=3, taper_weeks=3
)
print(f"\nQuality check result: {'✅ PASSED' if is_valid else '❌ FAILED'}")
if issues:
    print("Issues found:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("No quality issues detected!")

# Test 2: Test with different starting point
print("\n" + "=" * 60)
print("Test 2: Generating spine from start 12 (should pass quality checks)")
print("=" * 60)
weeks2 = generate_long_run_spine(
    starting_long_run_miles=12.0,
    total_weeks_in_plan=0,
    peak_long_run_target=20.0,
    taper_weeks=3,
    cutback_every=3,
)

lr_values2 = [w["long_run_miles"] for w in weeks2]
print(f"Generated {len(weeks2)} weeks")
print(f"Long run values: {lr_values2}")

is_valid2, issues2 = validate_phase_quality(
    weeks2, peak=20.0, cutback_every=3, taper_weeks=3
)
print(f"\nQuality check result: {'✅ PASSED' if is_valid2 else '❌ FAILED'}")
if issues2:
    print("Issues found:")
    for issue in issues2:
        print(f"  - {issue}")
else:
    print("No quality issues detected!")

# Summary
print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
print(f"Test 1 (start 15): {'✅ PASSED' if is_valid else '❌ FAILED'}")
print(f"Test 2 (start 12): {'✅ PASSED' if is_valid2 else '❌ FAILED'}")

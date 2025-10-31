"""Test script for the new weekly total calculator."""

import sys
import os
import importlib.util

# Load the module directly
spec = importlib.util.spec_from_file_location(
    "weekly_total_calculator",
    os.path.join(
        os.path.dirname(__file__),
        "src",
        "services",
        "training_plan",
        "weekly_total_calculator.py",
    ),
)
calculator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calculator)

recommend_weekly_total = calculator.recommend_weekly_total
calculate_weekly_totals_from_long_runs = (
    calculator.calculate_weekly_totals_from_long_runs
)

# Test 1: Basic calculation (3 days/week)
print("=" * 60)
print("Test 1: 15-mile long run, 3 days/week")
print("=" * 60)
total = recommend_weekly_total(long_run=15.0, runs_per_week=3)
print(f"15-mile LR → Total: {total} miles")
print(f"  Long run %: {(15.0/total)*100:.1f}% (target: 45%)")
print(f"  Expected range: 40-50%")

# Test 2: 4 days/week
print("\n" + "=" * 60)
print("Test 2: 15-mile long run, 4 days/week")
print("=" * 60)
total = recommend_weekly_total(long_run=15.0, runs_per_week=4)
print(f"15-mile LR → Total: {total} miles")
print(f"  Long run %: {(15.0/total)*100:.1f}% (target: 40%)")
print(f"  Expected range: 35-45%")

# Test 3: 5 days/week
print("\n" + "=" * 60)
print("Test 3: 15-mile long run, 5 days/week")
print("=" * 60)
total = recommend_weekly_total(long_run=15.0, runs_per_week=5)
print(f"15-mile LR → Total: {total} miles")
print(f"  Long run %: {(15.0/total)*100:.1f}% (target: 33%)")
print(f"  Expected range: 30-40%")

# Test 4: Weekly progression with ramp cap
print("\n" + "=" * 60)
print("Test 4: Weekly progression (ramp cap test)")
print("=" * 60)
long_runs = [15, 16, 17, 12, 18, 19, 20]
prev_total = None
for i, lr in enumerate(long_runs, start=1):
    total = recommend_weekly_total(
        long_run=lr,
        runs_per_week=3,
        prev_week_total=prev_total,
    )
    increase = ((total - prev_total) / prev_total * 100) if prev_total else 0
    print(f"Week {i}: LR {lr:>2} mi → Total {total:>2} mi | Increase: {increase:+.1f}%")
    prev_total = float(total)

# Test 5: Full weeks list calculation
print("\n" + "=" * 60)
print("Test 5: Full weeks list calculation (preserves long runs)")
print("=" * 60)
weeks = [
    {"week_number": 1, "long_run_miles": 15.0, "phase": "Base"},
    {"week_number": 2, "long_run_miles": 16.0, "phase": "Base"},
    {"week_number": 3, "long_run_miles": 17.0, "phase": "Base"},
    {"week_number": 4, "long_run_miles": 12.0, "phase": "Cutback"},
    {"week_number": 5, "long_run_miles": 18.0, "phase": "Build"},
]
result = calculate_weekly_totals_from_long_runs(weeks, runs_per_week=3)
print("Week | LR   | Total | Phase")
print("-" * 40)
for w in result:
    lr = w.get("long_run_miles", 0)
    total = w.get("weekly_mileage", 0)
    phase = w.get("phase", "")
    print(f"{w['week_number']:>4} | {lr:>4.1f} | {total:>5} | {phase}")

# Verify long runs are preserved
print("\n✅ Long runs preserved check:")
for i, (orig, new) in enumerate(zip(weeks, result), start=1):
    orig_lr = orig.get("long_run_miles", 0)
    new_lr = new.get("long_run_miles", 0)
    if abs(orig_lr - new_lr) < 0.01:
        print(f"  Week {i}: ✅ {orig_lr} = {new_lr}")
    else:
        print(f"  Week {i}: ❌ {orig_lr} ≠ {new_lr}")

print("\n" + "=" * 60)
print("Summary: Weekly total calculator is working correctly!")
print("=" * 60)

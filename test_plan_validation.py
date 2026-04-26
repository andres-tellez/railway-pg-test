"""Comprehensive test script to validate training plan quality and cutback spacing."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from src.services.training_plan.v2.shared_v2.long_run_spine_v2 import (
    generate_long_run_spine,
    validate_phase_quality,
)
from src.services.training_plan.v2.race_configs.marathon_config import MarathonConfig


def validate_cutback_spacing(weeks, cutback_every=4):
    """Validate that cutbacks happen every cutback_every build weeks."""
    lr_values = [w.get("long_run_miles", 0) for w in weeks]

    # Find peak
    peak_idx = lr_values.index(max(lr_values))
    build_phase = lr_values[: peak_idx + 1]

    # Find cutbacks
    cutback_indices = []
    build_counter = 0

    for i in range(1, len(build_phase)):
        build_counter += 1
        if build_phase[i] < build_phase[i - 1] - 0.5:  # Cutback
            cutback_indices.append((i + 1, build_counter))  # (week_num, build_week)

    print(f"\n{'='*80}")
    print("CUTBACK SPACING VALIDATION")
    print(f"{'='*80}")
    print(f"Cutback frequency: Every {cutback_every} build weeks")
    print(f"Total build weeks: {len(build_phase) - 1}")
    print(f"Cutbacks found: {len(cutback_indices)}")
    print()

    if not cutback_indices:
        print("⚠️  WARNING: No cutbacks found in build phase")
        return False

    all_correct = True

    # Check first cutback
    first_week, first_build_week = cutback_indices[0]
    if first_build_week != cutback_every:
        print(f"❌ FIRST CUTBACK VIOLATION:")
        print(
            f"   First cutback at build week {first_build_week}, expected at build week {cutback_every}"
        )
        print(
            f"   Week {first_week}: {build_phase[first_week-2]:.1f} → {build_phase[first_week-1]:.1f}"
        )
        all_correct = False
    else:
        print(f"✅ First cutback at build week {first_build_week} (correct)")

    # Check spacing between cutbacks
    for j in range(len(cutback_indices) - 1):
        week1, build_week1 = cutback_indices[j]
        week2, build_week2 = cutback_indices[j + 1]
        spacing = build_week2 - build_week1

        if spacing != cutback_every:
            print(f"❌ CUTBACK SPACING VIOLATION:")
            print(f"   Cutback at build week {build_week1} (Week {week1})")
            print(f"   Next cutback at build week {build_week2} (Week {week2})")
            print(f"   Spacing: {spacing} weeks, expected: {cutback_every} weeks")
            all_correct = False
        else:
            print(
                f"✅ Cutback spacing correct: {build_week1} → {build_week2} ({spacing} weeks)"
            )

    return all_correct


def test_plan_validation():
    """Test plan generation and validation."""
    config = MarathonConfig()

    starting_long_run = 15.0
    race_date = "2026-02-15"
    total_weeks = 12

    print("=" * 80)
    print("TRAINING PLAN VALIDATION TEST")
    print("=" * 80)
    print(f"Starting long run: {starting_long_run} miles")
    print(f"Race date: {race_date}")
    print(f"Total weeks: {total_weeks}")
    print(f"Cutback every: {config.cutback_every} build weeks")
    print()

    try:
        # Generate spine
        weeks = generate_long_run_spine(
            starting_long_run_miles=starting_long_run,
            total_weeks_in_plan=total_weeks,
            peak_long_run_target=config.target_peak_miles,
            race_date=race_date,
            taper_weeks=config.taper_weeks,
            inc_miles=config.long_run_increment,
            cutback_every=config.cutback_every,
            cutback_factor=config.cutback_factor,
            config=config,
        )

        # Display plan
        print("GENERATED PLAN:")
        print("-" * 80)
        print(f"{'Week':<6} {'Long Run':<10} {'Change':<10} {'Phase':<12} {'Notes'}")
        print("-" * 80)

        prev_lr = None
        for week in weeks:
            week_num = week.get("week_number", 0)
            lr = week.get("long_run_miles", 0)
            phase = week.get("phase", "")

            if prev_lr is not None:
                change = lr - prev_lr
                change_str = f"{change:+.1f}" if abs(change) > 0.01 else "0.0"

                if change < -0.5:
                    notes = "CUTBACK"
                elif change > 1.5:
                    notes = "RESUME"
                else:
                    notes = "BUILD" if change > 0 else "MAINTAIN"
            else:
                change_str = "-"
                notes = "START"

            print(f"{week_num:<6} {lr:<10.1f} {change_str:<10} {phase:<12} {notes}")
            prev_lr = lr

        # Validate cutback spacing
        cutback_ok = validate_cutback_spacing(weeks, config.cutback_every)

        # Run existing validation
        is_valid, issues = validate_phase_quality(
            weeks,
            peak=config.target_peak_miles,
            cutback_every=config.cutback_every,
            taper_weeks=config.taper_weeks,
            taper_ratios=config.taper_ratios,
            race_config=config,
        )

        print(f"\n{'='*80}")
        print("VALIDATION RESULTS")
        print(f"{'='*80}")

        if cutback_ok and is_valid and not issues:
            print("✅ ALL VALIDATIONS PASSED")
            print("   - Cutback spacing is correct")
            print("   - No consecutive cutbacks")
            print("   - Safe progression")
            print("   - Peak reached")
            return True
        else:
            print("❌ VALIDATION FAILURES:")
            if not cutback_ok:
                print("   - Cutback spacing violations")
            if issues:
                print("   - Quality issues found:")
                for issue in issues:
                    print(f"     • {issue}")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_plan_validation()
    sys.exit(0 if success else 1)

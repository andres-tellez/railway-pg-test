"""Final test to verify consecutive cutbacks are fixed."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from src.services.training_plan.v2.shared_v2.long_run_spine_v2 import (
    generate_long_run_spine,
)
from src.services.training_plan.v2.race_configs.marathon_config import MarathonConfig


def test_with_race_date_2_15_26():
    """Test with race date 2/15/26 and realistic starting parameters."""
    config = MarathonConfig()

    # Simulate user scenario: 15-mile recent long run, race date 2/15/26
    starting_long_run = 15.0
    race_date = "2026-02-15"
    total_weeks = 12  # Typical plan length

    print("=" * 100)
    print("TESTING CONSECUTIVE CUTBACKS FIX")
    print("=" * 100)
    print(f"Starting long run: {starting_long_run} miles")
    print(f"Race date: {race_date}")
    print(f"Total weeks: {total_weeks}")
    print(f"Cutback every: {config.cutback_every} weeks")
    print(
        f"Cutback factor: {config.cutback_factor} ({(1-config.cutback_factor)*100:.0f}% reduction)"
    )
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

        print("GENERATED SPINE:")
        print("-" * 100)
        print(f"{'Week':<6} {'Long Run':<10} {'Change':<10} {'Phase':<12} {'Status'}")
        print("-" * 100)

        prev_lr = None
        consecutive_cutbacks = []
        cutback_count = 0

        for i, week in enumerate(weeks):
            week_num = week.get("week_number", i + 1)
            lr = week.get("long_run_miles", 0)
            phase = week.get("phase", "")

            if prev_lr is not None:
                change = lr - prev_lr
                change_str = f"{change:+.1f}" if abs(change) > 0.01 else "0.0"

                # Detect consecutive cutbacks
                if change < -0.5:  # Significant decrease (cutback)
                    cutback_count += 1
                    if (
                        len(consecutive_cutbacks) > 0
                        and consecutive_cutbacks[-1] == week_num - 1
                    ):
                        consecutive_cutbacks.append(week_num)
                        status = f"❌ CONSECUTIVE CUTBACK! (Week {week_num-1} was also cutback)"
                    else:
                        consecutive_cutbacks = [week_num]
                        status = "CUTBACK"
                elif change > 1.5:
                    status = "RESUME (after cutback)"
                    consecutive_cutbacks = []  # Reset on resume
                else:
                    status = "BUILD" if change > 0 else "MAINTAIN"
                    consecutive_cutbacks = []  # Reset on build
            else:
                change_str = "-"
                status = "START"

            print(f"{week_num:<6} {lr:<10.1f} {change_str:<10} {phase:<12} {status}")
            prev_lr = lr

        print("-" * 100)
        print()

        # Final analysis
        print("FINAL ANALYSIS:")
        print("-" * 100)

        lr_values = [w.get("long_run_miles", 0) for w in weeks]
        consecutive_found = False
        consecutive_pairs = []

        for i in range(1, len(lr_values)):
            if lr_values[i] < lr_values[i - 1] - 0.5:  # Significant decrease
                if (
                    i > 1 and lr_values[i - 1] < lr_values[i - 2] - 0.5
                ):  # Previous was also cutback
                    consecutive_found = True
                    consecutive_pairs.append((i, i + 1))
                    print(f"❌ CONSECUTIVE CUTBACKS DETECTED:")
                    print(f"   Week {i}: {lr_values[i-1]:.1f} → {lr_values[i]:.1f}")
                    if i + 1 < len(lr_values):
                        print(
                            f"   Week {i+1}: {lr_values[i]:.1f} → {lr_values[i+1]:.1f}"
                        )

        if not consecutive_found:
            print("✅ NO CONSECUTIVE CUTBACKS DETECTED - FIX WORKS!")
            print(f"   Total cutbacks: {cutback_count}")

            # Check cutback spacing
            cutback_weeks = []
            for i in range(1, len(lr_values)):
                if lr_values[i] < lr_values[i - 1] - 0.5:
                    cutback_weeks.append(i + 1)

            if len(cutback_weeks) > 1:
                print()
                print("CUTBACK SPACING:")
                for j in range(len(cutback_weeks) - 1):
                    spacing = cutback_weeks[j + 1] - cutback_weeks[j]
                    print(
                        f"   Week {cutback_weeks[j]} → Week {cutback_weeks[j+1]} (spacing: {spacing} weeks)"
                    )
                    if spacing < config.cutback_every:
                        print(
                            f"   ⚠️  WARNING: Spacing is {spacing} weeks, expected {config.cutback_every} weeks"
                        )
                    else:
                        print(f"   ✅ Spacing is correct")
        else:
            print(
                f"❌ ISSUE STILL EXISTS: Found {len(consecutive_pairs)} consecutive cutback pair(s)"
            )

        print("=" * 100)
        return not consecutive_found

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_with_race_date_2_15_26()
    sys.exit(0 if success else 1)

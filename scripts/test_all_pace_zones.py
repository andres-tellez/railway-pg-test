#!/usr/bin/env python3
"""Test all pace zones calculation from median easy pace."""

import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=project_root / ".env.local", override=True)
sys.path.insert(0, str(project_root))

from src.db.db_session import get_session
from src.services.training_plan.pace import get_initial_pace_seed


def format_pace(sec):
    """Convert seconds per mile to mm:ss/mile format."""
    minutes = int(sec // 60)
    seconds = int(sec % 60)
    return f"{minutes}:{seconds:02d}/mi"


def test_all_pace_zones(user_id: str):
    """Test all pace zones calculation."""
    print("=" * 60)
    print("TESTING ALL PACE ZONES")
    print("=" * 60)
    print(f"User ID: {user_id}")
    print()

    session = get_session()
    try:
        seed = get_initial_pace_seed(
            session=session,
            user_id=user_id,
            week1_long=8.0,
            lookback_weeks=6,
        )

        print("✅ SUCCESS! All pace zones calculated:")
        print("-" * 60)
        print(f"Easy:      {format_pace(seed.E_min)} - {format_pace(seed.E_max)}")
        print(f"          ({seed.E_min:.1f} - {seed.E_max:.1f} sec/mi)")
        print()
        print(f"Steady:    {format_pace(seed.S_min)} - {format_pace(seed.S_max)}")
        print(f"          ({seed.S_min:.1f} - {seed.S_max:.1f} sec/mi)")
        print()
        print(f"Marathon:  {format_pace(seed.M)}")
        print(f"          ({seed.M:.1f} sec/mi)")
        print()
        print(f"Threshold: {format_pace(seed.T_min)} - {format_pace(seed.T_max)}")
        print(f"          ({seed.T_min:.1f} - {seed.T_max:.1f} sec/mi)")
        print()
        print(f"Week 1 Long Cap: {seed.week1_long_cap:.1f} miles")
        print()

        # Verify ordering
        print("Verification:")
        print("-" * 60)
        print(
            f"Threshold max ({seed.T_max:.1f}) < Marathon ({seed.M:.1f}): {seed.T_max < seed.M}"
        )
        print(
            f"Marathon ({seed.M:.1f}) < Steady min ({seed.S_min:.1f}): {seed.M < seed.S_min}"
        )
        print(
            f"Steady within Easy range: {seed.E_min <= seed.S_min <= seed.S_max <= seed.E_max}"
        )
        print()

        # Correct ordering: Threshold < Marathon < Steady < Easy
        # Note: Steady overlaps with Easy (Steady is subset of Easy), which is correct
        if (
            seed.T_max < seed.M < seed.S_min
            and seed.E_min <= seed.S_min <= seed.S_max <= seed.E_max
        ):
            print("✅ All paces are correctly ordered!")
        else:
            print("❌ WARNING: Pace ordering issue detected!")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_all_pace_zones.py <user_id>")
        print()
        print("Example:")
        print(
            '  python scripts/test_all_pace_zones.py "2e1c2581-619c-4a2a-a8b4-4dfc265e7789"'
        )
        sys.exit(1)

    user_id = sys.argv[1]
    test_all_pace_zones(user_id)

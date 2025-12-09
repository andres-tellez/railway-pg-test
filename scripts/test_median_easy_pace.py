#!/usr/bin/env python3
"""
Test script for median easy pace calculation.

Usage:
    python scripts/test_median_easy_pace.py <user_id>

Example:
    python scripts/test_median_easy_pace.py "2e1c2581-619c-4a2a-a8b4-4dfc265e7789"
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
project_root = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=project_root / ".env.local", override=True)

# Add project root to path
sys.path.insert(0, str(project_root))

from src.db.db_session import get_session
from src.services.training_plan.pace.performance_calculator import (
    calculate_paces_from_performance,
)
from sqlalchemy import text
from datetime import datetime, timedelta


def format_pace(sec):
    """Convert seconds per mile to mm:ss/mile format."""
    minutes = int(sec // 60)
    seconds = int(sec % 60)
    return f"{minutes}:{seconds:02d}/mi"


def test_median_easy_pace(user_id: str):
    """Test the median easy pace calculation."""
    print("=" * 60)
    print("TESTING MEDIAN EASY PACE CALCULATION")
    print("=" * 60)
    print(f"User ID: {user_id}")
    print()

    session = get_session()
    try:
        # First, check how many runs we have
        cutoff = datetime.now() - timedelta(weeks=6)
        count_query = text(
            """
            SELECT COUNT(*) as run_count
            FROM activities
            WHERE user_id = :user_id
              AND type = 'Run'
              AND start_date >= :cutoff
              AND conv_distance >= 2.0
              AND moving_time IS NOT NULL
              AND moving_time > 0
              AND conv_distance > 0
              AND (moving_time::float / conv_distance) BETWEEN 360 AND 1200
        """
        )

        run_count = session.execute(
            count_query, {"user_id": user_id, "cutoff": cutoff}
        ).scalar()

        print(f"📊 Valid runs found: {run_count}")
        print(f"📅 Lookback period: Last 6 weeks (since {cutoff.date()})")
        print()

        if run_count < 6:
            print(f"❌ INSUFFICIENT DATA: Need at least 6 runs, found {run_count}")
            return

        # Get all runs for inspection
        detail_query = text(
            """
            SELECT
                activity_id,
                start_date,
                conv_distance,
                moving_time,
                moving_time::float / conv_distance AS pace_sec_per_mile
            FROM activities
            WHERE user_id = :user_id
              AND type = 'Run'
              AND start_date >= :cutoff
              AND conv_distance >= 2.0
              AND moving_time IS NOT NULL
              AND moving_time > 0
              AND conv_distance > 0
              AND (moving_time::float / conv_distance) BETWEEN 360 AND 1200
            ORDER BY pace_sec_per_mile
            LIMIT 20
        """
        )

        runs = session.execute(
            detail_query, {"user_id": user_id, "cutoff": cutoff}
        ).fetchall()

        print(f"📋 Sample runs (showing first 20, sorted by pace):")
        print("-" * 60)
        for i, run in enumerate(runs, 1):
            pace_str = format_pace(run.pace_sec_per_mile)
            print(
                f"{i:2d}. {run.start_date.date()} | {run.conv_distance:5.2f} mi | "
                f"{run.moving_time//60:3d}:{run.moving_time%60:02d} | {pace_str}"
            )
        print()

        # Calculate median using our function
        print("🔍 Calculating median easy pace...")
        pace_seed = calculate_paces_from_performance(
            session=session,
            user_id=user_id,
            lookback_weeks=6,
        )

        if pace_seed:
            # Extract median easy pace from the calculated seed
            # Easy pace range is median - 15 to + 45, so median is E_min + 15
            median_pace = pace_seed.E_min + 15
            print()
            print("✅ SUCCESS!")
            print("-" * 60)
            print(f"Median Easy Pace: {format_pace(median_pace)}")
            print(f"                 {median_pace:.1f} seconds/mile")
            print(f"                 {median_pace/60:.2f} minutes/mile")
            print()

            # Show pace range
            paces = [float(r.pace_sec_per_mile) for r in runs]
            print(f"Pace Range:")
            print(f"  Min: {format_pace(min(paces))} ({min(paces):.1f} sec/mi)")
            print(f"  Max: {format_pace(max(paces))} ({max(paces):.1f} sec/mi)")
            print(
                f"  Avg: {format_pace(sum(paces)/len(paces))} ({sum(paces)/len(paces):.1f} sec/mi)"
            )
            print(f"  Median: {format_pace(median_pace)} ({median_pace:.1f} sec/mi)")
        else:
            print()
            print("❌ FAILED: Function returned None")
            print("   This shouldn't happen if we have 6+ runs")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_median_easy_pace.py <user_id>")
        print()
        print("Example:")
        print(
            '  python scripts/test_median_easy_pace.py "2e1c2581-619c-4a2a-a8b4-4dfc265e7789"'
        )
        sys.exit(1)

    user_id = sys.argv[1]
    test_median_easy_pace(user_id)

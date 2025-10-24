#!/usr/bin/env python3
"""
Test the fixed v_upcoming_workouts view
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
load_dotenv(".env.local")

# Add project root to path
project_root = Path(__file__).resolve().parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

from src.db.db_session import get_session
from sqlalchemy import text


def test_fixed_view():
    """Test the fixed v_upcoming_workouts view"""

    print("=" * 60)
    print("TESTING FIXED v_upcoming_workouts VIEW")
    print("=" * 60)

    session = get_session()
    try:
        # Test the fixed view
        result = session.execute(
            text(
                """
            SELECT date, workout_type, miles, timeframe
            FROM v_upcoming_workouts
            WHERE user_id = :user_id
            ORDER BY date
            LIMIT 15
        """
            ),
            {"user_id": "ddc21831-1b01-4cfc-82db-7632ab2cfba1"},
        ).fetchall()

        print("Fixed v_upcoming_workouts view results:")
        print("-" * 50)

        for row in result:
            print(
                f"{row.date}: {row.workout_type} - {row.miles} miles ({row.timeframe})"
            )

        # Test timeframe distribution
        print("\nTimeframe distribution:")
        print("-" * 30)

        timeframe_result = session.execute(
            text(
                """
            SELECT timeframe, COUNT(*) as count
            FROM v_upcoming_workouts
            WHERE user_id = :user_id
            GROUP BY timeframe
            ORDER BY timeframe
        """
            ),
            {"user_id": "ddc21831-1b01-4cfc-82db-7632ab2cfba1"},
        ).fetchall()

        for row in timeframe_result:
            print(f"{row.timeframe}: {row.count} workouts")

        # Verify no past dates are included
        print("\nVerifying no past dates:")
        print("-" * 30)

        past_check = session.execute(
            text(
                """
            SELECT COUNT(*) as past_count
            FROM v_upcoming_workouts
            WHERE user_id = :user_id
            AND date < CURRENT_DATE
        """
            ),
            {"user_id": "ddc21831-1b01-4cfc-82db-7632ab2cfba1"},
        ).fetchone()

        print(f"Past workouts included: {past_check.past_count}")

        if past_check.past_count == 0:
            print("SUCCESS: No past workouts included!")
        else:
            print("ISSUE: Past workouts are still included!")

    except Exception as e:
        print(f"Error testing view: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    test_fixed_view()

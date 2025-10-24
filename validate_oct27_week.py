#!/usr/bin/env python3
"""
Validate the actual database data for October 27 week
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


def validate_oct27_week():
    """Validate the actual database data for October 27 week"""

    print("=" * 60)
    print("VALIDATING OCTOBER 27 WEEK DATA")
    print("=" * 60)

    session = get_session()
    try:
        # Query the actual database data for Oct 27 week
        result = session.execute(
            text(
                """
            SELECT date, workout_type, miles, description
            FROM plan_workouts
            WHERE date >= '2025-10-27' AND date <= '2025-11-02'
            ORDER BY date
        """
            )
        ).fetchall()

        print("ACTUAL DATABASE DATA for Oct 27 week (2025-10-27 to 2025-11-02):")
        print("-" * 60)

        total = 0
        for row in result:
            print(
                f"{row.date}: {row.workout_type} - {row.miles} miles ({row.description})"
            )
            total += row.miles

        print("-" * 60)
        print(f"TOTAL FROM DATABASE: {total} miles")
        print("=" * 60)

        # Also check what the GPT context generation is calculating
        print("\nCHECKING GPT CONTEXT CALCULATION:")
        print("-" * 60)

        # Get the context to see what the GPT is receiving
        from src.services.simple_conversation_service import SimpleConversationService

        # Get a user_id
        user_result = session.execute(
            text("SELECT user_id FROM user_profile LIMIT 1")
        ).fetchone()
        if user_result:
            user_id = user_result[0]
            service = SimpleConversationService(user_id)
            context = service.get_context("How does my running plan look?")

            # Look for the Oct 27 week in the context
            lines = context.split("\n")
            in_oct27_week = False
            oct27_total = 0

            for line in lines:
                if "Week of October 27 - November 02:" in line:
                    in_oct27_week = True
                    print("Found Oct 27 week in GPT context:")
                    continue
                elif in_oct27_week and line.startswith("Week of"):
                    break
                elif in_oct27_week and "miles" in line and "Distance:" in line:
                    # Extract miles from line like "Distance: 4.0 miles"
                    try:
                        miles_str = line.split("Distance: ")[1].split(" miles")[0]
                        miles = float(miles_str)
                        oct27_total += miles
                        print(f"  {line.strip()}")
                    except:
                        pass

            print(f"\nTOTAL FROM GPT CONTEXT: {oct27_total} miles")
            service.close()

        print("=" * 60)
        print("VALIDATION COMPLETE")

    except Exception as e:
        print(f"Error during validation: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    validate_oct27_week()

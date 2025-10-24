#!/usr/bin/env python3
"""
Test script to compare old vs new streamlined approach
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

from src.services.simple_conversation_service import SimpleConversationService
from src.services.streamlined_conversation_service import StreamlinedConversationService
from src.utils.gpt_ops import get_conversation_response
from src.routes.conversation_routes import build_gpt_messages
from src.db.db_session import get_session
from sqlalchemy import text


def compare_approaches():
    """Compare old vs new approach"""

    print("=" * 80)
    print("COMPARING OLD VS NEW APPROACH")
    print("=" * 80)

    # Get a real user_id
    session = get_session()
    try:
        result = session.execute(
            text("SELECT user_id FROM user_profile LIMIT 1")
        ).fetchone()
        if not result:
            print("No users found in database")
            return

        user_id = result[0]
        print(f"Using user_id: {user_id}")

        # Test question
        question = "What's my total planned mileage for the week of October 27?"

        print(f"\nTesting question: {question}")
        print("=" * 60)

        # Test OLD approach
        print("\n1. OLD APPROACH (SimpleConversationService):")
        print("-" * 50)
        try:
            old_service = SimpleConversationService(user_id)
            old_context = old_service.get_context(question)
            old_messages = build_gpt_messages(old_context, [], question)
            old_response = get_conversation_response(old_messages, require_json=False)

            print(f"Context length: {len(old_context)} characters")
            print(
                f"System message length: {len(old_messages[0]['content'])} characters"
            )
            print(f"Response: {old_response[:200]}...")

            old_service.close()
        except Exception as e:
            print(f"Error with old approach: {e}")

        # Test NEW approach
        print("\n2. NEW APPROACH (StreamlinedConversationService):")
        print("-" * 50)
        try:
            new_service = StreamlinedConversationService(user_id)
            new_context = new_service.get_context(question)
            new_messages = build_gpt_messages(new_context, [], question)
            new_response = get_conversation_response(new_messages, require_json=False)

            print(f"Context length: {len(new_context)} characters")
            print(
                f"System message length: {len(new_messages[0]['content'])} characters"
            )
            print(f"Response: {new_response[:200]}...")

            new_service.close()
        except Exception as e:
            print(f"Error with new approach: {e}")

        # Compare results
        print("\n3. COMPARISON:")
        print("-" * 50)
        print(
            f"Old context: {len(old_context) if 'old_context' in locals() else 'ERROR'} chars"
        )
        print(
            f"New context: {len(new_context) if 'new_context' in locals() else 'ERROR'} chars"
        )

        if "old_context" in locals() and "new_context" in locals():
            reduction = len(old_context) - len(new_context)
            reduction_pct = (reduction / len(old_context)) * 100
            print(f"Reduction: {reduction} characters ({reduction_pct:.1f}%)")

        # Test the calculated views
        print("\n4. TESTING CALCULATED VIEWS:")
        print("-" * 50)

        # Test weekly totals view
        weekly_result = session.execute(
            text(
                """
            SELECT week_start, total_miles, workout_count, workout_types
            FROM v_weekly_plan_totals
            WHERE week_start >= '2025-10-27' AND week_start <= '2025-11-02'
            ORDER BY week_start
        """
            )
        ).fetchall()

        print("Weekly totals from view:")
        for row in weekly_result:
            print(
                f"  {row.week_start.date()}: {row.total_miles} miles ({row.workout_count} workouts)"
            )

        # Test plan summary view
        plan_result = session.execute(
            text(
                """
            SELECT plan_name, total_miles, avg_weekly_miles, peak_weekly_miles
            FROM v_plan_summary
            WHERE user_id = :user_id
        """
            ),
            {"user_id": user_id},
        ).fetchone()

        if plan_result:
            print(f"\nPlan summary from view:")
            print(f"  Plan: {plan_result.plan_name}")
            print(f"  Total miles: {plan_result.total_miles}")
            print(f"  Avg weekly: {plan_result.avg_weekly_miles}")
            print(f"  Peak weekly: {plan_result.peak_weekly_miles}")

    except Exception as e:
        print(f"Error during comparison: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    compare_approaches()

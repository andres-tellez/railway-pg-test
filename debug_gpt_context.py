#!/usr/bin/env python3
"""
Debug script to check what GPT is actually receiving
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
from src.db.db_session import get_session
from sqlalchemy import text


def debug_gpt_context():
    """Debug what the GPT is actually receiving"""

    print("=" * 60)
    print("DEBUGGING GPT CONTEXT")
    print("=" * 60)

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

        # Test the enhanced conversation service
        service = SimpleConversationService(user_id)
        context = service.get_context("How does my running plan look?")

        print("\n" + "=" * 60)
        print("GPT CONTEXT RECEIVED:")
        print("=" * 60)
        # Handle Unicode issues by encoding to ASCII with errors='replace'
        try:
            print(context)
        except UnicodeEncodeError:
            print(context.encode("ascii", errors="replace").decode("ascii"))

        print("\n" + "=" * 60)
        print(f"TOTAL CONTEXT LENGTH: {len(context)} characters")
        print("=" * 60)

        # Check what data sources are being used
        print("\n" + "=" * 60)
        print("DATA SOURCE ANALYSIS:")
        print("=" * 60)

        if "TRAINING PLAN ANALYSIS:" in context:
            print("✓ Training plan data is being loaded")
        else:
            print("✗ Training plan data is MISSING")

        if "RECENT COMPLETED ACTIVITIES:" in context:
            print("✓ Recent activities data is being loaded")
        else:
            print("✗ Recent activities data is MISSING")

        if "DATA QUALITY ASSESSMENT:" in context:
            print("✓ Data quality assessment is being loaded")
        else:
            print("✗ Data quality assessment is MISSING")

        service.close()

    except Exception as e:
        print(f"Error during debugging: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    debug_gpt_context()

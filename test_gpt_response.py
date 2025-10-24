#!/usr/bin/env python3
"""
Test script to check GPT response with enhanced context
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
from src.utils.gpt_ops import get_conversation_response
from src.routes.conversation_routes import build_gpt_messages


def test_gpt_response():
    """Test GPT response with enhanced context"""

    print("=" * 60)
    print("TESTING GPT RESPONSE WITH ENHANCED CONTEXT")
    print("=" * 60)

    # Get a real user_id
    from src.db.db_session import get_session
    from sqlalchemy import text

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

        # Get the enhanced context
        service = SimpleConversationService(user_id)
        context = service.get_context("How does my running plan look?")

        # Build GPT messages
        messages = build_gpt_messages(context, [], "How does my running plan look?")

        print("\n" + "=" * 60)
        print("GPT MESSAGES BEING SENT:")
        print("=" * 60)
        print(f"Number of messages: {len(messages)}")
        print(f"System message length: {len(messages[0]['content'])} characters")
        print(f"User message: {messages[-1]['content']}")

        # Show first part of system message
        system_msg = messages[0]["content"]
        print(f"\nSystem message preview (first 500 chars):")
        print(system_msg[:500])
        print("...")

        # Test GPT response
        print("\n" + "=" * 60)
        print("TESTING GPT RESPONSE:")
        print("=" * 60)

        try:
            response = get_conversation_response(messages, require_json=False)
            print("GPT Response:")
            print(response)
        except Exception as e:
            print(f"Error calling GPT: {e}")
            import traceback

            traceback.print_exc()

        service.close()

    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    test_gpt_response()

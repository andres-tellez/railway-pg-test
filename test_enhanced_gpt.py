#!/usr/bin/env python3
"""
Test script for enhanced GPT implementation
This script validates the new training plan context and data quality features
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
from src.utils.data_quality_validator import DataQualityValidator
from src.db.db_session import get_session
from src.config.conversation_config import ConversationConfig


def test_enhanced_gpt():
    """Test the enhanced GPT context"""

    print("=" * 60)
    print("TESTING ENHANCED GPT IMPLEMENTATION")
    print("=" * 60)

    # Test configuration first
    print("\n1. Testing Configuration")
    print("-" * 50)
    test_configuration()

    # Test database views
    print("\n2. Testing Database Views")
    print("-" * 50)
    test_database_views()

    print("\n" + "=" * 60)
    print("BASIC TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("\nTo test with actual user data, run:")
    print(
        "python -c \"from dotenv import load_dotenv; load_dotenv('.env.local'); from test_enhanced_gpt import test_with_user; test_with_user('your-user-id')\""
    )


def test_with_user(user_id: str):
    """Test with actual user data"""
    try:
        # Test the enhanced conversation service
        print(f"\nTesting Enhanced Conversation Service for user: {user_id}")
        print("-" * 50)

        service = SimpleConversationService(user_id)
        context = service.get_context("How does my running plan look?")

        print("=== ENHANCED GPT CONTEXT ===")
        print(context)
        print("\n" + "=" * 50)

        # Test data quality validation
        print("\nTesting Data Quality Validation")
        print("-" * 50)

        validator = DataQualityValidator(service.session)
        plan_quality = validator.validate_training_plan_data(user_id)
        activity_quality = validator.validate_activity_data(user_id)

        print("=== DATA QUALITY ASSESSMENT ===")
        print(f"Plan Quality: {plan_quality}")
        print(f"Activity Quality: {activity_quality}")

        service.close()

        print("\n" + "=" * 60)
        print("USER-SPECIFIC TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR during testing: {e}")
        import traceback

        traceback.print_exc()


def test_configuration():
    """Test the updated configuration"""
    print("GPT Model:", ConversationConfig.GPT_MODEL)
    print("Temperature:", ConversationConfig.GPT_TEMPERATURE)
    print("Max Tokens:", ConversationConfig.GPT_MAX_TOKENS)
    print(
        "Max Context Tokens:", ConversationConfig.CONTEXT_LIMITS["max_context_tokens"]
    )
    print("Database Views:", ConversationConfig.DATABASE_VIEWS)

    # Validate configuration
    assert ConversationConfig.GPT_MODEL == "gpt-4", "GPT model should be gpt-4"
    assert ConversationConfig.GPT_TEMPERATURE == 0.3, "Temperature should be 0.3"
    assert ConversationConfig.GPT_MAX_TOKENS == 2000, "Max tokens should be 2000"
    assert (
        ConversationConfig.DATABASE_VIEWS["activities"] == "v_completed_activities"
    ), "Activities view should be renamed"
    assert (
        ConversationConfig.DATABASE_VIEWS["splits"] == "v_activity_splits"
    ), "Splits view should be renamed"

    print("Configuration validation passed!")


def test_database_views():
    """Test that the new database views exist and work"""
    print("\n4. Testing Database Views")
    print("-" * 50)

    try:
        session = get_session()

        from sqlalchemy import text

        # Test v_completed_activities view
        result = session.execute(
            text("SELECT COUNT(*) FROM v_completed_activities LIMIT 1")
        ).fetchone()
        print(
            f"v_completed_activities view accessible: {result[0] if result else 0} records"
        )

        # Test v_activity_splits view
        result = session.execute(
            text("SELECT COUNT(*) FROM v_activity_splits LIMIT 1")
        ).fetchone()
        print(
            f"v_activity_splits view accessible: {result[0] if result else 0} records"
        )

        session.close()

    except Exception as e:
        print(f"Database view test failed: {e}")
        print("Make sure to run the database migration first!")


if __name__ == "__main__":
    test_enhanced_gpt()
    test_database_views()

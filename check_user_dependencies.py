#!/usr/bin/env python3
"""
Check all dependencies for a user before deletion.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
env_path = Path(__file__).parent / ".env.local"
load_dotenv(env_path)

from src.db.db_session import get_session
from src.db.models.user_identity import UserIdentity
from src.db.models.user_profile import UserProfile
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.plans import Plan
from src.db.models.conversations import Conversation
from src.db.models.activities import Activity
from src.db.models.user_auth_providers import UserAuthProvider


def check_user_dependencies(email: str):
    """Check all dependencies for a user by email."""
    session = get_session()

    try:
        # Find user by email
        user = session.query(UserIdentity).filter_by(email=email).first()

        if not user:
            print(f"User with email '{email}' not found!")
            return

        user_id = str(user.user_id)

        print("=" * 80)
        print(f"Checking Dependencies for User: {email}")
        print(f"User ID: {user_id}")
        print("=" * 80)
        print()

        # Check UserProfile
        profile = session.query(UserProfile).filter_by(user_id=user_id).first()
        has_profile = profile is not None
        print(f"UserProfile: {'EXISTS' if has_profile else 'NONE'}")

        # Check UserAthleteLink
        athlete_link = session.query(UserAthleteLink).filter_by(user_id=user_id).first()
        has_athlete = athlete_link is not None
        print(f"UserAthleteLink: {'EXISTS' if has_athlete else 'NONE'}")
        if has_athlete:
            print(f"  Athlete ID: {athlete_link.athlete_id}")

        # Check Plans
        plans = session.query(Plan).filter_by(user_id=user.user_id).all()
        plan_count = len(plans)
        print(f"Plans: {plan_count} plan(s)")
        for plan in plans:
            print(
                f"  - Plan ID: {plan.id}, Name: {plan.plan_name}, Active: {plan.is_active}"
            )

        # Check Conversations
        conversations = (
            session.query(Conversation).filter_by(user_id=user.user_id).all()
        )
        conv_count = len(conversations)
        print(f"Conversations: {conv_count} conversation(s)")

        # Check Activities
        activities = session.query(Activity).filter_by(user_id=user_id).all()
        activity_count = len(activities)
        print(f"Activities: {activity_count} activity/activities")

        # Check UserAuthProviders
        auth_providers = (
            session.query(UserAuthProvider).filter_by(user_id=user_id).all()
        )
        provider_count = len(auth_providers)
        print(f"Auth Providers: {provider_count} provider(s)")
        for provider in auth_providers:
            print(f"  - {provider.provider_name}: {provider.provider_user_id}")

        print()
        print("-" * 80)
        print("Summary:")
        print(f"  - UserProfile: {'YES (will be deleted)' if has_profile else 'NO'}")
        print(
            f"  - UserAthleteLink: {'YES (will be CASCADE deleted)' if has_athlete else 'NO'}"
        )
        print(f"  - Plans: {plan_count} (will be CASCADE deleted)")
        print(f"  - Conversations: {conv_count} (will be CASCADE deleted)")
        print(f"  - Activities: {activity_count} (NEEDS MANUAL DELETE - no CASCADE)")
        print(
            f"  - Auth Providers: {provider_count} (NEEDS MANUAL DELETE - no CASCADE)"
        )
        print()

        # Check if safe to delete
        safe_to_delete = activity_count == 0 and provider_count == 0

        if safe_to_delete:
            print("SAFE TO DELETE: All dependencies have CASCADE delete")
        else:
            print("WARNING: Some dependencies need manual deletion:")
            if activity_count > 0:
                print(f"  - {activity_count} activities must be deleted manually")
            if provider_count > 0:
                print(f"  - {provider_count} auth providers must be deleted manually")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    check_user_dependencies("andres.tellez@kohls.com")

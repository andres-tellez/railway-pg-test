#!/usr/bin/env python3
"""
Safely delete a user and all their dependencies.
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


def delete_user_safely(email: str, confirm: bool = False):
    """Safely delete a user and all their dependencies."""
    session = get_session()

    try:
        # Find user by email
        user = session.query(UserIdentity).filter_by(email=email).first()

        if not user:
            print(f"User with email '{email}' not found!")
            return

        user_id = str(user.user_id)

        print("=" * 80)
        print(f"DELETING USER: {email}")
        print(f"User ID: {user_id}")
        print("=" * 80)
        print()

        # Check dependencies first
        profile = session.query(UserProfile).filter_by(user_id=user_id).first()
        athlete_link = session.query(UserAthleteLink).filter_by(user_id=user_id).first()
        plans = session.query(Plan).filter_by(user_id=user.user_id).all()
        conversations = (
            session.query(Conversation).filter_by(user_id=user.user_id).all()
        )
        activities = session.query(Activity).filter_by(user_id=user_id).all()
        auth_providers = (
            session.query(UserAuthProvider).filter_by(user_id=user_id).all()
        )

        print("Dependencies Found:")
        print(f"  - UserProfile: {'YES' if profile else 'NO'}")
        print(f"  - UserAthleteLink: {'YES' if athlete_link else 'NO'}")
        print(f"  - Plans: {len(plans)}")
        print(f"  - Conversations: {len(conversations)}")
        print(f"  - Activities: {len(activities)}")
        print(f"  - Auth Providers: {len(auth_providers)}")
        print()

        if not confirm:
            print(
                "WARNING: This will permanently delete the user and all dependencies!"
            )
            print("To confirm deletion, run: delete_user_safely(email, confirm=True)")
            return

        # Delete in order (respecting foreign keys)
        # 1. Delete Activities (no CASCADE, must delete manually)
        if activities:
            print(f"Deleting {len(activities)} activities...")
            for activity in activities:
                session.delete(activity)
            session.flush()

        # 2. Delete Auth Providers (no CASCADE, must delete manually)
        if auth_providers:
            print(f"Deleting {len(auth_providers)} auth providers...")
            for provider in auth_providers:
                session.delete(provider)
            session.flush()

        # 3. Delete UserProfile (no CASCADE, must delete manually)
        if profile:
            print("Deleting UserProfile...")
            session.delete(profile)
            session.flush()

        # 4. Delete UserIdentity (will CASCADE delete Plans, Conversations, UserAthleteLink)
        print(
            "Deleting UserIdentity (will cascade delete Plans, Conversations, UserAthleteLink)..."
        )
        session.delete(user)
        session.commit()

        print()
        print("SUCCESS: User and all dependencies deleted!")

    except Exception as e:
        print(f"ERROR: {e}")
        session.rollback()
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    import sys

    email = "andres.tellez@kohls.com"

    # Check for confirmation flag
    confirm = "--confirm" in sys.argv or "-c" in sys.argv

    if confirm:
        print("CONFIRMED: Proceeding with deletion...")
        print()
    else:
        print("DRY RUN MODE: Use --confirm or -c flag to actually delete")
        print()

    delete_user_safely(email, confirm=confirm)

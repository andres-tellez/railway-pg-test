#!/usr/bin/env python3
"""
Debug script to check user status and understand why redirect to /setup.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
env_path = Path(__file__).parent / ".env.local"
load_dotenv(env_path)

from src.db.db_session import get_session
from src.db.models.user_profile import UserProfile
from src.db.dao.user_athletes_dao import get_by_user_id
from src.db.models.user_identity import UserIdentity
from sqlalchemy import select


def debug_user_status():
    """Check user status and explain redirect behavior."""
    session = get_session()

    try:
        print("=" * 80)
        print("DEBUG: User Status Check")
        print("=" * 80)

        # Get all users
        users = session.query(UserIdentity).all()

        if not users:
            print("\nWARNING: No users found in database!")
            return

        print(f"\nFound {len(users)} user(s) in database:\n")

        for user in users:
            print(f"User ID: {user.user_id}")
            print(f"  Email: {user.email}")
            print(f"  Name: {user.name}")
            print()

            # Check hasOnboarded (UserProfile exists)
            profile = session.execute(
                select(UserProfile).where(UserProfile.user_id == str(user.user_id))
            ).scalar_one_or_none()

            has_onboarded = profile is not None
            print(f"  hasOnboarded: {has_onboarded}")
            if has_onboarded:
                print(f"     YES - UserProfile exists (user has completed onboarding)")
            else:
                print(
                    f"     NO - No UserProfile found (user needs to complete onboarding)"
                )
            print()

            # Check hasStrava (user_athletes link exists)
            link = get_by_user_id(str(user.user_id))
            has_strava = link is not None
            print(f"  hasStrava: {has_strava}")
            if has_strava:
                print(f"     YES - Strava athlete link exists")
                print(f"        Athlete ID: {link.athlete_id}")
                print(f"        Created: {link.created_at}")
            else:
                print(
                    f"     NO - No Strava athlete link found (user needs to connect Strava)"
                )
            print()

            # Determine redirect destination
            print(f"  Expected Redirect:")
            if has_onboarded:
                print(f"     Should redirect to: /home")
            elif has_strava:
                print(f"     Should redirect to: /onboarding")
            else:
                print(f"     Should redirect to: /setup")
            print()

            print("-" * 80)
            print()

        # Summary
        print("\nSummary:")
        print("   Based on the logic in SmartRouter.tsx:")
        print("   1. If hasOnboarded === true -> /home")
        print("   2. If hasStrava === true (but not onboarded) -> /onboarding")
        print("   3. If neither -> /setup")
        print("   4. On API error -> /setup (fallback)")
        print()

        # Check for potential issues
        print("Potential Issues to Check:")
        print("   1. Is the /api/user endpoint returning correct values?")
        print("   2. Are there any errors in the browser console?")
        print("   3. Is the API request failing silently?")
        print("   4. Check Network tab in browser DevTools for /api/user response")
        print()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    debug_user_status()

#!/usr/bin/env python3
"""Check user-athlete linkage for specific user."""

import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env.local"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

from src.db.db_session import get_session
from src.db.models.user_identity import UserIdentity
from src.db.models.user_athletes import UserAthleteLink

session = get_session()

try:
    email = "andres.tellez@gmail.com"

    # Find user by email
    user = session.query(UserIdentity).filter_by(email=email).first()

    if not user:
        print(f"❌ User not found with email: {email}")
    else:
        user_id = str(user.user_id)
        print(f"✅ Found user: {email}")
        print(f"   User ID: {user_id}")

        # Check for athlete link
        link = session.query(UserAthleteLink).filter_by(user_id=user_id).first()

        if link:
            print(f"\n✅ User-Athlete link EXISTS:")
            print(f"   Athlete ID: {link.athlete_id}")
            print(f"   Created: {link.created_at}")
        else:
            print(f"\n❌ No athlete link found for this user")
            print(f"\nChecking all existing links:")
            all_links = session.query(UserAthleteLink).all()
            for l in all_links:
                user_check = (
                    session.query(UserIdentity).filter_by(user_id=l.user_id).first()
                )
                email_display = user_check.email if user_check else "unknown"
                print(
                    f"   User: {l.user_id} ({email_display}) → Athlete: {l.athlete_id}"
                )

            print(f"\n💡 Your user_id ({user_id}) is NOT linked to any athlete")
            print(f"   You need to reconnect your Strava account")

finally:
    session.close()

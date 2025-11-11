#!/usr/bin/env python3
"""Check athlete 347085 linkage and activities."""

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
from src.db.models.activities import Activity
from src.db.models.tokens import Token
from datetime import datetime, timedelta

session = get_session()

try:
    athlete_id = 347085
    user_email = "andres.tellez@gmail.com"

    print("=" * 80)
    print("CHECKING ATHLETE 347085 LINKAGE")
    print("=" * 80)

    # Find user by email
    user = session.query(UserIdentity).filter_by(email=user_email).first()
    if not user:
        print(f"❌ User not found: {user_email}")
        exit(1)

    user_id = str(user.user_id)
    print(f"\n✅ User found: {user_email}")
    print(f"   User ID: {user_id}")

    # Check current link for athlete 347085
    current_link = (
        session.query(UserAthleteLink).filter_by(athlete_id=athlete_id).first()
    )

    if current_link:
        current_user = (
            session.query(UserIdentity).filter_by(user_id=current_link.user_id).first()
        )
        current_email = current_user.email if current_user else "unknown"

        print(f"\n📋 Current link for athlete {athlete_id}:")
        print(f"   Linked to User ID: {current_link.user_id}")
        print(f"   Email: {current_email}")
        print(f"   Created: {current_link.created_at}")

        if current_link.user_id == user_id:
            print(f"\n✅ CORRECT: Athlete is already linked to your account!")
        else:
            print(f"\n⚠️  MISMATCH: Athlete is linked to a DIFFERENT user account")
            print(f"   Expected: {user_id} ({user_email})")
            print(f"   Actual:   {current_link.user_id} ({current_email})")
    else:
        print(f"\n❌ No link found for athlete {athlete_id}")

    # Check activities for this athlete
    print(f"\n📊 Activities for athlete {athlete_id}:")
    activities = (
        session.query(Activity)
        .filter_by(athlete_id=athlete_id)
        .order_by(Activity.start_date.desc())
        .limit(10)
        .all()
    )

    if activities:
        print(f"   Found {len(activities)} recent activities")
        for act in activities[:5]:
            user_match = "✅" if act.user_id == user_id else "❌"
            print(
                f"   {user_match} {act.start_date.strftime('%Y-%m-%d')} - {act.name[:40]}"
            )
            print(f"      user_id: {act.user_id}")
    else:
        print("   No activities found")

    # Check today's activities
    today = datetime.utcnow().date()
    today_activities = (
        session.query(Activity)
        .filter_by(athlete_id=athlete_id)
        .filter(Activity.start_date >= today)
        .all()
    )

    print(f"\n🏃 Today's activities (athlete {athlete_id}):")
    if today_activities:
        for act in today_activities:
            user_match = "✅" if act.user_id == user_id else "❌"
            print(f"   {user_match} {act.start_date} - {act.name}")
            print(f"      Activity ID: {act.activity_id}")
            print(f"      user_id: {act.user_id}")
    else:
        print("   No activities found for today")

    # Check token
    token = session.query(Token).filter_by(athlete_id=athlete_id).first()
    if token:
        print(f"\n🔑 Token status:")
        if token.is_revoked():
            print(f"   ❌ Token is REVOKED")
        else:
            expires_at = datetime.fromtimestamp(token.expires_at)
            now = datetime.utcnow()
            if expires_at < now:
                print(f"   ⚠️  Token is EXPIRED (expired: {expires_at})")
            else:
                print(f"   ✅ Token is VALID (expires: {expires_at})")
    else:
        print(f"\n❌ No token found for athlete {athlete_id}")

    # Summary and recommendations
    print(f"\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    if current_link and current_link.user_id != user_id:
        print("\n⚠️  ISSUE FOUND: Athlete is linked to wrong user account")
        print("   Options:")
        print("   1. Reconnect Strava via OAuth (will update the link)")
        print("   2. Manually update the link in database")
    elif not current_link:
        print("\n⚠️  ISSUE FOUND: No link exists for this athlete")
        print("   Solution: Reconnect Strava via OAuth")
    else:
        print("\n✅ Link is correct, checking other issues...")
        if today_activities:
            print("   ✅ Today's run is in database!")
        else:
            print("   ⚠️  Today's run not found - check webhook events")

finally:
    session.close()

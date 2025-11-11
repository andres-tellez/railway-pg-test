#!/usr/bin/env python3
"""
Fix athlete 347085 link to point to correct user account.

This will:
1. Remove the old link (if exists)
2. Create new link to correct user_id
3. Update any activities to use correct user_id
"""

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

session = get_session()

try:
    athlete_id = 347085
    user_email = "andres.tellez@gmail.com"

    print("=" * 80)
    print("FIXING ATHLETE LINK")
    print("=" * 80)

    # Find user
    user = session.query(UserIdentity).filter_by(email=user_email).first()
    if not user:
        print(f"❌ User not found: {user_email}")
        exit(1)

    user_id = str(user.user_id)
    print(f"\n✅ User: {user_email}")
    print(f"   User ID: {user_id}")

    # Check current link
    current_link = (
        session.query(UserAthleteLink).filter_by(athlete_id=athlete_id).first()
    )

    if current_link:
        if current_link.user_id == user_id:
            print(f"\n✅ Link is already correct!")
            session.close()
            exit(0)

        print(f"\n⚠️  Found existing link to different user:")
        print(f"   Old user_id: {current_link.user_id}")
        print(f"   Removing old link...")
        session.delete(current_link)
        session.flush()

    # Create new link
    print(f"\n🔗 Creating new link...")
    new_link = UserAthleteLink(user_id=user_id, athlete_id=athlete_id)
    session.add(new_link)
    session.commit()

    print(f"✅ Link created successfully!")
    print(f"   User ID: {user_id}")
    print(f"   Athlete ID: {athlete_id}")

    # Update activities to use correct user_id
    print(f"\n🔄 Updating activities...")
    activities_updated = (
        session.query(Activity)
        .filter_by(athlete_id=athlete_id)
        .update({Activity.user_id: user_id}, synchronize_session=False)
    )
    session.commit()

    print(f"✅ Updated {activities_updated} activities to use correct user_id")

    # Check today's activities
    from datetime import datetime

    today = datetime.utcnow().date()
    today_activities = (
        session.query(Activity)
        .filter_by(athlete_id=athlete_id, user_id=user_id)
        .filter(Activity.start_date >= today)
        .all()
    )

    print(f"\n📊 Today's activities:")
    if today_activities:
        for act in today_activities:
            print(f"   ✅ {act.start_date} - {act.name} (ID: {act.activity_id})")
    else:
        print("   ⚠️  No activities found for today")
        print("   → The run may not have been synced yet")
        print("   → Try manual sync or check webhook events")

    print(f"\n✅ Fix complete!")
    print(f"\nNext steps:")
    print(f"   1. Check webhook events to see if today's run was received")
    print(
        f"   2. If not, manually fetch: POST /admin/fetch-activity/<activity_id>?athlete_id=347085"
    )
    print(f"   3. Or trigger sync: POST /admin/trigger-ingest/347085?lookback_days=1")

except Exception as e:
    session.rollback()
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
finally:
    session.close()

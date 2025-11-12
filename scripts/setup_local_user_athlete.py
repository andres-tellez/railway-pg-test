"""Setup user_athletes link in local database for migration."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment
load_dotenv(Path(".env.local"), override=False)

local_db_url = os.getenv("DATABASE_URL")
if not local_db_url:
    print("❌ DATABASE_URL not set")
    sys.exit(1)

# Get user_id from command line or use current logged-in user
if len(sys.argv) > 1:
    user_id = sys.argv[1]
else:
    # Get the most recent user_id from user_identity
    engine = create_engine(local_db_url)
    conn = engine.connect()
    result = conn.execute(text("SELECT user_id FROM user_identity LIMIT 1"))
    row = result.fetchone()
    if not row:
        print("❌ No users found in local database")
        print("   Usage: python scripts/setup_local_user_athlete.py <user_id>")
        print("   Or connect Strava first to create the user")
        sys.exit(1)
    user_id = str(row[0])
    conn.close()
    engine.dispose()

athlete_id = 347085

print("=" * 60)
print(f"Setting up user_athletes link")
print("=" * 60)
print(f"User ID: {user_id}")
print(f"Athlete ID: {athlete_id}")

try:
    engine = create_engine(local_db_url)
    session = sessionmaker(bind=engine)()

    # Check if user exists
    result = session.execute(
        text("SELECT user_id FROM user_identity WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    if not result.fetchone():
        print(f"❌ User {user_id} not found in user_identity")
        print("   Make sure you're logged in first")
        sys.exit(1)

    # Check if link already exists for this user
    result = session.execute(
        text("SELECT athlete_id FROM user_athletes WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    existing_user_link = result.fetchone()

    # Check if link already exists for this athlete
    result = session.execute(
        text("SELECT user_id FROM user_athletes WHERE athlete_id = :athlete_id"),
        {"athlete_id": athlete_id},
    )
    existing_athlete_link = result.fetchone()

    if existing_user_link:
        if existing_user_link[0] == athlete_id:
            print(
                f"✅ Link already exists: user_id={user_id} → athlete_id={athlete_id}"
            )
        else:
            old_athlete_id = existing_user_link[0]
            print(f"⚠️  User already linked to different athlete_id: {old_athlete_id}")
            print(f"   Updating to athlete_id={athlete_id}...")

            # Temporarily disable foreign key constraints
            session.execute(text("SET session_replication_role = replica"))

            # Update user_athletes first (create the target athlete_id entry)
            session.execute(
                text(
                    "UPDATE user_athletes SET athlete_id = :athlete_id WHERE user_id = :user_id"
                ),
                {"athlete_id": athlete_id, "user_id": user_id},
            )

            # Update tokens
            session.execute(
                text(
                    "UPDATE tokens SET athlete_id = :new_athlete_id WHERE athlete_id = :old_athlete_id"
                ),
                {"new_athlete_id": athlete_id, "old_athlete_id": old_athlete_id},
            )

            # Update activities
            session.execute(
                text(
                    "UPDATE activities SET athlete_id = :new_athlete_id WHERE athlete_id = :old_athlete_id"
                ),
                {"new_athlete_id": athlete_id, "old_athlete_id": old_athlete_id},
            )

            # Update strava_sync_status
            session.execute(
                text(
                    "UPDATE strava_sync_status SET athlete_id = :new_athlete_id WHERE athlete_id = :old_athlete_id"
                ),
                {"new_athlete_id": athlete_id, "old_athlete_id": old_athlete_id},
            )

            # Re-enable foreign key constraints
            session.execute(text("SET session_replication_role = DEFAULT"))
            session.commit()
            print(f"✅ Updated link: user_id={user_id} → athlete_id={athlete_id}")
    elif existing_athlete_link:
        if str(existing_athlete_link[0]) == user_id:
            print(
                f"✅ Link already exists: user_id={user_id} → athlete_id={athlete_id}"
            )
        else:
            print(
                f"⚠️  Athlete already linked to different user_id: {existing_athlete_link[0]}"
            )
            print(f"   Updating to user_id={user_id}...")
            session.execute(
                text(
                    "UPDATE user_athletes SET user_id = :user_id WHERE athlete_id = :athlete_id"
                ),
                {"user_id": user_id, "athlete_id": athlete_id},
            )
            session.commit()
            print(f"✅ Updated link: user_id={user_id} → athlete_id={athlete_id}")
    else:
        # Create new link
        session.execute(
            text(
                "INSERT INTO user_athletes (user_id, athlete_id) VALUES (:user_id, :athlete_id)"
            ),
            {"user_id": user_id, "athlete_id": athlete_id},
        )
        session.commit()
        print(f"✅ Created link: user_id={user_id} → athlete_id={athlete_id}")

    session.close()
    engine.dispose()

    print("\n✅ Setup complete! You can now run the migration script.")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

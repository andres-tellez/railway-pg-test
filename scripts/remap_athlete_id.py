#!/usr/bin/env python3
"""
Remap athlete_id from one value to another in local database.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment
env_local = Path(".env.local")
if env_local.exists():
    load_dotenv(env_local, override=False)

database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("❌ DATABASE_URL not set")
    sys.exit(1)

old_athlete_id = 190482332
new_athlete_id = 347085

print("=" * 60)
print(f"🔄 Remapping athlete_id: {old_athlete_id} → {new_athlete_id}")
print("=" * 60)

try:
    engine = create_engine(database_url)
    conn = engine.connect()

    # Get user_id for the athlete
    result = conn.execute(
        text("SELECT user_id FROM user_athletes WHERE athlete_id = :old"),
        {"old": old_athlete_id},
    )
    user_row = result.fetchone()
    if not user_row:
        print(f"❌ No user_athletes record found with athlete_id {old_athlete_id}")
        sys.exit(1)
    user_id = user_row[0]

    # Check if tokens exist
    result = conn.execute(
        text("SELECT COUNT(*) FROM tokens WHERE athlete_id = :old"),
        {"old": old_athlete_id},
    )
    token_count = result.fetchone()[0]

    # Strategy: Temporarily disable FK constraint, update everything, then re-enable
    print("\n1. Temporarily disabling foreign key constraints...")
    conn.execute(text("SET session_replication_role = replica"))

    print("\n2. Deleting tokens...")
    if token_count > 0:
        conn.execute(
            text("DELETE FROM tokens WHERE athlete_id = :old"), {"old": old_athlete_id}
        )
        print(f"   ✅ Deleted {token_count} tokens")
    else:
        print(f"   ℹ️  No tokens to delete")

    print("\n3. Updating activities...")
    result = conn.execute(
        text("UPDATE activities SET athlete_id = :new WHERE athlete_id = :old"),
        {"new": new_athlete_id, "old": old_athlete_id},
    )
    print(f"   ✅ Updated {result.rowcount} activities")

    print("\n4. Updating strava_sync_status...")
    result = conn.execute(
        text("UPDATE strava_sync_status SET athlete_id = :new WHERE athlete_id = :old"),
        {"new": new_athlete_id, "old": old_athlete_id},
    )
    print(f"   ✅ Updated {result.rowcount} sync status records")

    print("\n5. Updating user_athletes...")
    conn.execute(
        text("UPDATE user_athletes SET athlete_id = :new WHERE athlete_id = :old"),
        {"new": new_athlete_id, "old": old_athlete_id},
    )
    print(f"   ✅ Updated user_athletes")

    print("\n6. Re-enabling foreign key constraints...")
    conn.execute(text("SET session_replication_role = DEFAULT"))

    conn.commit()

    print("\n" + "=" * 60)
    print("✅ Remapping complete!")
    print("=" * 60)

    # Verify
    print("\n📊 Verification:")
    result = conn.execute(text("SELECT athlete_id FROM user_athletes"))
    print(f"   user_athletes athlete_id: {result.fetchone()[0]}")

    result = conn.execute(
        text("SELECT COUNT(*) FROM activities WHERE athlete_id = :id"),
        {"id": new_athlete_id},
    )
    print(f"   Activities with athlete_id {new_athlete_id}: {result.fetchone()[0]}")

    result = conn.execute(
        text("SELECT COUNT(*) FROM activities WHERE athlete_id = :id"),
        {"id": old_athlete_id},
    )
    old_count = result.fetchone()[0]
    if old_count > 0:
        print(f"   ⚠️  Warning: {old_count} activities still have old athlete_id")
    else:
        print(f"   ✅ No activities with old athlete_id remaining")

    conn.close()
    engine.dispose()

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

#!/usr/bin/env python3
"""
manual_sync_today.py

Manually sync today's activities to catch missed runs.
This fixes the timezone issue where runs might be missed.
"""

from datetime import datetime, timedelta
from sqlalchemy import text

from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import run_full_ingestion_and_enrichment

def main():
    """Sync today's activities for all athletes"""

    # Get today's UTC range (to catch any missed activities)
    today_utc = datetime.utcnow().date()
    yesterday_utc = today_utc - timedelta(days=1)

    # Fetch from yesterday to today (covers timezone differences)
    after = int(datetime.combine(yesterday_utc, datetime.min.time()).timestamp())
    before = int(datetime.combine(today_utc + timedelta(days=1), datetime.min.time()).timestamp())

    print(f"🕐 Syncing activities from: {yesterday_utc.isoformat()} to {today_utc.isoformat()} (UTC)")
    print(f"🔍 Timestamp range: {after} to {before}")
    print(f"🕐 Current UTC time: {datetime.utcnow()}")

    session = get_session()

    try:
        # Get all athletes
        rows = session.execute(
            text("SELECT user_id, athlete_id FROM public.user_athletes")
        ).fetchall()

        if not rows:
            print("❌ No athletes found in user_athletes table")
            return

        print(f"📡 Found {len(rows)} athletes to sync")

        for row in rows:
            athlete_id = row.athlete_id
            user_id = row.user_id

            print(f"\n📡 Syncing athlete {athlete_id} (user {user_id})")

            result = run_full_ingestion_and_enrichment(
                session,
                athlete_id,
                user_id=user_id,
                after=after,
                before=before,
                batch_size=10,
                per_page=200
            )

            print(f"✅ Result: {result}")
            session.commit()

    except Exception as e:
        print(f"❌ Error during sync: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()

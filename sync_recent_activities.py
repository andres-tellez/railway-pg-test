#!/usr/bin/env python
"""Sync recent activities using the full ingestion and enrichment service"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load staging environment
env_staging_path = Path(".env.staging")
if env_staging_path.exists():
    load_dotenv(env_staging_path, override=True)
    print(f"✅ Loaded staging environment from {env_staging_path}")
else:
    print("❌ .env.staging not found!")
    sys.exit(1)

from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)


def main():
    session = get_session()

    try:
        # Get the athlete_id (most active athlete)
        result = session.execute(
            """
            SELECT athlete_id, COUNT(*) as activity_count
            FROM activities
            GROUP BY athlete_id
            ORDER BY activity_count DESC
            LIMIT 1
        """
        ).fetchone()

        if not result:
            print(
                "❌ No activities found in database. You may need to connect Strava first."
            )
            return

        athlete_id = result[0]
        print(f"📊 Using athlete_id: {athlete_id}")

        # Get user_id for this athlete
        user_result = session.execute(
            """
            SELECT user_id FROM user_athletes WHERE athlete_id = :athlete_id LIMIT 1
        """,
            {"athlete_id": athlete_id},
        ).fetchone()

        if not user_result:
            print("❌ No user_id found for this athlete")
            return

        user_id = user_result[0]
        print(f"👤 Using user_id: {user_id}")

        # Set up time range for today (this morning's run)
        from datetime import datetime, timedelta

        today = datetime.utcnow().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())

        print(f"\n🔄 Running full ingestion and enrichment for today ({today})...")
        print(f"📅 Time range: {start_of_day} to {end_of_day}")
        print(
            "This will sync today's activities from Strava and enrich them with additional data."
        )

        # Run the full ingestion and enrichment for today only
        result = run_full_ingestion_and_enrichment(
            session=session,
            athlete_id=athlete_id,
            user_id=user_id,
            after=int(start_of_day.timestamp()),  # Start of today
            before=int(end_of_day.timestamp()),  # End of today
            max_activities=10,  # Limit to 10 activities for today
        )

        print(f"\n✅ Sync complete!")
        print(f"📊 Synced: {result.get('synced', 0)} activities")
        print(f"🔧 Enriched: {result.get('enriched', 0)} activities")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()

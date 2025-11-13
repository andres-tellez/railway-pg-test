#!/usr/bin/env python
"""Sync only today's activities"""
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Load local environment
load_dotenv(".env.local", override=True)

from src.db.db_session import get_session
from src.services.activity_service import ActivityIngestionService
from src.db.dao.activity_dao import ActivityDAO


def main():
    session = get_session()

    try:
        # Your actual IDs
        athlete_id = 347085
        user_id = "ddc21831-1b01-4cfc-82db-7632ab2cfba1"

        # Set up time range for today only
        today = datetime.utcnow().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())

        print(f"🔄 Syncing activities for today only ({today})...")
        print(f"📅 Time range: {start_of_day} to {end_of_day}")

        # Create service
        service = ActivityIngestionService(session, athlete_id)

        # Get activities between start and end of today
        activities = service.client.get_activities(
            after=int(start_of_day.timestamp()),
            before=int(end_of_day.timestamp()),
            per_page=50,
            limit=10,
        )

        # Filter for runs only
        runs = [a for a in activities if a.get("type") == "Run"]
        print(f"📊 Found {len(runs)} runs for today")

        if runs:
            # Add user_id to each activity
            for activity in runs:
                activity["user_id"] = user_id
                if "id" in activity:
                    activity["activity_id"] = activity.pop("id")

            # Save to database
            synced_count = ActivityDAO.upsert_activities(
                session, athlete_id, runs, user_id=user_id
            )
            print(f"✅ Synced {synced_count} activities to database")

            # Show what was synced
            for run in runs:
                print(
                    f"  - {run.get('name', 'Unnamed')} ({run.get('distance', 0):.2f} km)"
                )
        else:
            print("ℹ️ No runs found for today")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()


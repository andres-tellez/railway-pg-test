#!/usr/bin/env python3
"""
fetch_morning_run.py

Use webhook processor logic to manually fetch this morning's run.
This uses the same code as webhooks but for a specific activity.
"""

import os
import sys
from datetime import datetime, timedelta
from src.db.db_session import get_session
from src.db.models.user_athletes import UserAthleteLink
from src.db.models.activities import Activity
from src.db.dao.activity_dao import ActivityDAO
from src.services.strava_access_service import StravaClient
from src.services.token_service import get_valid_token
from sqlalchemy import text

def find_todays_runs():
    """Find runs from today that might be your 8:30AM run"""

    session = get_session()
    try:
        # Get today's date range
        today = datetime.utcnow().date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())

        print(f"🔍 Looking for runs from {start_of_day} to {end_of_day} UTC")

        # Get all athletes
        athletes = session.execute(
            text("SELECT user_id, athlete_id FROM public.user_athletes")
        ).fetchall()

        if not athletes:
            print("❌ No athletes found")
            return []

        print(f"📡 Found {len(athletes)} athletes")

        all_runs = []

        for row in athletes:
            athlete_id = row.athlete_id
            user_id = row.user_id

            print(f"\n🔍 Checking athlete {athlete_id} for today's runs...")

            try:
                # Get valid token
                access_token = get_valid_token(session, athlete_id)
                client = StravaClient(access_token)

                # Fetch today's activities
                activities = client.get_activities(
                    after=int(start_of_day.timestamp()),
                    before=int(end_of_day.timestamp()),
                    per_page=50
                )

                # Filter for runs
                runs = [a for a in activities if a.get("type") == "Run"]

                print(f"🏃 Found {len(runs)} runs today")

                for run in runs:
                    activity_id = run.get("id")
                    start_time = run.get("start_date_local", "unknown")
                    name = run.get("name", "Unknown")
                    distance = run.get("distance", 0) / 1609.34  # Convert to miles

                    print(f"   📍 Activity {activity_id}: {name}")
                    print(f"      🕐 Started: {start_time}")
                    print(f"      📏 Distance: {distance:.2f} miles")

                    all_runs.append({
                        'activity_id': activity_id,
                        'athlete_id': athlete_id,
                        'user_id': user_id,
                        'name': name,
                        'start_time': start_time,
                        'distance': distance,
                        'data': run
                    })

            except Exception as e:
                print(f"❌ Error fetching activities for athlete {athlete_id}: {e}")

        return all_runs

    finally:
        session.close()

def fetch_and_store_run(activity_data):
    """Use webhook processor logic to fetch and store a specific run"""

    session = get_session()
    try:
        activity_id = activity_data['activity_id']
        athlete_id = activity_data['athlete_id']
        user_id = activity_data['user_id']

        print(f"\n📥 Fetching and storing activity {activity_id}...")

        # Check if already exists
        existing = session.query(Activity).filter_by(activity_id=activity_id).first()

        if existing:
            print(f"ℹ️ Activity {activity_id} already exists in database")
            return True

        # Get valid token
        access_token = get_valid_token(session, athlete_id)
        client = StravaClient(access_token)

        # Fetch full activity details
        full_activity_data = client.get_activity(activity_id)

        if not full_activity_data:
            print(f"❌ Failed to fetch activity {activity_id}")
            return False

        # Prepare for storage (same as webhook processor)
        full_activity_data["activity_id"] = full_activity_data.pop("id", activity_id)
        full_activity_data["user_id"] = user_id

        # Store activity
        inserted = ActivityDAO.upsert_activities(
            session, athlete_id, [full_activity_data], user_id=user_id
        )

        if inserted > 0:
            print(f"✅ Successfully stored activity {activity_id}")
            session.commit()
            return True
        else:
            print(f"❌ Failed to store activity {activity_id}")
            return False

    except Exception as e:
        print(f"❌ Error processing activity {activity_id}: {e}")
        session.rollback()
        return False
    finally:
        session.close()

def main():
    """Main function to find and fetch today's runs"""

    print("🔍 Finding today's runs using webhook processor logic...")

    # Find all runs from today
    runs = find_todays_runs()

    if not runs:
        print("❌ No runs found for today")
        return

    print(f"\n🏃 Found {len(runs)} runs today:")

    for i, run in enumerate(runs):
        print(f"\n{i+1}. Activity {run['activity_id']}: {run['name']}")
        print(f"   🕐 Started: {run['start_time']}")
        print(f"   📏 Distance: {run['distance']:.2f} miles")

    # Ask user which one to fetch
    if len(runs) == 1:
        print(f"\n📥 Fetching the only run found...")
        fetch_and_store_run(runs[0])
    else:
        print(f"\n🤔 Multiple runs found. Please specify which one to fetch:")
        print("Enter the number (1-{}) or 'all' to fetch all: ".format(len(runs)), end="")

        choice = input().strip().lower()

        if choice == 'all':
            for run in runs:
                fetch_and_store_run(run)
        else:
            try:
                index = int(choice) - 1
                if 0 <= index < len(runs):
                    fetch_and_store_run(runs[index])
                else:
                    print("❌ Invalid choice")
            except ValueError:
                print("❌ Invalid input")

if __name__ == "__main__":
    main()

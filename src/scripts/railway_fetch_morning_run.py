#!/usr/bin/env python3
"""
railway_fetch_morning_run.py

Railway-compatible script to fetch today's runs using webhook logic.
Run this on Railway: railway run python -m src.scripts.railway_fetch_morning_run
"""

from datetime import datetime
from sqlalchemy import text

from src.db.db_session import get_session
from src.db.models.activities import Activity
from src.db.dao.activity_dao import ActivityDAO
from src.services.strava_access_service import StravaClient
from src.services.token_service import get_valid_token

def main():
    """Find and fetch today's runs using webhook processor logic"""

    print("🔍 Finding today's runs using webhook processor logic...")
    print(f"🕐 Current UTC time: {datetime.utcnow()}")

    session = get_session()

    try:
        # Get today's date range (UTC)
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
            return

        print(f"📡 Found {len(athletes)} athletes")

        runs_found = []

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

                    runs_found.append({
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

        if not runs_found:
            print("❌ No runs found for today")
            return

        print(f"\n🏃 Found {len(runs_found)} runs today - fetching all...")

        # Fetch and store all runs (using webhook processor logic)
        for run in runs_found:
            activity_id = run['activity_id']
            athlete_id = run['athlete_id']
            user_id = run['user_id']

            print(f"\n📥 Fetching and storing activity {activity_id}...")

            # Check if already exists
            existing = session.query(Activity).filter_by(activity_id=activity_id).first()

            if existing:
                print(f"ℹ️ Activity {activity_id} already exists in database")
                continue

            # Get valid token
            access_token = get_valid_token(session, athlete_id)
            client = StravaClient(access_token)

            # Fetch full activity details
            full_activity_data = client.get_activity(activity_id)

            if not full_activity_data:
                print(f"❌ Failed to fetch activity {activity_id}")
                continue

            # Prepare for storage (same as webhook processor)
            full_activity_data["activity_id"] = full_activity_data.pop("id", activity_id)
            full_activity_data["user_id"] = user_id

            # Store activity
            inserted = ActivityDAO.upsert_activities(
                session, athlete_id, [full_activity_data], user_id=user_id
            )

            if inserted > 0:
                print(f"✅ Successfully stored activity {activity_id}")
            else:
                print(f"❌ Failed to store activity {activity_id}")

        session.commit()
        print(f"\n🎉 Done! Processed {len(runs_found)} runs")

    except Exception as e:
        print(f"❌ Error during fetch: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()

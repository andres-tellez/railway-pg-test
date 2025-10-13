#!/usr/bin/env python
"""Check current activities and sync recent ones from Strava"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load staging environment
env_staging_path = Path(".env.staging")
if env_staging_path.exists():
    load_dotenv(env_staging_path, override=True)
    print(f"✅ Loaded staging environment from {env_staging_path}")
else:
    print("❌ .env.staging not found!")
    sys.exit(1)

from src.db.db_session import get_session
from src.db.dao.activity_stats_dao import ActivityStatsDAO
from src.services.activity_service import ActivityIngestionService

def main():
    session = get_session()
    
    try:
        # Get the athlete_id (you'll need to replace this with your actual athlete_id)
        # For now, let's find the most active athlete
        result = session.execute("""
            SELECT athlete_id, COUNT(*) as activity_count 
            FROM activities 
            GROUP BY athlete_id 
            ORDER BY activity_count DESC 
            LIMIT 1
        """).fetchone()
        
        if not result:
            print("❌ No activities found in database. You may need to sync first.")
            return
            
        athlete_id = result[0]
        print(f"📊 Using athlete_id: {athlete_id}")
        
        # Check recent activities (last 7 days)
        recent_activities = ActivityStatsDAO.get_recent_activities(session, athlete_id, 7)
        print(f"\n📅 Recent activities (last 7 days): {len(recent_activities)}")
        
        for activity in recent_activities:
            print(f"  - {activity.start_date.strftime('%Y-%m-%d %H:%M')}: {activity.name} ({activity.distance:.2f} km)")
        
        # Check if we need to sync more recent activities
        if len(recent_activities) == 0:
            print("\n🔄 No recent activities found. Syncing last 7 days from Strava...")
            
            # Create ingestion service
            service = ActivityIngestionService(session, athlete_id)
            
            # Sync last 7 days
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)
            
            synced_count = service.ingest_between(start_date, end_date, max_activities=50)
            print(f"✅ Synced {synced_count} activities from Strava")
            
            # Check again after sync
            recent_activities = ActivityStatsDAO.get_recent_activities(session, athlete_id, 7)
            print(f"\n📅 Recent activities after sync: {len(recent_activities)}")
            
            for activity in recent_activities:
                print(f"  - {activity.start_date.strftime('%Y-%m-%d %H:%M')}: {activity.name} ({activity.distance:.2f} km)")
        else:
            print(f"\n✅ Found {len(recent_activities)} recent activities. No sync needed.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    main()

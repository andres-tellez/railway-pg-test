# src/scripts/temp_test_ingest_activities.py

import sys
from src.db.db_session import get_session
from src.services.activity_service import ActivityIngestionService

def main():
    if len(sys.argv) != 2:
        print("Usage: python -m src.scripts.temp_test_ingest_activities <ATHLETE_ID>")
        return

    athlete_id = int(sys.argv[1])
    session = get_session()

    try:
        service = ActivityIngestionService(session, athlete_id)
        count = service.ingest_recent()
        print(f"✅ Synced {count} activities for athlete {athlete_id}")
    except Exception as e:
        print(f"🔥 Failed to ingest activities: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    main()

import argparse
from src.db.db_session import get_session
from src.services.strava_access_service import StravaClient
from src.db.dao.activity_dao import ActivityDAO
from src.services.token_service import get_valid_token

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete_id", type=int, required=True, help="Athlete ID")
    parser.add_argument("--activity_id", type=int, required=True, help="Activity ID to ingest")
    args = parser.parse_args()

    print("📥 Ingesting activity", args.activity_id)

    session = get_session()
    try:
        access_token = get_valid_token(session, args.athlete_id)
        client = StravaClient(access_token)
        activity_json = client.get_activity(args.activity_id)
        ActivityDAO.upsert_activities(session, args.athlete_id, [activity_json])
        print("✅ Activity ingested successfully")
    finally:
        session.close()
        print("🛑 DB session closed.")

if __name__ == "__main__":
    main()

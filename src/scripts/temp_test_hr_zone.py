import argparse
from src.db.db_session import get_session
from src.services.activity_service import enrich_one_activity_with_refresh
from sqlalchemy import text

def activity_exists(session, activity_id):
    result = session.execute(
        text("SELECT 1 FROM activities WHERE activity_id = :activity_id"),
        {"activity_id": activity_id}
    ).fetchone()
    return result is not None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--athlete_id", type=int, required=True, help="Athlete ID")
    parser.add_argument("--activity_id", type=int, required=True, help="Activity ID to test")
    args = parser.parse_args()

    print("🧪 Test started")
    print(f"🔎 Fetching activity {args.activity_id}")

    session = get_session()
    try:
        if not activity_exists(session, args.activity_id):
            print(f"❌ Activity {args.activity_id} not found in DB. Please ingest it first.")
            return

        result = enrich_one_activity_with_refresh(session, args.athlete_id, args.activity_id)
        print(f"✅ Enrichment result for activity {args.activity_id}: {result}")
    finally:
        session.close()
        print("🛑 DB session closed.")

if __name__ == "__main__":
    main()

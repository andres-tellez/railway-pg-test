import logging
from src.db.db_session import get_session
from src.services.activity_service import enrich_one_activity_with_refresh

logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    db = get_session()

    athlete_id = 347085                # Replace with the correct athlete ID if different
    activity_id = 14816481623

    try:
        print("🧪 Running enrichment for splits...")
        success = enrich_one_activity_with_refresh(db, athlete_id, activity_id)
        if success:
            print("✅ Enrichment completed successfully.")
        else:
            print("⚠️ Enrichment did not complete.")
    except Exception as e:
        print(f"🔥 Error: {e}")
    finally:
        db.close()
        print("🛑 DB session closed.")

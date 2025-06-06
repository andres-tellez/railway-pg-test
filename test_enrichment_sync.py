from src.db.db_session import get_session
from src.services.enrichment_sync import run_enrichment_batch

if __name__ == "__main__":
    athlete_id = 12345  # <-- replace with a valid athlete_id from your database

    session = get_session()
    try:
        count = run_enrichment_batch(session, athlete_id=athlete_id)
        print(f"✅ Enriched {count} activities")
    finally:
        session.close()

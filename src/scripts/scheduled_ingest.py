from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import run_full_ingestion_and_enrichment
from src.services.token_service import refresh_access_token, refresh_token_if_expired
import os

if __name__ == "__main__":
    print("🔍 DATABASE_URL at runtime:", os.getenv("DATABASE_URL"), flush=True)

    session = get_session()
    athlete_id = 347085

    # 🔁 Force refresh (for now)
    refresh_access_token(session, athlete_id)

    session.commit()
    session.expire_all()

    refresh_token_if_expired(session, athlete_id)

    run_full_ingestion_and_enrichment(session, athlete_id, lookback_days=1)

    session.close()

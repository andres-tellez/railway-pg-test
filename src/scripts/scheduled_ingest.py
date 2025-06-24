from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import run_full_ingestion_and_enrichment
from src.services.token_service import refresh_access_token  # Use only this

if __name__ == "__main__":
    session = get_session()
    athlete_id = 347085  # Replace with dynamic or loop if needed

    # 🔐 Force token refresh
    refresh_access_token(session, athlete_id)

    # 🚀 Run ingestion
    run_full_ingestion_and_enrichment(session, athlete_id, lookback_days=1)

    session.close()

# src/scripts/main_pipeline.py

import argparse
import logging
from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import run_full_ingestion_and_enrichment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orchestrate full sync + enrichment for existing athlete")
    parser.add_argument("--athlete_id", required=True, type=int)
    parser.add_argument("--lookback_days", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=10)

    args = parser.parse_args()

    session = get_session()
    try:
        run_full_ingestion_and_enrichment(
            session,
            args.athlete_id,
            lookback_days=args.lookback_days,
            batch_size=args.batch_size
        )
    except Exception as e:
        logger.exception(f"❌ Error in main_pipeline: {e}")
    finally:
        session.close()

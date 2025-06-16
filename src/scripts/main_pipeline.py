# src/scripts/main_pipeline.py

import argparse
import logging

from src.db.db_session import get_session
from src.db.dao.token_dao import get_tokens_sa
from src.services.token_service import get_valid_token
from src.services.activity_service import ActivityIngestionService
from src.services.activity_service import run_enrichment_batch  # ✅ Correct import

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def onboard_and_sync(athlete_id, lookback_days=30, batch_size=10):
    """
    Full sync pipeline for onboarding + enrichment.
    """

    session = get_session()

    try:
        logger.info(f"🚀 Starting onboard_and_sync for athlete {athlete_id}")

        tokens = get_tokens_sa(session, athlete_id)

        if not tokens:
            raise RuntimeError(
                f"No tokens found for athlete {athlete_id}. "
                "Please complete OAuth authorization first via /oauth/callback."
            )

        access_token = get_valid_token(session, athlete_id)
        logger.info(f"🟢 Retrieved valid access token for athlete {athlete_id}")

        # ✅ Ingestion orchestrator using new ingestion service
        ingestion_service = ActivityIngestionService(session, athlete_id)
        synced_count = ingestion_service.ingest_full_history(
            lookback_days=lookback_days
        )
        logger.info(f"✅ Synced {synced_count} activities")

        # ✅ Enrichment orchestration uses run_enrichment_batch()
        enriched_count = run_enrichment_batch(session, athlete_id, batch_size=batch_size)
        logger.info(f"✅ Enriched {enriched_count} activities")

        logger.info(f"🎯 Onboard and sync complete for athlete {athlete_id}")

    except Exception as e:
        logger.exception(f"❌ Failed during onboard_and_sync: {e}")

    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orchestrate full sync + enrichment for existing athlete")
    parser.add_argument("--athlete_id", required=True, type=int)
    parser.add_argument("--lookback_days", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=10)

    args = parser.parse_args()
    onboard_and_sync(args.athlete_id, args.lookback_days, args.batch_size)

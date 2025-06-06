# src/scripts/onboard_and_sync.py

import argparse
import logging

from src.db.db_session import get_session
from src.db.dao.token_dao import get_tokens_sa
from src.services.token_refresh import ensure_fresh_access_token
from src.services.activity_sync import sync_full_history
from src.services.enrichment import ActivityEnrichor
from src.utils.enrichment_debug_wrapper import EnrichmentDebugWrapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def onboard_and_sync(athlete_id, lookback_days=30, batch_size=10):
    """
    Full sync pipeline for onboarding + enrichment.
    """

    session = get_session()

    try:
        logger.info(f"🚀 Starting full onboard_and_sync for athlete {athlete_id}")

        tokens = get_tokens_sa(session, athlete_id)

        if not tokens:
            raise RuntimeError(
                f"No tokens found for athlete {athlete_id}. "
                "Please complete OAuth authorization first via /oauth/callback."
            )

        access_token = ensure_fresh_access_token(session, athlete_id)
        logger.info(f"🟢 Retrieved valid access token for athlete {athlete_id}")

        # Sync activities
        synced_count = sync_full_history(
            session,
            athlete_id,
            access_token,
            lookback_days=lookback_days
        )
        logger.info(f"✅ Synced {synced_count} activities.")

        # Build enrichment pipeline
        enrichor = ActivityEnrichor()

        # Wrap enrichment with debug instrumentation
        debug_wrapper = EnrichmentDebugWrapper(enrichor, session)
        enriched_count = debug_wrapper.enrich(athlete_id, batch_size=batch_size)
        logger.info(f"✅ Enriched {enriched_count} activities (with debug tracing).")

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

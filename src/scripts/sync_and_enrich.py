# src/scripts/sync_and_enrich.py

import argparse
from src.db.db_session import get_session
from src.services.activity_sync import sync_full_history
from src.services.enrichment_sync import run_enrichment_batch

def main(athlete_id: int, lookback_days: int, batch_size: int):
    session = get_session()

    try:
        # Step 1: Ensure valid token
        access_token = ensure_fresh_access_token(session, athlete_id)

        # Step 2: Sync activities
        synced_count = sync_full_history(
            session=session,
            athlete_id=athlete_id,
            access_token=access_token,
            lookback_days=lookback_days
        )
        print(f"✅ Sync complete — {synced_count} activities synced.")

        # Step 3: Enrich activities
        enriched_count = run_enrichment_batch(
            session=session,
            athlete_id=athlete_id,
            batch_size=batch_size
        )
        print(f"✅ Enrichment complete — {enriched_count} activities enriched.")

    except Exception as e:
        print(f"❌ Failed: {e}")

    finally:
        session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync and Enrich Activities for an Athlete")
    parser.add_argument("--athlete_id", type=int, required=True, help="Strava athlete ID")
    parser.add_argument("--lookback_days", type=int, default=30, help="Lookback window for sync (days)")
    parser.add_argument("--batch_size", type=int, default=20, help="Batch size for enrichment")

    args = parser.parse_args()
    main(args.athlete_id, args.lookback_days, args.batch_size)

# src/scripts/enrich_runner.py

import argparse
from src.db.db_session import get_session
from src.services.enrichment_sync import run_enrichment_batch

def main(athlete_id: int, batch_size: int):
    session = get_session()
    try:
        count = run_enrichment_batch(session, athlete_id, batch_size)
        print(f"✅ Enrichment complete — {count} activities processed for athlete {athlete_id}")
    except Exception as e:
        print(f"❌ Enrichment failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrichment Runner")
    parser.add_argument("athlete_id", type=int, help="Strava athlete ID to enrich")
    parser.add_argument("--batch", type=int, default=10, help="Batch size for enrichment")

    args = parser.parse_args()
    main(args.athlete_id, args.batch)

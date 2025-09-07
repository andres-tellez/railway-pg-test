# src/scripts/run_staging_cron.py

import argparse
from src.db.db_session import get_session
from src.db.dao.athlete_dao import get_all_athletes
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)


def main():
    parser = argparse.ArgumentParser(description="Run ingestion for all athletes")
    parser.add_argument("--lookback_days", type=int, default=1)
    parser.add_argument("--max_activities", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=10)
    parser.add_argument("--per_page", type=int, default=200)
    args = parser.parse_args()

    session = get_session()
    athletes = get_all_athletes(session)

    for athlete in athletes:
        print(f"🔄 Syncing athlete {athlete.strava_athlete_id}")
        run_full_ingestion_and_enrichment(
            session,
            athlete.strava_athlete_id,
            lookback_days=args.lookback_days,
            max_activities=args.max_activities,
            batch_size=args.batch_size,
            per_page=args.per_page,
        )
        session.commit()


if __name__ == "__main__":
    main()

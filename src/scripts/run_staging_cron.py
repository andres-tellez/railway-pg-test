# src/scripts/run_staging_cron.py

import argparse
from datetime import datetime, timedelta
from src.db.db_session import get_session
from src.db.dao.athlete_dao import get_all_athletes
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)


def main():
    parser = argparse.ArgumentParser(description="Run ingestion for all athletes")
    parser.add_argument("--batch_size", type=int, default=10)
    parser.add_argument("--per_page", type=int, default=200)
    args = parser.parse_args()

    # Get UTC midnight range for yesterday
    yesterday = datetime.utcnow().date() - timedelta(days=1)
    after = int(datetime.combine(yesterday, datetime.min.time()).timestamp())
    before = int(
        datetime.combine(yesterday + timedelta(days=1), datetime.min.time()).timestamp()
    )

    print(f"🕐 Targeting activities from: {yesterday.isoformat()} (UTC)")
    print(f"🔍 after: {after} | before: {before}")

    session = get_session()
    athletes = get_all_athletes(session)

    for athlete in athletes:
        print(f"🔄 Syncing athlete {athlete.strava_athlete_id}")
        run_full_ingestion_and_enrichment(
            session,
            athlete.strava_athlete_id,
            after=after,
            before=before,
            batch_size=args.batch_size,
            per_page=args.per_page,
        )
        session.commit()


if __name__ == "__main__":
    main()

# src/scripts/run_staging_cron.py

import argparse
from datetime import datetime, timedelta
from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)
from sqlalchemy import text


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

    # ✅ Fetch both athlete_id and user_id from mapping
    rows = session.execute(
        text("SELECT user_id, athlete_id FROM public.user_athletes")
    ).fetchall()

    for row in rows:
        athlete_id = row.athlete_id
        user_id = row.user_id
        print(f"📡 Syncing athlete {athlete_id} (user {user_id})")

        run_full_ingestion_and_enrichment(
            session,
            athlete_id,
            user_id=user_id,  # ✅ critical: link activities back to user
            after=after,
            before=before,
            batch_size=args.batch_size,
            per_page=args.per_page,
        )
        session.commit()


if __name__ == "__main__":
    main()

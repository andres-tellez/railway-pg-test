# src/scripts/run_staging_cron.py

"""
run_staging_cron.py

Fixed cron script that fetches yesterday + today UTC to catch missed activities.
This addresses timezone issues where runs might be missed.
"""

import argparse
from datetime import datetime, timedelta
from sqlalchemy import text

from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)


def main():
    """Run ingestion for all athletes with fixed timezone handling."""
    parser = argparse.ArgumentParser(description="Run ingestion for all athletes")
    parser.add_argument("--batch_size", type=int, default=10)
    parser.add_argument("--per_page", type=int, default=200)
    args = parser.parse_args()

    # Get UTC midnight range for yesterday AND today (to catch missed activities)
    today_utc = datetime.utcnow().date()
    yesterday_utc = today_utc - timedelta(days=1)

    # Fetch both yesterday and today to catch any missed activities
    after = int(datetime.combine(yesterday_utc, datetime.min.time()).timestamp())
    before = int(datetime.combine(today_utc + timedelta(days=1), datetime.min.time()).timestamp())

    print(
        f"🕐 Targeting activities from: {yesterday_utc.isoformat()} to "
        f"{today_utc.isoformat()} (UTC)"
    )
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

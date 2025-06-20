import argparse
import logging
from datetime import datetime
from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import run_full_ingestion_and_enrichment, ingest_specific_activity, ingest_between_dates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Orchestrate full sync + enrichment for existing athlete")
    parser.add_argument("--athlete_id", required=True, type=int)
    parser.add_argument("--lookback_days", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=10)
    parser.add_argument("--activity_id", type=int, help="Specific activity ID to sync")
    parser.add_argument("--start_date", type=parse_date, help="Start date YYYY-MM-DD")
    parser.add_argument("--end_date", type=parse_date, help="End date YYYY-MM-DD")

    args = parser.parse_args()

    session = get_session()
    try:
        if args.activity_id:
            # Call ingestion for a single activity
            ingest_specific_activity(session, args.athlete_id, args.activity_id)
        elif args.start_date and args.end_date:
            # Call ingestion for date range
            ingest_between_dates(session, args.athlete_id, args.start_date, args.end_date)
        else:
            # Default full ingestion
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

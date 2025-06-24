import argparse
import logging
import sys
import os
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()
import src.utils.config as config

from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
    ingest_specific_activity,
    ingest_between_dates,
)
from src.db.dao.token_dao import get_tokens_sa
from src.scripts import oauth_cli

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD.")

def main():
    print("⚙️ FLASK_ENV =", os.getenv("FLASK_ENV"))
    print("⚙️ config.DATABASE_URL =", config.DATABASE_URL)
    parser = argparse.ArgumentParser(description="Orchestrate full sync + enrichment for existing athlete")
    parser.add_argument("--athlete_id", required=True, type=int)
    parser.add_argument("--lookback_days", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=10)
    parser.add_argument("--activity_id", type=int, help="Specific activity ID to sync")
    parser.add_argument("--start_date", type=parse_date, help="Start date YYYY-MM-DD")
    parser.add_argument("--end_date", type=parse_date, help="End date YYYY-MM-DD")
    parser.add_argument("--max_activities", type=int, help="Maximum number of activities to ingest")
    parser.add_argument("--per_page", type=int, default=200, help="Number of results to fetch per API page")

    args = parser.parse_args()
    session = get_session()

    # Ensure token is available, or run OAuth flow
    try:
        tokens = get_tokens_sa(session, args.athlete_id)
    except Exception:
        tokens = None

    if not tokens:
        logger.info(f"🔐 No token found for athlete {args.athlete_id}. Launching OAuth flow...")
        oauth_cli.main(athlete_id_override=args.athlete_id)

    try:
        if args.activity_id:
            ingest_specific_activity(session, args.athlete_id, args.activity_id)
        elif args.start_date and args.end_date:
            ingest_between_dates(
                session,
                args.athlete_id,
                args.start_date,
                args.end_date,
                batch_size=args.batch_size,
                max_activities=args.max_activities,
                per_page=args.per_page
            )
        elif args.start_date or args.end_date:
            raise ValueError("Both --start_date and --end_date must be provided together.")
        else:
            run_full_ingestion_and_enrichment(
                session,
                args.athlete_id,
                lookback_days=args.lookback_days,
                batch_size=args.batch_size,
                max_activities=args.max_activities,
                per_page=args.per_page
            )
    except Exception as e:
        logger.exception(f"❌ Error in main_pipeline: {e}")
        sys.exit(1)
    finally:
        session.close()

    sys.exit(0)

if __name__ == "__main__":
    main()

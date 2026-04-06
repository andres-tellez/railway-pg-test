#!/usr/bin/env python3
"""
Generate weekly training insights for all qualifying users.

Intended to run as a Sunday evening cron (e.g. 5 PM CT) so the Mon–Sun week
ending that day is complete; Monday–Saturday runs use the prior completed week.
Idempotent: safe to re-run for the same week.

Usage:
    python scripts/generate_weekly_insights.py            # dev (last completed week)
    python scripts/generate_weekly_insights.py --prod      # prod
    python scripts/generate_weekly_insights.py --week 2026-03-16  # specific week (Monday date)
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.smartcoach_mobile_coach.weekly_insights_service import (
    generate_weekly_insight,
    get_users_with_easy_runs,
    last_completed_week_bounds,
)


def main():
    parser = argparse.ArgumentParser(description="Generate weekly training insights")
    parser.add_argument("--prod", action="store_true", help="Run against prod DB")
    parser.add_argument(
        "--week", type=str, help="Monday date (YYYY-MM-DD) of the target week"
    )
    args = parser.parse_args()

    env_key = "PROD_DATABASE_URL" if args.prod else "DATABASE_URL"
    db_url = os.environ.get(env_key)
    if not db_url:
        print(f"ERROR: {env_key} not set")
        sys.exit(1)

    if args.week:
        week_start = datetime.strptime(args.week, "%Y-%m-%d").date()
        week_end = week_start + timedelta(days=6)
    else:
        week_start, week_end = last_completed_week_bounds()

    label = "PROD" if args.prod else "DEV"
    print(f"\n[{label}] Generating insights for week {week_start} to {week_end}")

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        users = get_users_with_easy_runs(session, week_start, week_end)
        print(f"  Found {len(users)} user(s) with easy runs")

        for uid in users:
            ref = week_start + timedelta(days=7)
            result = generate_weekly_insight(session, uid, ref_date=ref)
            status = (
                "generated"
                if result.get("generated")
                else f"skipped ({result.get('reason', '?')})"
            )
            print(
                f"  User {uid[:8]}…: {status} — overall: {result.get('overall_band', '—')}"
            )

        print(f"\nDone. {len(users)} user(s) processed.")
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()

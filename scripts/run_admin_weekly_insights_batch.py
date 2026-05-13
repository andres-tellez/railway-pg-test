#!/usr/bin/env python3
"""
Run the same work as POST /admin/refresh-weekly-training-insights.

Refreshes six completed Mon–Sun weeks (oldest → newest) plus the current
in-progress week for users with easy runs in each window.

Usage:
  python scripts/run_admin_weekly_insights_batch.py
  python scripts/run_admin_weekly_insights_batch.py --prod

Requires DATABASE_URL, or PROD_DATABASE_URL when using --prod.
Loads .env.local from repo root if present (same pattern as generate_weekly_insights.py).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Admin weekly insights batch (DB direct)"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Use PROD_DATABASE_URL instead of DATABASE_URL",
    )
    args = parser.parse_args()

    env_key = "PROD_DATABASE_URL" if args.prod else "DATABASE_URL"
    db_url = os.environ.get(env_key)
    if not db_url:
        print(f"ERROR: {env_key} is not set.", file=sys.stderr)
        sys.exit(1)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from src.services.admin_weekly_insights_batch_service import (
        run_weekly_insights_admin_batch,
    )

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        payload = run_weekly_insights_admin_batch(session)
        if payload["six_completed_weeks"]["totals"].get("errors", 0) or payload[
            "current_week_in_progress"
        ].get("errors", 0):
            payload["status"] = "partial"
        else:
            payload["status"] = "success"
        print(json.dumps(payload, indent=2, default=str))
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()

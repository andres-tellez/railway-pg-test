#!/usr/bin/env python3
"""
Backfill Tier 2 execution analytics on activities, then optionally regenerate
weekly_training_insights snapshots.

Prerequisites:
  1. Run scripts/sql/add_activity_execution_analytics_columns.sql on the database.
  2. Deploy execution_analytics producer code.

Usage:
    python scripts/backfill_execution_analytics.py --prod
    python scripts/backfill_execution_analytics.py --prod --user-id <uuid>
    python scripts/backfill_execution_analytics.py --prod --skip-weekly-insights
    python scripts/backfill_execution_analytics.py --prod --force-all
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

# Register ORM mappers for Activity FK targets before flush/commit.
from src.db.models.activities import Activity  # noqa: F401
from src.db.models.runner_zone_profiles import RunnerZoneProfile  # noqa: F401
from src.db.models.splits import Split  # noqa: F401
from src.db.models.user_athletes import UserAthleteLink  # noqa: F401
from src.db.models.user_identity import UserIdentity  # noqa: F401

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.execution_analytics_recompute_service import (
    recompute_recent_execution_kpis,
    recompute_stale_execution_kpis_for_user,
)
from src.smartcoach_mobile_coach.execution_analytics.producer import (
    EXECUTION_ANALYTICS_VERSION,
    refresh_activity_execution_kpis,
)
from src.smartcoach_mobile_coach.weekly_insights_service import (
    generate_weekly_insight,
    last_completed_week_bounds,
)


def _users_with_profile(session) -> list[str]:
    rows = session.execute(
        text(
            """
            SELECT user_id::text
            FROM runner_zone_profiles
            WHERE hr_z2_low IS NOT NULL
            ORDER BY user_id
            """
        )
    ).fetchall()
    return [str(row.user_id) for row in rows]


def _backfill_user(
    session,
    user_id: str,
    *,
    force_all: bool,
    lookback_days: int | None,
) -> int:
    if force_all:
        ids = [
            int(row.activity_id)
            for row in session.query(Activity.activity_id)
            .filter(Activity.user_id == user_id, Activity.type == "Run")
            .order_by(Activity.activity_id)
            .all()
        ]
        if not ids:
            return 0
        batch = 100
        total = 0
        for offset in range(0, len(ids), batch):
            chunk = ids[offset : offset + batch]
            total += refresh_activity_execution_kpis(
                session,
                user_id,
                activity_ids=chunk,
                commit=True,
            )
        return total

    if lookback_days is not None:
        return recompute_recent_execution_kpis(
            session, user_id, days=lookback_days, commit=True
        )
    return recompute_stale_execution_kpis_for_user(session, user_id, commit=True)


def _regenerate_weekly_insights(session, user_id: str, weeks: int) -> None:
    today = date.today()
    last_completed_monday, _ = last_completed_week_bounds(today)
    oldest = last_completed_monday - timedelta(weeks=max(0, weeks - 1))

    for i in range(weeks):
        week_monday = oldest + timedelta(weeks=i)
        ref_date = week_monday + timedelta(days=7)
        generate_weekly_insight(
            session,
            user_id,
            ref_date=ref_date,
            insight_week="completed",
        )

    generate_weekly_insight(
        session,
        user_id,
        ref_date=today,
        insight_week="in_progress",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill execution analytics")
    parser.add_argument("--prod", action="store_true", help="Use PROD_DATABASE_URL")
    parser.add_argument("--user-id", type=str, help="Single user UUID")
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="Recompute every run (ignore staleness/version)",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Only recompute runs in the last N days (unless --force-all)",
    )
    parser.add_argument(
        "--skip-weekly-insights",
        action="store_true",
        help="Skip weekly_training_insights regeneration",
    )
    parser.add_argument(
        "--weekly-weeks",
        type=int,
        default=6,
        help="Completed weeks to regenerate (default 6)",
    )
    args = parser.parse_args()

    env_key = "PROD_DATABASE_URL" if args.prod else "DATABASE_URL"
    db_url = os.environ.get(env_key)
    if not db_url:
        print(f"ERROR: {env_key} not set")
        sys.exit(1)

    label = "PROD" if args.prod else "DEV"
    print(f"\n[{label}] Backfill execution_analytics v{EXECUTION_ANALYTICS_VERSION}")

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        user_ids = [args.user_id] if args.user_id else _users_with_profile(session)
        print(f"  Users to process: {len(user_ids)}")

        for uid in user_ids:
            updated = _backfill_user(
                session,
                uid,
                force_all=args.force_all,
                lookback_days=args.lookback_days,
            )
            print(f"  User {uid[:8]}…: {updated} run(s) updated")
            if not args.skip_weekly_insights:
                _regenerate_weekly_insights(session, uid, args.weekly_weeks)
                print(f"  User {uid[:8]}…: weekly insights regenerated")

        print("\nDone.")
    finally:
        session.close()


if __name__ == "__main__":
    main()

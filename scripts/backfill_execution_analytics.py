#!/usr/bin/env python3
"""
Backfill Tier 2 execution analytics on activities, then optionally regenerate
weekly_training_insights snapshots.

Prerequisites:
  1. Run scripts/sql/add_activity_execution_analytics_columns.sql on the database.
  2. Deploy execution_analytics producer code.

Usage:
    python scripts/backfill_execution_analytics.py --prod
    python scripts/backfill_execution_analytics.py --staging --user-id <uuid>
    python scripts/backfill_execution_analytics.py --prod --user-id <uuid>
    python scripts/backfill_execution_analytics.py --prod --skip-weekly-insights
    python scripts/backfill_execution_analytics.py --prod --force-all

``--staging`` uses ``STAGING_DATABASE_URL`` from ``.env.local`` (Railway DB behind
``https://api.smartcoach.dev``). Default (no flag) still uses ``DATABASE_URL``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

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
from src.services.weekly_insights_reconcile_service import ensure_user_weekly_insights


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


def _resolve_database_target(*, prod: bool, staging: bool) -> tuple[str, str]:
    if prod and staging:
        print("ERROR: use only one of --prod or --staging")
        sys.exit(1)
    if staging:
        return "STAGING_DATABASE_URL", "STAGING"
    if prod:
        return "PROD_DATABASE_URL", "PROD"
    return "DATABASE_URL", "DEV"


def _database_host_label(db_url: str) -> str:
    parsed = urlparse(db_url.replace("postgresql+psycopg2://", "postgresql://", 1))
    host = parsed.hostname or "(unknown host)"
    port = parsed.port
    dbname = (parsed.path or "").lstrip("/") or "railway"
    return f"{host}:{port}/{dbname}" if port else f"{host}/{dbname}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill execution analytics")
    parser.add_argument("--prod", action="store_true", help="Use PROD_DATABASE_URL")
    parser.add_argument(
        "--staging",
        action="store_true",
        help="Use STAGING_DATABASE_URL (api.smartcoach.dev Postgres)",
    )
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

    env_key, label = _resolve_database_target(prod=args.prod, staging=args.staging)
    db_url = os.environ.get(env_key)
    if not db_url:
        hint = (
            "Add STAGING_DATABASE_URL to .env.local (copy DATABASE_URL from "
            "Railway staging API service)."
            if args.staging
            else f"Set {env_key} in .env.local"
        )
        print(f"ERROR: {env_key} not set. {hint}")
        sys.exit(1)

    print(f"\n[{label}] Backfill execution_analytics v{EXECUTION_ANALYTICS_VERSION}")
    print(f"  Database: {_database_host_label(db_url)}")

    engine = create_engine(db_url, connect_args={"connect_timeout": 30})
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
                result = ensure_user_weekly_insights(
                    session,
                    uid,
                    weeks=args.weekly_weeks,
                    include_current_week=True,
                )
                print(
                    f"  User {uid[:8]}…: weekly reconcile "
                    f"summary={result.get('summary')}"
                )

        print("\nDone.")
    finally:
        session.close()


if __name__ == "__main__":
    main()

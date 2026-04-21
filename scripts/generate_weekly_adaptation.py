#!/usr/bin/env python3
"""
Generate end-of-week adaptive plan rebuilds for active plans.

Intended to run as a weekly job (typically Monday before weekly insights) to
rebuild the upcoming week based on the just-completed week's execution.

Usage:
    python scripts/generate_weekly_adaptation.py
    python scripts/generate_weekly_adaptation.py --dry-run
    python scripts/generate_weekly_adaptation.py --prod --dry-run
    python scripts/generate_weekly_adaptation.py --plan-id 123
    python scripts/generate_weekly_adaptation.py --user-id <uuid>
    python scripts/generate_weekly_adaptation.py --today 2026-04-20
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import and_, create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

from src.db.models.plans import Plan
from src.services.training_plan.weekly_rebuild_service import WeeklyRebuildService
from src.utils.date_helpers import get_next_monday


def calculate_upcoming_week_num(race_date: date, today: date) -> Optional[int]:
    """
    Calculate the upcoming training week number from race date and current date.

    Week numbering follows the current rebuild scheduler behavior:
    - derive next Monday as start of upcoming week
    - compute whole weeks between that Monday and race date
    - return None when race is too close/past for another full week rebuild
    """
    upcoming_monday = get_next_monday(today)
    days_until_race = (race_date - upcoming_monday).days
    if days_until_race < 7:
        return None

    week_num = days_until_race // 7
    return week_num if week_num > 0 else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate adaptive weekly plan rebuilds"
    )
    parser.add_argument("--prod", action="store_true", help="Run against prod DB")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview rebuild decisions without writing changes",
    )
    parser.add_argument(
        "--plan-id",
        type=int,
        help="Only process one plan id",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        help="Only process plans for one user id",
    )
    parser.add_argument(
        "--today",
        type=str,
        help="Override current date (YYYY-MM-DD) for deterministic runs",
    )
    return parser.parse_args()


def _resolve_today(raw_today: Optional[str]) -> date:
    if not raw_today:
        return date.today()
    return datetime.strptime(raw_today, "%Y-%m-%d").date()


def main() -> int:
    args = parse_args()

    env_key = "PROD_DATABASE_URL" if args.prod else "DATABASE_URL"
    db_url = os.environ.get(env_key)
    if not db_url:
        print(f"ERROR: {env_key} not set")
        return 1

    today = _resolve_today(args.today)
    mode = "PROD" if args.prod else "DEV"
    print(
        f"\n[{mode}] Weekly adaptation run ({'DRY RUN' if args.dry_run else 'LIVE'}) for {today}"
    )

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    rebuilt_count = 0
    dry_run_count = 0
    skipped_count = 0
    error_count = 0

    try:
        query = session.query(Plan).filter(Plan.is_active.is_(True))
        if args.plan_id:
            query = query.filter(Plan.id == args.plan_id)
        if args.user_id:
            query = query.filter(Plan.user_id == args.user_id)

        plans = query.order_by(Plan.id.asc()).all()
        if not plans:
            print("  No active plans found for the selected filters.")
            return 0

        print(f"  Found {len(plans)} active plan(s)")
        rebuild_service = WeeklyRebuildService()

        for plan in plans:
            if not plan.race_date:
                print(f"  Plan {plan.id}: skipped (missing race_date)")
                skipped_count += 1
                continue

            upcoming_week_num = calculate_upcoming_week_num(plan.race_date, today)
            if upcoming_week_num is None:
                print(f"  Plan {plan.id}: skipped (no upcoming week to rebuild)")
                skipped_count += 1
                continue

            if args.dry_run:
                print(
                    f"  Plan {plan.id} (user={plan.user_id}): would rebuild week {upcoming_week_num}"
                )
                dry_run_count += 1
                continue

            try:
                result = rebuild_service.rebuild_week(
                    session=session,
                    plan_id=plan.id,
                    week_num=upcoming_week_num,
                    previous_week_logs=None,
                    initial_seed=None,
                )
                session.commit()
                decision = result.get("adjustment_decision")
                decision_type = decision.decision_type if decision else "none"
                print(
                    f"  Plan {plan.id}: rebuilt week {upcoming_week_num} "
                    f"(decision={decision_type}, pace_adjusted={result.get('pace_adjusted', False)})"
                )
                rebuilt_count += 1
            except Exception as exc:
                session.rollback()
                print(
                    f"  Plan {plan.id}: error rebuilding week {upcoming_week_num} ({exc})"
                )
                error_count += 1

        print(
            "\nDone. "
            f"rebuilt={rebuilt_count}, dry_run_previewed={dry_run_count}, "
            f"skipped={skipped_count}, errors={error_count}"
        )
        return 1 if error_count > 0 else 0
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

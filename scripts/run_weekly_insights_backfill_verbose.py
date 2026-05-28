#!/usr/bin/env python3
"""Weekly insights backfill with per-user progress (same scope as admin batch)."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.smartcoach_mobile_coach.weekly_insights_service import (
    calendar_week_containing,
    generate_weekly_insight,
    get_users_with_easy_runs,
    last_completed_week_bounds,
)


def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("ERROR: DATABASE_URL is not set.")

    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 60},
    )
    Session = sessionmaker(bind=engine)
    session = Session()
    totals = {"generated": 0, "skipped": 0, "errors": 0}

    try:
        last_monday, _ = last_completed_week_bounds()
        oldest = last_monday - timedelta(weeks=5)

        for i in range(6):
            week_start = oldest + timedelta(weeks=i)
            week_end = week_start + timedelta(days=6)
            ref_date = week_start + timedelta(days=7)
            users = get_users_with_easy_runs(session, week_start, week_end)
            print(f"Week {week_start}..{week_end}: {len(users)} user(s)", flush=True)
            for uid in users:
                try:
                    result = generate_weekly_insight(
                        session,
                        uid,
                        ref_date=ref_date,
                        insight_week="completed",
                    )
                    if result.get("generated"):
                        totals["generated"] += 1
                        overall = result.get("overall_band", "—")
                        print(f"  {uid[:8]} generated overall={overall}", flush=True)
                    else:
                        totals["skipped"] += 1
                        reason = result.get("reason", "?")
                        print(f"  {uid[:8]} skipped ({reason})", flush=True)
                except Exception as exc:
                    totals["errors"] += 1
                    print(f"  {uid[:8]} ERROR: {exc}", flush=True)

        today = date.today()
        cur_start, cur_end = calendar_week_containing(today)
        kpi_end = min(today, cur_end)
        users = get_users_with_easy_runs(session, cur_start, kpi_end)
        print(f"In-progress {cur_start}..{kpi_end}: {len(users)} user(s)", flush=True)
        for uid in users:
            try:
                result = generate_weekly_insight(
                    session,
                    uid,
                    ref_date=today,
                    insight_week="in_progress",
                )
                if result.get("generated"):
                    totals["generated"] += 1
                    overall = result.get("overall_band", "—")
                    print(f"  {uid[:8]} generated overall={overall}", flush=True)
                else:
                    totals["skipped"] += 1
                    reason = result.get("reason", "?")
                    print(f"  {uid[:8]} skipped ({reason})", flush=True)
            except Exception as exc:
                totals["errors"] += 1
                print(f"  {uid[:8]} ERROR: {exc}", flush=True)

        print(f"DONE {totals}", flush=True)
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()

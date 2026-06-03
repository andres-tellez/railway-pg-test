#!/usr/bin/env python3
"""
A1 staging finish: apply threshold DDL, backfill execution analytics, verify weekly-history.

Requires STAGING_DATABASE_URL in .env.local (Railway public URL for api.smartcoach.dev Postgres)
or pass --url.

Usage:
  python scripts/run_a1_staging_finish.py
  python scripts/run_a1_staging_finish.py --user-id 149cd9b1-20a8-41b8-a514-b688b4dca868
  python scripts/run_a1_staging_finish.py --url "postgresql://..." --skip-sql
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ORM registration
from src.db.models.activities import Activity  # noqa: F401
from src.db.models.runner_zone_profiles import RunnerZoneProfile  # noqa: F401
from src.db.models.splits import Split  # noqa: F401
from src.db.models.user_athletes import UserAthleteLink  # noqa: F401
from src.db.models.user_identity import UserIdentity  # noqa: F401

from src.services.execution_analytics_recompute_service import (
    recompute_stale_execution_kpis_for_user,
)
from src.services.weekly_insights_reconcile_service import ensure_user_weekly_insights
from src.smartcoach_mobile_coach.execution_analytics.producer import (
    EXECUTION_ANALYTICS_VERSION,
)
from src.smartcoach_mobile_coach.weekly_insights_service import (
    get_weekly_insight_history,
)

SQL_FILE = (
    Path(__file__).resolve().parent
    / "sql"
    / "add_activity_threshold_segment_columns.sql"
)
DEFAULT_USER = "149cd9b1-20a8-41b8-a514-b688b4dca868"


def _host_label(url: str) -> str:
    p = urlparse(url.replace("postgresql+psycopg2://", "postgresql://", 1))
    return f"{p.hostname}:{p.port}/{ (p.path or '').lstrip('/') or 'railway'}"


def _count_threshold_fields(session, user_id: str) -> dict:
    row = session.execute(
        text(
            """
            SELECT
              COUNT(*) FILTER (WHERE type = 'Run') AS runs,
              COUNT(*) FILTER (
                WHERE type = 'Run' AND threshold_segment_pace_min_per_mi IS NOT NULL
              ) AS pace_populated,
              COUNT(*) FILTER (
                WHERE type = 'Run' AND insights_system = 'threshold'
              ) AS insights_threshold
            FROM activities
            WHERE user_id::text = :u
            """
        ),
        {"u": user_id},
    ).one()
    return {
        "runs": int(row.runs or 0),
        "threshold_segment_pace_populated": int(row.pace_populated or 0),
        "insights_system_threshold": int(row.insights_threshold or 0),
    }


def _apply_sql(engine) -> None:
    ddl = SQL_FILE.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(ddl))
    print(f"  SQL applied from {SQL_FILE.name}")


def _threshold_api_summary(payload: dict) -> dict:
    systems = payload.get("systems") or {}
    thr = systems.get("threshold") or {}
    weekly = thr.get("weekly_data") or []
    with_pace = [
        p for p in weekly if p.get("threshold_segment_pace_min_per_mi") is not None
    ]
    with_band = [p for p in weekly if p.get("threshold_pace_progress_band")]
    easy = systems.get("easy") or {}
    tempo = systems.get("tempo") or {}
    return {
        "has_history": payload.get("has_history"),
        "has_systems_threshold": "threshold" in systems,
        "threshold_weekly_len": len(weekly),
        "threshold_rows_with_segment_pace": len(with_pace),
        "threshold_rows_with_progress_band": len(with_band),
        "easy_weekly_len": len(easy.get("weekly_data") or []),
        "tempo_weekly_len": len(tempo.get("weekly_data") or []),
        "sample_threshold_point": weekly[0] if weekly else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Finish A1 on staging Postgres")
    parser.add_argument(
        "--url", help="Staging Postgres URL (overrides STAGING_DATABASE_URL)"
    )
    parser.add_argument("--user-id", default=DEFAULT_USER)
    parser.add_argument("--skip-sql", action="store_true")
    parser.add_argument("--skip-backfill", action="store_true")
    parser.add_argument("--weekly-weeks", type=int, default=6)
    args = parser.parse_args()

    db_url = args.url or os.environ.get("STAGING_DATABASE_URL")
    if not db_url:
        print(
            "ERROR: set STAGING_DATABASE_URL in .env.local or pass --url\n"
            "  (copy public DATABASE_URL from Railway → Staging service → Postgres)",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[STAGING] host={_host_label(db_url)}")
    print(f"  execution_analytics_version={EXECUTION_ANALYTICS_VERSION}")

    engine = create_engine(db_url, connect_args={"connect_timeout": 60})
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        before = _count_threshold_fields(session, args.user_id)
        print("  BEFORE:", json.dumps(before))

        if not args.skip_sql:
            _apply_sql(engine)
            session.commit()

        if not args.skip_backfill:
            updated = recompute_stale_execution_kpis_for_user(
                session, args.user_id, commit=True
            )
            print(f"  execution backfill updated_runs={updated}")
            reconcile = ensure_user_weekly_insights(
                session,
                args.user_id,
                weeks=args.weekly_weeks,
                include_current_week=True,
            )
            print(f"  weekly reconcile={json.dumps(reconcile.get('summary'))}")

        after = _count_threshold_fields(session, args.user_id)
        print("  AFTER:", json.dumps(after))

        payload = get_weekly_insight_history(
            session, args.user_id, weeks=args.weekly_weeks
        )
        summary = _threshold_api_summary(payload)
        print("  API-shaped weekly-history:", json.dumps(summary, indent=2))
        if summary.get("sample_threshold_point"):
            print(
                "  sample systems.threshold.weekly_data[0]:",
                json.dumps(summary["sample_threshold_point"], indent=2),
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()

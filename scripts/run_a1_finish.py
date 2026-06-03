#!/usr/bin/env python3
"""
Finish A1 (Threshold pace backend) on a target Postgres: DDL, backfill, weekly-history check.

Use --prod for api.prod.smartcoach.dev (PROD_DATABASE_URL).
Use --staging only when validating api.smartcoach.dev (STAGING_DATABASE_URL).
Or pass --url for a one-off connection string.

Usage:
  python scripts/run_a1_finish.py --prod
  python scripts/run_a1_finish.py --prod --user-id 149cd9b1-20a8-41b8-a514-b688b4dca868
  python scripts/run_a1_finish.py --prod --force-all
  python scripts/run_a1_finish.py --staging --user-id <uuid>
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
    refresh_activity_execution_kpis,
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


def _resolve_target(*, prod: bool, staging: bool, url: str | None) -> tuple[str, str]:
    if sum((bool(prod), bool(staging), bool(url))) > 1:
        print("ERROR: use only one of --prod, --staging, or --url", file=sys.stderr)
        sys.exit(1)
    if url:
        return url, "CUSTOM"
    if prod:
        key = "PROD_DATABASE_URL"
        label = "PROD"
    elif staging:
        key = "STAGING_DATABASE_URL"
        label = "STAGING"
    else:
        print("ERROR: pass --prod, --staging, or --url", file=sys.stderr)
        sys.exit(1)
    db_url = os.environ.get(key)
    if not db_url:
        print(f"ERROR: {key} not set in .env.local", file=sys.stderr)
        sys.exit(1)
    return db_url, label


def _host_label(url: str) -> str:
    p = urlparse(url.replace("postgresql+psycopg2://", "postgresql://", 1))
    return f"{p.hostname}:{p.port}/{(p.path or '').lstrip('/') or 'railway'}"


def _threshold_columns_exist(conn) -> bool:
    n = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'activities'
              AND column_name = 'threshold_segment_pace_min_per_mi'
            """
        )
    ).scalar()
    return int(n or 0) > 0


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


def _backfill_user(session, user_id: str, *, force_all: bool) -> int:
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
        total = 0
        for offset in range(0, len(ids), 100):
            chunk = ids[offset : offset + 100]
            total += refresh_activity_execution_kpis(
                session, user_id, activity_ids=chunk, commit=True
            )
        return total
    return recompute_stale_execution_kpis_for_user(session, user_id, commit=True)


def _threshold_api_summary(payload: dict) -> dict:
    systems = payload.get("systems") or {}
    thr = systems.get("threshold") or {}
    weekly = thr.get("weekly_data") or []
    with_pace = [
        p for p in weekly if p.get("threshold_segment_pace_min_per_mi") is not None
    ]
    easy = systems.get("easy") or {}
    tempo = systems.get("tempo") or {}
    return {
        "has_history": payload.get("has_history"),
        "has_systems_threshold": "threshold" in systems,
        "has_systems_easy": "easy" in systems,
        "has_systems_tempo": "tempo" in systems,
        "threshold_weekly_len": len(weekly),
        "threshold_rows_with_segment_pace": len(with_pace),
        "easy_weekly_len": len(easy.get("weekly_data") or []),
        "tempo_weekly_len": len(tempo.get("weekly_data") or []),
        "easy_pace_target": (easy.get("pace_target_display") or "").strip() or None,
        "tempo_pace_target": (tempo.get("pace_target_display") or "").strip() or None,
        "sample_threshold_point": weekly[0] if weekly else None,
    }


def _verify_a1_contract(summary: dict) -> list[str]:
    failures: list[str] = []
    if not summary.get("has_systems_threshold"):
        failures.append("systems.threshold missing")
    elif summary.get("threshold_weekly_len", 0) <= 0:
        failures.append("systems.threshold.weekly_data empty")
    elif summary.get("threshold_rows_with_segment_pace", 0) < 1:
        failures.append("no threshold_segment_pace_min_per_mi in weekly_data")
    if not summary.get("has_systems_easy"):
        failures.append("systems.easy missing")
    if not summary.get("has_systems_tempo"):
        failures.append("systems.tempo missing")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finish A1 on prod or staging Postgres"
    )
    parser.add_argument("--prod", action="store_true", help="PROD_DATABASE_URL")
    parser.add_argument(
        "--staging",
        action="store_true",
        help="STAGING_DATABASE_URL (api.smartcoach.dev only)",
    )
    parser.add_argument("--url", help="Override database URL")
    parser.add_argument("--user-id", default=DEFAULT_USER)
    parser.add_argument("--skip-sql", action="store_true")
    parser.add_argument("--skip-backfill", action="store_true")
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="Recompute every run (not only stale)",
    )
    parser.add_argument("--weekly-weeks", type=int, default=6)
    args = parser.parse_args()

    db_url, label = _resolve_target(prod=args.prod, staging=args.staging, url=args.url)

    print(f"[{label}] host={_host_label(db_url)}")
    print(f"  execution_analytics_version={EXECUTION_ANALYTICS_VERSION}")

    engine = create_engine(db_url, connect_args={"connect_timeout": 60})
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        with engine.connect() as conn:
            if not _threshold_columns_exist(conn):
                print("  threshold columns: MISSING")
                if args.skip_sql:
                    print("ERROR: columns missing and --skip-sql set", file=sys.stderr)
                    sys.exit(1)
            else:
                print("  threshold columns: present")

        if not args.skip_sql:
            _apply_sql(engine)
            session.commit()
            print("  threshold columns: applied (idempotent)")

        before = _count_threshold_fields(session, args.user_id)
        print("  BEFORE:", json.dumps(before))

        link = session.execute(
            text(
                "SELECT athlete_id FROM user_athletes WHERE user_id::text = :u LIMIT 1"
            ),
            {"u": args.user_id},
        ).fetchone()
        print(
            "  user_link:",
            json.dumps(
                {
                    "user_id": args.user_id,
                    "athlete_id": int(link[0]) if link else None,
                }
            ),
        )

        if not args.skip_backfill:
            updated = _backfill_user(session, args.user_id, force_all=args.force_all)
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
        print("  weekly-history (same handler as API):", json.dumps(summary, indent=2))
        failures = _verify_a1_contract(summary)
        if failures:
            print("  A1_VERIFY: FAIL", failures, file=sys.stderr)
            sys.exit(2)
        print("  A1_VERIFY: PASS")
        if summary.get("sample_threshold_point"):
            print(
                "  sample systems.threshold.weekly_data[0]:",
                json.dumps(summary["sample_threshold_point"], indent=2),
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()

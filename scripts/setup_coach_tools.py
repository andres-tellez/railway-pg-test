#!/usr/bin/env python3
"""
Create coach_tools table and seed with initial tool definitions.

Usage:
    python scripts/setup_coach_tools.py          # dev database
    python scripts/setup_coach_tools.py --prod    # prod database
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS coach_tools (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR NOT NULL UNIQUE,
    display_name   VARCHAR NOT NULL,
    category       VARCHAR NOT NULL,
    description    TEXT NOT NULL,
    when_to_call   TEXT,
    parameters_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    returns_description TEXT,
    data_source    VARCHAR,
    is_enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    call_count     INTEGER NOT NULL DEFAULT 0,
    last_called_at TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

SEED_TOOLS = [
    {
        "name": "find_runs_by_date",
        "display_name": "Find Runs by Date",
        "category": "run_analysis",
        "description": (
            "Find the user's run activities on a local calendar date (YYYY-MM-DD). "
            "When they ask about 'my run', 'how was my run', 'this run', 'today', or omit a date, "
            "use the device anchor date from the system prompt as local_date unless they clearly name another day. "
            "If multiple runs are returned, ask which one using the candidate list. "
            "If one activity_id is returned, call get_run_summary with it."
        ),
        "when_to_call": (
            "User asks 'how was my run', 'today's run', references a specific date, "
            "or any question about a particular run. This is the entry point — call this first "
            "to resolve a date to an activity_id, then chain to get_run_summary."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "local_date": {
                    "type": "string",
                    "description": "Local calendar date in YYYY-MM-DD format.",
                }
            },
            "required": ["local_date"],
        },
        "returns_description": (
            "If one run: { activity_id, local_date }. "
            "If multiple: { disambiguation_needed: true, candidates: [...] }. "
            "If none: { no_runs: true }."
        ),
        "data_source": "activities (via ActivityDAO)",
        "is_enabled": True,
        "sort_order": 10,
    },
    {
        "name": "get_run_summary",
        "display_name": "Get Run Summary",
        "category": "run_analysis",
        "description": (
            "Load complete analysis for one run: facts (distance, time, pace, HR), "
            "comparison vs recent similar runs, and Z2 training KPIs (HR drift, Z2 adherence, "
            "pace consistency). Only call after you know the activity_id from find_runs_by_date "
            "or the user provides one directly. "
            "Pace and times in tool output are display-ready; quote them accurately."
        ),
        "when_to_call": (
            "After identifying a specific activity_id (via find_runs_by_date or user-provided). "
            "Provides everything needed to discuss a single run."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "activity_id": {
                    "type": "integer",
                    "description": "Strava activity id for this user's run.",
                }
            },
            "required": ["activity_id"],
        },
        "returns_description": (
            "Run facts (distance, pace, HR, time), peer comparison table, "
            "Z2 KPIs (hr_drift_pct, z2_band_pct, easy_pct, pace_spread), "
            "is_easy_run classification, zone bounds used."
        ),
        "data_source": "run_insight + v_easy_runs",
        "is_enabled": True,
        "sort_order": 20,
    },
    {
        "name": "get_training_kpis",
        "display_name": "Get Training KPIs",
        "category": "training_progress",
        "description": (
            "Get the user's training KPI trends over recent weeks: Z2 pace, HR drift, "
            "Z2 adherence, weekly mileage, and long run readiness. "
            "Call when the user asks about training progress, marathon readiness, "
            "'how am I doing', 'am I on track', or 'am I improving'. "
            "Never calculate KPIs yourself — always use this tool's data."
        ),
        "when_to_call": (
            "User asks about overall training progress, trends, weekly improvement, "
            "marathon readiness, or any question about how their training is going "
            "over time (not a single run)."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "weeks": {
                    "type": "integer",
                    "description": "Number of weeks to look back. Default 4.",
                }
            },
        },
        "returns_description": (
            "Weekly summaries with avg Z2 pace, avg HR drift, avg Z2 adherence, "
            "total miles, easy run count, longest run. Trend direction for each KPI "
            "(improving/stable/declining). Long run drift assessment."
        ),
        "data_source": "v_easy_runs (aggregated by week)",
        "is_enabled": False,
        "sort_order": 30,
    },
]


def main():
    env_key = "PROD_DATABASE_URL" if "--prod" in sys.argv else "DATABASE_URL"
    db_url = os.environ.get(env_key)
    if not db_url:
        print(f"ERROR: {env_key} not set")
        sys.exit(1)
    print(f"Using {env_key} -> {db_url.split('@')[1].split('/')[0]}")

    engine = create_engine(db_url)
    s = sessionmaker(bind=engine)()

    print("\nCreating coach_tools table...")
    s.execute(text(_CREATE_TABLE))
    s.commit()
    print("  Done.")

    print(f"\nSeeding {len(SEED_TOOLS)} tools...")
    for tool in SEED_TOOLS:
        s.execute(
            text(
                """
                INSERT INTO coach_tools (
                    name, display_name, category, description,
                    when_to_call, parameters_schema, returns_description,
                    data_source, is_enabled, sort_order
                ) VALUES (
                    :name, :display_name, :category, :description,
                    :when_to_call, :parameters_schema, :returns_description,
                    :data_source, :is_enabled, :sort_order
                )
                ON CONFLICT (name) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    category = EXCLUDED.category,
                    description = EXCLUDED.description,
                    when_to_call = EXCLUDED.when_to_call,
                    parameters_schema = EXCLUDED.parameters_schema,
                    returns_description = EXCLUDED.returns_description,
                    data_source = EXCLUDED.data_source,
                    is_enabled = EXCLUDED.is_enabled,
                    sort_order = EXCLUDED.sort_order,
                    updated_at = now()
            """
            ),
            {
                **tool,
                "parameters_schema": json.dumps(tool["parameters_schema"]),
            },
        )
        status = "ENABLED" if tool["is_enabled"] else "DISABLED"
        print(f"  {status:>8}  {tool['name']:<25} ({tool['category']})")

    s.commit()

    # Validate
    rows = s.execute(
        text(
            "SELECT name, display_name, category, is_enabled, call_count "
            "FROM coach_tools ORDER BY sort_order"
        )
    ).fetchall()

    print(f"\ncoach_tools ({len(rows)} rows):")
    print(
        f"  {'Name':<25} {'Display':<25} {'Category':<20} {'Enabled':>7} {'Calls':>5}"
    )
    for r in rows:
        enabled = "yes" if r[3] else "no"
        print(f"  {r[0]:<25} {r[1]:<25} {r[2]:<20} {enabled:>7} {r[4]:>5}")

    s.close()
    engine.dispose()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Create weekly_training_insights table.

Usage:
    python scripts/setup_weekly_insights.py          # dev + prod
"""

import os
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS weekly_training_insights (
    id                    SERIAL PRIMARY KEY,
    user_id               UUID NOT NULL,
    week_start            DATE NOT NULL,
    week_end              DATE NOT NULL,

    hr_drift_pct          DOUBLE PRECISION,
    z2_pace_min_per_mi    DOUBLE PRECISION,
    efficiency            DOUBLE PRECISION,

    hr_drift_band         VARCHAR(10),
    z2_pace_band          VARCHAR(10),
    efficiency_band       VARCHAR(10),
    overall_band          VARCHAR(10) NOT NULL,

    hr_drift_delta        DOUBLE PRECISION,
    z2_pace_delta         DOUBLE PRECISION,
    efficiency_delta       DOUBLE PRECISION,

    easy_avg_hr           DOUBLE PRECISION,
    easy_avg_hr_band      VARCHAR(10),
    easy_avg_hr_delta    DOUBLE PRECISION,

    easy_run_count        INTEGER NOT NULL DEFAULT 0,
    total_run_count       INTEGER NOT NULL DEFAULT 0,

    summary_text          TEXT,
    action_text           TEXT,

    kpi_snapshot          JSONB,
    generated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(user_id, week_start)
)
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_weekly_insights_user_week
ON weekly_training_insights (user_id, week_start DESC)
"""

WEEKLY_INSIGHT_TOOL = {
    "name": "get_weekly_training_insight",
    "display_name": "Get Weekly Training Insight",
    "category": "training_progress",
    "description": (
        "Latest weekly insight. Default: orientation (week + overall_band). "
        "include_kpi_detail=true for full KPIs, deltas, and zone charts."
    ),
    "when_to_call": (
        "Weekly progress / on-track questions for the current insight week."
    ),
    "parameters_schema": {
        "type": "object",
        "properties": {
            "include_kpi_detail": {
                "type": "boolean",
                "description": "Return full KPI payload when true.",
            },
        },
    },
    "returns_description": (
        "Orientation or full scoreboard; see setup_coach_tools get_weekly_training_insight."
    ),
    "data_source": "weekly_training_insights",
    "is_enabled": True,
    "sort_order": 35,
}


def setup_db(db_url: str, label: str):
    engine = create_engine(db_url)
    s = sessionmaker(bind=engine)()

    print(f"\n{label}:")

    print("  Creating weekly_training_insights table...")
    s.execute(text(_CREATE_TABLE))
    s.execute(text(_CREATE_INDEX))
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
            **WEEKLY_INSIGHT_TOOL,
            "parameters_schema": json.dumps(WEEKLY_INSIGHT_TOOL["parameters_schema"]),
        },
    )
    s.commit()
    print("  Done.")

    s.close()
    engine.dispose()


if __name__ == "__main__":
    for env_key, label in [("DATABASE_URL", "DEV"), ("PROD_DATABASE_URL", "PROD")]:
        url = os.environ.get(env_key)
        if url:
            setup_db(url, label)

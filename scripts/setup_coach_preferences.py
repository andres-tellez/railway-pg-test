#!/usr/bin/env python3
"""
Create user_coach_preferences table and add save_coach_preference tool.

Usage:
    python scripts/setup_coach_preferences.py          # dev
    python scripts/setup_coach_preferences.py --prod    # prod
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
CREATE TABLE IF NOT EXISTS user_coach_preferences (
    user_id              UUID PRIMARY KEY,
    coaching_level       VARCHAR NOT NULL DEFAULT 'beginner',
    run_summary_priority JSONB,
    training_summary_priority JSONB,
    verbosity            VARCHAR NOT NULL DEFAULT 'normal',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

SAVE_TOOL = {
    "name": "save_coach_preference",
    "display_name": "Save Coach Preference",
    "category": "preferences",
    "description": (
        "Save or update **this user's** coaching preferences only (per account — "
        "does not affect other users). Call when the user says 'remember this', "
        "'only show me X', 'from now on include HR drift and the KPI color', "
        "'I want more detail', 'keep it simple', 'change my level', or any lasting "
        "preference for run or training summaries. For run recap add-ons, set "
        "`run_summary_priority` to include the matching ALLOWED_METRICS key (e.g. "
        "`hr_drift` for drift % and Insights band color). Merge with existing "
        "priorities when appropriate. Validate fields against allowed metrics."
    ),
    "when_to_call": (
        "User expresses a lasting preference about format, verbosity, metrics to "
        "prioritize in run/training summaries, or 'from now on always show …'. "
        "Also when they want advanced/beginner style changes."
    ),
    "parameters_schema": {
        "type": "object",
        "properties": {
            "coaching_level": {
                "type": "string",
                "enum": ["beginner", "intermediate", "advanced"],
                "description": "Coaching detail level.",
            },
            "run_summary_priority": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Ordered list of metrics to prioritize in run summaries (this user only). "
                    "Allowed: summary, easy_pct, hr_drift (includes % + green/yellow/orange/red "
                    "band from training_kpis when present), z2_adherence, z2_pace, "
                    "efficiency, pace_spread."
                ),
            },
            "training_summary_priority": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Ordered list of metrics to prioritize in training progress summaries. "
                    "Same allowed values as run_summary_priority."
                ),
            },
            "verbosity": {
                "type": "string",
                "enum": ["minimal", "normal", "detailed"],
                "description": "Response length preference.",
            },
        },
    },
    "returns_description": "Confirmation of saved preferences with the current state.",
    "data_source": "user_coach_preferences",
    "is_enabled": True,
    "sort_order": 40,
}


def setup_db(db_url: str, label: str):
    engine = create_engine(db_url)
    s = sessionmaker(bind=engine)()

    print(f"\n{label}:")

    print("  Creating user_coach_preferences table...")
    s.execute(text(_CREATE_TABLE))
    s.commit()
    print("  Done.")

    print("  Adding save_coach_preference tool...")
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
            **SAVE_TOOL,
            "parameters_schema": json.dumps(SAVE_TOOL["parameters_schema"]),
        },
    )
    s.commit()
    print("  Done.")

    rows = s.execute(
        text("SELECT name, is_enabled FROM coach_tools ORDER BY sort_order")
    ).fetchall()
    print(f"\n  coach_tools ({len(rows)}):")
    for r in rows:
        print(f"    {'ON' if r[1] else 'OFF':>3}  {r[0]}")

    s.close()
    engine.dispose()


if __name__ == "__main__":
    for env_key, label in [("DATABASE_URL", "DEV"), ("PROD_DATABASE_URL", "PROD")]:
        url = os.environ.get(env_key)
        if url:
            setup_db(url, label)

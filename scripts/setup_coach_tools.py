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
        "name": "aggregate_runs_in_range",
        "display_name": "Aggregate Runs in Date Range",
        "category": "run_analysis",
        "description": (
            "Return **full** run count and **total distance** for all Run activities in an inclusive "
            "date range (YYYY-MM-DD). Each row is included by its **activity local calendar day** "
            "(Strava timezone — same as find_runs_by_date), not raw UTC date. "
            "Also returns **weekly_summaries** (ISO week buckets) from the same filtered activities set, "
            "so weekly and overall totals stay aligned. "
            "Use for **total miles in the last 30 days**, **how many runs this month**, "
            "or **volume between two dates**. "
            "Optional filters match `search_runs` (distance bounds, name text). "
            "**Do not** use `search_runs` for totals — it returns a capped sample, not complete aggregates. "
            "In answers, quote **run_count** and **total_mi_display** exactly from the tool result."
        ),
        "when_to_call": (
            "User asks for total runs, total miles/volume, or sum of distance over a calendar window "
            "(e.g. last N days, this month, year to date), OR asks for per-week mileage totals over a date range. "
            "Compute dates from context or the device anchor date."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "start_date_from": {
                    "type": "string",
                    "description": (
                        "Inclusive start date (YYYY-MM-DD), activity-local calendar (not UTC-only)."
                    ),
                },
                "start_date_to": {
                    "type": "string",
                    "description": (
                        "Inclusive end date (YYYY-MM-DD), activity-local calendar (not UTC-only)."
                    ),
                },
                "min_distance_m": {
                    "type": "number",
                    "description": "Optional minimum distance in meters (same as search_runs).",
                },
                "max_distance_m": {
                    "type": "number",
                    "description": "Optional maximum distance in meters (same as search_runs).",
                },
                "name_query": {
                    "type": "string",
                    "description": "Optional case-insensitive substring match on run title.",
                },
            },
            "required": ["start_date_from", "start_date_to"],
        },
        "returns_description": (
            "run_count, total_distance_meters, total_mi_display, weekly_summaries, filters, "
            "scope (all Strava runs in range)."
        ),
        "data_source": "activities (aggregated)",
        "is_enabled": True,
        "sort_order": 12,
    },
    {
        "name": "get_run_summary",
        "display_name": "Get Run Summary",
        "category": "run_analysis",
        "description": (
            "Load run analysis for one activity_id. **Core (always returned):** `facts` — "
            "distance (mi), time, Avg. pace, Avg./max HR (bpm), title, local date/time (display-ready). "
            "**Optional sections** (each defaults to true if omitted; set false to reduce payload): "
            "`include_peer_comparison` → `comparison` (this run vs up to 5 prior runs, deltas); "
            "`include_execution_kpis` → `training_kpis`, `zone_bounds`, `is_easy_run` from v_easy_runs "
            "(kpis: `hr_drift_pct`, `hr_drift_band`, `hr_drift_summary_display` as `![HR drift: X%](kpi-band://band)` for chat dot + label; "
            "`easy_pct_display`, `z2_band_pct_display`); "
            "Always: `hr_drift_band_zones` — min/max % drift per color (app-wide, same as Weekly Insights; use when user asks band definitions). "
            "`include_hr_profile` → `user_hr_profile` (Z1–Z5 bpm, hrmax_used_bpm, resting_hr_used_bpm, method). "
            "For **lap / mile-by-mile** pace and avg HR rows, use **`get_run_splits`** (same activity_id), not this tool alone. "
            "Only call after activity_id is known (find_runs_by_date or user-provided)."
        ),
        "when_to_call": (
            "After identifying activity_id. Use defaults (all sections) for first 'how was my run' style "
            "questions; turn off sections you do not need on follow-ups to save tokens."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "activity_id": {
                    "type": "integer",
                    "description": "Strava activity id for this user's run.",
                },
                "include_peer_comparison": {
                    "type": "boolean",
                    "description": (
                        "If true (default), include comparison vs recent peer runs and deltas. "
                        "If false, omit `comparison` (facts only besides other flags)."
                    ),
                },
                "include_execution_kpis": {
                    "type": "boolean",
                    "description": (
                        "If true (default), include training_kpis, zone_bounds, is_easy_run when "
                        "the run exists in v_easy_runs. If false, skip KPI query."
                    ),
                },
                "include_hr_profile": {
                    "type": "boolean",
                    "description": (
                        "If true (default), attach user_hr_profile from user_hr_zones when configured. "
                        "If false, omit (e.g. user only asked about pace, not zones)."
                    ),
                },
            },
            "required": ["activity_id"],
        },
        "returns_description": (
            "Always: schema_version, activity_id, facts, hr_drift_band_zones (HR drift % bands for all users). "
            "If include_peer_comparison: comparison (this_run, peer_runs, deltas). "
            "If include_execution_kpis and KPI row exists: training_kpis.kpis "
            "(hr_drift_summary_display, easy_pct_display, z2_band_pct_display, etc.), "
            "zone_bounds, is_easy_run. "
            "If include_hr_profile and zones configured: user_hr_profile."
        ),
        "data_source": "run_insight + v_easy_runs",
        "is_enabled": True,
        "sort_order": 20,
    },
    {
        "name": "get_run_splits",
        "display_name": "Get Run Splits",
        "category": "run_analysis",
        "description": (
            "Load **per-lap / per-split** rows for one **activity_id** from the `splits` table (Strava lap ingestion). "
            "Each row includes **segment_label**, **distance_display**, **moving_time_display**, **avg_pace_display**, "
            "**avg_heart_rate_display** (display strings — quote exactly). "
            "Use for **mile over mile**, **each mile**, **lap by lap**, **split-by-split** HR or pace, or any ask for "
            "finer progression than **get_run_summary.training_kpis** (early/late/peak HR). "
            "**scope** in the payload explains lap boundaries (often ~1 mi, not guaranteed). "
            "Session-level drift % and Z2 KPIs stay on **get_run_summary**; do not recompute splits yourself."
        ),
        "when_to_call": (
            "User wants split-level or per-mile / per-lap breakdown of pace or heart rate for a run you can identify "
            "with **activity_id** (same run as a prior **get_run_summary** when continuing that thread)."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "activity_id": {
                    "type": "integer",
                    "description": "Strava activity id for this user's run.",
                },
            },
            "required": ["activity_id"],
        },
        "returns_description": (
            "activity_id, title, splits_count, splits[] (lap_index, segment_label, display fields), scope; "
            "or empty splits with message when no lap rows stored."
        ),
        "data_source": "splits (+ activities ownership check)",
        "is_enabled": True,
        "sort_order": 21,
    },
    {
        "name": "search_runs",
        "display_name": "Search Runs",
        "category": "run_analysis",
        "description": (
            "Search the user's run history using optional filters (distance, name text, date range), "
            "ordered newest-first, **capped to a small limit** (sample only). "
            "Use for discovery — e.g. 'when was my last marathon?', 'last race'. "
            "**Never** use this tool for **total miles** or **total run count** over a period; "
            "use **aggregate_runs_in_range** instead. "
            "For marathon distance use min_distance_m ~42195. "
            "For race questions, after matches return, chain get_run_summary(top activity_id) in the same "
            "turn — search_runs alone has no finish time or avg pace."
        ),
        "when_to_call": (
            "Historical run discovery without a specific local_date. If a single date is known, "
            "prefer find_runs_by_date. For last marathon / last race / when was [event] / race-shaped "
            "filters, always call get_run_summary on the top match's activity_id in the same assistant "
            "turn (include_peer_comparison true by default). For pure multi-run listing with no stats "
            "ask, search_runs alone is OK."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "min_distance_m": {
                    "type": "number",
                    "description": "Optional minimum distance in meters.",
                },
                "max_distance_m": {
                    "type": "number",
                    "description": "Optional maximum distance in meters.",
                },
                "name_query": {
                    "type": "string",
                    "description": "Optional case-insensitive text match on run title.",
                },
                "start_date_from": {
                    "type": "string",
                    "description": (
                        "Optional inclusive start (YYYY-MM-DD), activity-local calendar per run."
                    ),
                },
                "start_date_to": {
                    "type": "string",
                    "description": (
                        "Optional inclusive end (YYYY-MM-DD), activity-local calendar per run."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max matches to return (default 5, max 20).",
                },
            },
        },
        "returns_description": (
            "Matches ordered by most recent first with activity_id, title, distance_display, "
            "and start_local_time_display. Includes count and filters applied."
        ),
        "data_source": "activities (filtered run history)",
        "is_enabled": True,
        "sort_order": 15,
    },
    {
        "name": "get_weekly_training_insight",
        "display_name": "Get Weekly Training Insight",
        "category": "training_progress",
        "description": (
            "Get the user's latest precomputed weekly training scoreboard: overall band, "
            "HR drift / Avg. Z2 pace / efficiency bands, deltas, and coaching summary/action text. "
            "Use this first for **this week's** holistic status. "
            "**Not** for a table of weekly mileage totals across many weeks — use "
            "**aggregate_runs_in_range** weekly_summaries for that."
        ),
        "when_to_call": (
            "User asks weekly progress questions like 'am I on track', 'how am I doing this week', "
            "'weekly status', or wants a concise scoreboard for the **current** insight week. "
            "Do **not** use this alone when they want **per-week mileage** over roughly the last month."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {},
        },
        "returns_description": (
            "Always includes hr_drift_band_zones (HR drift % min/max per color, app-wide). "
            "If available: has_insight=true with week range, overall band, KPI cards, "
            "summary_text, action_text. If not available: has_insight=false with message."
        ),
        "data_source": "weekly_training_insights",
        "is_enabled": True,
        "sort_order": 35,
    },
    {
        "name": "get_training_kpis",
        "display_name": "Get Training KPIs",
        "category": "training_progress",
        "description": (
            "Get training KPI trends over recent **ISO weeks** (Mon–Sun): Avg. Z2 pace, HR drift, "
            "Z2 adherence (use *_display fields), **weekly_summaries** with miles per week, long-run readiness. "
            "Scope is **v_easy_runs** (easy-classified runs only) — see **weekly_summaries_scope** in the payload. "
            "Use for KPI trend interpretation (HR drift/Z2 progress), not inclusive all-runs mileage totals. "
            "For **all Strava runs** weekly mileage in a calendar window, use **aggregate_runs_in_range** instead. "
            "Never calculate KPIs yourself — always use this tool's data."
        ),
        "when_to_call": (
            "User asks about training progress, trends, weekly improvement, marathon readiness, "
            "or KPI quality trends over multiple weeks (not a single run). "
            "For inclusive weekly mileage totals over a date range, use aggregate_runs_in_range instead."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "weeks": {
                    "type": "integer",
                    "description": (
                        "Optional rolling lookback in weeks when no explicit date range is given."
                    ),
                },
                "start_date_from": {
                    "type": "string",
                    "description": (
                        "Optional inclusive start date (YYYY-MM-DD), activity-local calendar."
                    ),
                },
                "start_date_to": {
                    "type": "string",
                    "description": (
                        "Optional inclusive end date (YYYY-MM-DD), activity-local calendar."
                    ),
                },
            },
        },
        "returns_description": (
            "Weekly summaries with avg Z2 pace, avg HR drift, avg Z2 adherence, "
            "total miles, easy run count, longest run. Trend direction for each KPI "
            "(improving/stable/declining). Long run drift assessment. "
            "When explicit dates are provided, includes window and sum_weekly_total_mi_display. "
            "Always: hr_drift_band_zones (HR drift % bands, app-wide)."
        ),
        "data_source": "v_easy_runs (aggregated by week)",
        "is_enabled": True,
        "sort_order": 30,
    },
    {
        "name": "get_marathon_projection",
        "display_name": "Get Marathon Projection",
        "category": "training_progress",
        "description": (
            "Deterministic marathon finish-time projection from recent run signals. "
            "Returns scenario-based race pace and finish-time estimates (conservative/on_track/stretch) "
            "with explicit assumptions and data quality context. Use this for asks like "
            "'predict my next marathon time' or 'marathon projection'."
        ),
        "when_to_call": (
            "User asks to predict/project marathon finish time or marathon race pace. "
            "Optionally include target_race_date and goal_time_hhmmss for timeline and goal comparison."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "target_race_date": {
                    "type": "string",
                    "description": "Optional race date (YYYY-MM-DD).",
                },
                "goal_time_hhmmss": {
                    "type": "string",
                    "description": "Optional goal marathon time in HH:MM:SS.",
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Optional lookback window in days (default 84).",
                },
            },
        },
        "returns_description": (
            "Scenario list with race_pace_display and projected_finish_time_display, plus data_quality, "
            "assumptions, optional race_target timing, and optional goal comparison."
        ),
        "data_source": "activities + v_easy_runs-derived anchor",
        "is_enabled": True,
        "sort_order": 32,
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

#!/usr/bin/env python3
"""
Create coach_tools table and seed with initial tool definitions.

Upserts every row in SEED_TOOLS (ON CONFLICT (name) DO UPDATE), so re-run this
after changing tool copy in this file to refresh production/staging descriptions.

Usage:
    python scripts/setup_coach_tools.py                    # dev (DATABASE_URL)
    python scripts/setup_coach_tools.py --prod             # prod (PROD_DATABASE_URL)
    python scripts/setup_coach_tools.py --only=get_run_splits
    python scripts/setup_coach_tools.py --prod --only=get_run_splits,search_runs
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


def _tools_to_seed_from_argv(argv: list[str]) -> list[dict]:
    """If --only=a,b is present, seed only those tool names; else full SEED_TOOLS."""
    only_arg = None
    for a in argv:
        if a.startswith("--only="):
            only_arg = a.split("=", 1)[1].strip()
            break
    if not only_arg:
        return list(SEED_TOOLS)
    want = {x.strip() for x in only_arg.split(",") if x.strip()}
    picked = [t for t in SEED_TOOLS if t["name"] in want]
    unknown = want - {t["name"] for t in picked}
    if unknown:
        print(f"WARNING: --only mentions unknown tool name(s): {sorted(unknown)}")
    if not picked:
        print("ERROR: --only matched no tools; check names against SEED_TOOLS.")
        sys.exit(1)
    return picked


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
            "Long activities: payload may cap rows (first and last laps by lap order); check **splits_truncated** "
            "and **splits_total_count**. "
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
            "activity_id, title, splits[], splits_count (rows in splits), splits_total_count (laps in run), "
            "splits_truncated, scope; when truncated, splits_cap.policy head_tail_by_lap_index. "
            "Or empty splits with message when no lap rows stored."
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
        # DEPRECATED V1.6 (PHASE_3_IMPLEMENTATION_CHECKLIST 0.C):
        # Registration is preserved so existing LLM flows keep working, but
        # the description now steers the model toward the orientation path
        # only. The V1.7 replacement will be `get_weekly_plan`
        # (AGENTIC_COACH.md Topic 9). Do not add new callers or extend this
        # description with new capabilities.
        "name": "get_weekly_training_insight",
        "display_name": "Get Weekly Training Insight",
        "category": "training_progress",
        "description": (
            "[DEPRECATED — will be replaced by get_weekly_plan in a future release; "
            "prefer get_weekly_plan when available.] "
            "Latest precomputed weekly insight. **Default (coach):** orientation only — "
            "`week_start`, `week_end`, `overall_band` (`insight_detail_level` = `orientation`); "
            "no per-KPI numbers, deltas, zone charts, or run counts. "
            "Set **include_kpi_detail** true for the full scoreboard (HR drift / Z2 pace / efficiency, "
            "deltas, `hr_drift_band_zones`, `systems`, counts, summary/action when present). "
            "Use first for **this week's** holistic vibe. "
            "**Not** for a table of weekly mileage totals across many weeks — use "
            "**aggregate_runs_in_range** `weekly_summaries` for that."
        ),
        "when_to_call": (
            "User asks weekly progress questions like 'am I on track', 'how am I doing this week', "
            "'weekly status', or wants a concise read for the **current** insight week. "
            "Do **not** use this alone when they want **per-week mileage** over roughly the last month."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "include_kpi_detail": {
                    "type": "boolean",
                    "description": (
                        "When true, return full KPI payload (drift/Z2/efficiency, deltas, zone charts, "
                        "systems). Omit or false for default orientation-only (saves context; answer "
                        "from overall_band + week unless user wants numbers)."
                    ),
                },
            },
        },
        "returns_description": (
            "Default: insight_detail_level=orientation, week_start/week_end/overall_band, orientation_note. "
            "Full: kpis, systems, hr_drift_band_zones, aerobic_efficiency_band_zones, counts, etc. "
            "If no row: has_insight=false and message (full mode also includes zone charts for definitions)."
        ),
        "data_source": "weekly_training_insights",
        "is_enabled": True,
        "sort_order": 35,
    },
    {
        # V1.6 Phase B 3B.2–3B.4 (PHASE_3_IMPLEMENTATION_CHECKLIST):
        # canonical weekly-plan read. Replaces `get_weekly_training_insight`
        # for any question that requires planned-vs-actual reasoning.
        "name": "get_weekly_plan",
        "display_name": "Get Weekly Plan",
        "category": "plan_analysis",
        "description": (
            "V1.6 canonical weekly plan + execution read for one Monday-to-Sunday window. "
            "Use for 'what's on my plan this week', 'how did this week compare to plan', "
            "'what do I have next week', or any planned-vs-actual question about a **specific week**. "
            "Returns per-day `planned` / `actual` namespaced blocks (§6 namespace isolation), "
            "per-day `plan_status` (planned_only / in_progress / executed / missed / unplanned), "
            "`violated_rest_day` and `deviation_direction` controllers, weekly `adherence_runs_pct` + band, "
            "and `phase_kpi_priority` ordered emphasis list. "
            "Future weeks return **only planned** — no actuals, no adherence (§19.5 contract enforced structurally). "
            "Malformed or omitted `week_start_iso` resolves to the athlete's current week."
        ),
        "when_to_call": (
            "User asks about this / next / last week's plan or execution against plan; "
            "missed runs or rest-day violations in a week; what today's / tomorrow's planned run is; "
            "how the week shaped up compared to plan. Prefer this over get_weekly_training_insight "
            "whenever the question references the plan or planned workouts."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "week_start_iso": {
                    "type": "string",
                    "description": (
                        "Optional YYYY-MM-DD within the target week. Normalized to that week's Monday. "
                        "Omit for the athlete's current week. Past and future weeks are allowed."
                    ),
                },
                "tz": {
                    "type": "string",
                    "description": (
                        "Optional IANA timezone for 'current week' resolution (e.g. America/Denver). "
                        "Defaults to UTC."
                    ),
                },
            },
        },
        "returns_description": (
            "plan_id, plan_name, race_date, week_start, week_end, week_temporality (past/current/future), "
            "days[] with per-day planned + actual + plan_status + violated_rest_day, adherence block "
            "(null for future weeks), phase_kpi_priority ordered list."
        ),
        "data_source": "plans + plan_workouts + activities (matched)",
        "is_enabled": True,
        "sort_order": 36,
    },
    {
        # V1.6 Phase B 3B.5 — end-to-end plan overview, planned-only.
        "name": "get_plan_overview",
        "display_name": "Get Plan Overview",
        "category": "plan_analysis",
        "description": (
            "V1.6 end-to-end **planned-only** overview of the athlete's active (or most recent) plan. "
            "Use for plan-arc questions: 'what does my whole plan look like', 'what phase am I in vs. "
            "what comes next', 'how does weekly mileage progress over the plan', 'what's my long-run "
            "build'. Returns `phase_blocks` (Base/Build/Peak/Taper with week span, workout count, "
            "planned miles, and canonical `phase_kpi_priority` ordered emphasis list), `volume_curve` "
            "(one row per plan week with planned_runs + planned_miles_total + week_temporality), and "
            "`long_run_progression` (one row per week with the longest planned run date, miles, and type). "
            "**No actuals** — the overview never reads activities. Use `get_weekly_plan` if you need "
            "plan-vs-actual for a specific week. §19.5 future-week contract structurally applies to "
            "every week in the overview."
        ),
        "when_to_call": (
            "User asks about the shape of the whole plan, phase structure, weekly volume progression, "
            "or long-run build-up. Prefer this over calling `get_weekly_plan` N times when the question "
            "is about the plan arc rather than a specific week."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "tz": {
                    "type": "string",
                    "description": (
                        "Optional IANA timezone for per-week `week_temporality` stamping. "
                        "Defaults to UTC. Does not affect plan-side fields."
                    ),
                },
            },
        },
        "returns_description": (
            "plan_id, plan_name, race_date, plan_start, plan_end, total_weeks, total_planned_runs, "
            "total_planned_miles, phase_blocks[], volume_curve[] (planned-only), long_run_progression[]."
        ),
        "data_source": "plans + plan_workouts (planned-only; no activities read)",
        "is_enabled": True,
        "sort_order": 37,
    },
    {
        "name": "get_phase_analysis",
        "display_name": "Get Phase Analysis",
        "category": "plan_analysis",
        "description": (
            "V1.6 per-run-type KPI trend for a given training phase (Base / Build / Peak / Taper) "
            "through today. Surfaces `phase_kpi_priority` (the §8 ordered emphasis list the coach "
            "should lead with for this phase), `phase_weeks` (total/completed/in_progress/future with "
            "phase_temporality), `phase_window` (start/end/evaluated_through), and `by_run_type` — for "
            "each canonical run-type (easy/recovery/steady/tempo/long) that appears in the phase: planned "
            "vs matched run counts, planned/actual miles totals, zone_compliance_pct avg + weekly trend "
            "series, completion_miles_pct avg, deviation_direction distribution (too_hard/too_easy/"
            "on_target/null), and run_score distribution (green/yellow/red/null). All actual-side "
            "values come from the same canonical producer as `get_run_summary` and `get_weekly_plan`. "
            "Future phase-weeks contribute no execution data (§19.5 extension)."
        ),
        "when_to_call": (
            "User asks about how a phase is going ('how is my Base phase going'), phase-level KPI trends "
            "('is my Tempo compliance improving through Build'), or wants a summary of phase-to-date "
            "execution quality by run type. Prefer this over summing multiple `get_run_summary` calls. "
            "`phase_id` is required (Base / Build / Peak / Taper, case-insensitive)."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "phase_id": {
                    "type": "string",
                    "description": (
                        "Required. One of Base / Build / Peak / Taper (case-insensitive)."
                    ),
                },
                "tz": {
                    "type": "string",
                    "description": (
                        "Optional IANA timezone for resolving 'today' (phase-to-date cutoff). "
                        "Defaults to UTC."
                    ),
                },
            },
            "required": ["phase_id"],
        },
        "returns_description": (
            "plan_id, plan_name, phase, phase_kpi_priority, phase_weeks (total/completed/"
            "in_progress/future/completion_pct/phase_temporality), phase_window (start/end/"
            "evaluated_through), by_run_type{run_type_key -> {run_count_planned/matched, "
            "miles_planned_total/actual_total, zone_compliance_pct{avg,trend[]}, "
            "completion_miles_pct_avg, deviation_direction_distribution, run_score_distribution, "
            "run_type}}."
        ),
        "data_source": "plans + plan_workouts + matched activities via build_run_execution_block",
        "is_enabled": True,
        "sort_order": 38,
    },
    {
        # V1.6 Phase B 3B.10 — light user-level context payload.
        "name": "get_user_context",
        "display_name": "Get User Context",
        "category": "user_context",
        "description": (
            "V1.6 Phase B 3B.10 user-level context the coach reads at the start of a conversation. "
            "Single call returns: race_goal (race name/date/distance, goal_time, primary_goal, "
            "weeks_until_race), plan (plan_id, plan_name, plan_start/end, total_weeks, "
            "current_week_number, current_phase + canonical §8 phase_kpi_priority ordered emphasis "
            "list), baseline_status (insufficient/thin/strong via the canonical §12 producer), "
            "coaching (coaching_level, verbosity, stored run/training summary priorities from "
            "user_coach_preferences, has_saved_preferences flag), preferences (training_days, "
            "derived long_run_day, unit_system, timezone), and session_summary (null placeholder for "
            "V1.7). All deterministic values come from existing canonical producers — this tool "
            "never re-derives a signal. PII-light: only the first name of user_identity.name is "
            "emitted. Payload is < 2 KB."
        ),
        "when_to_call": (
            "Call at the START of a new conversation (turn_type == 'opening') or when the user asks "
            "a who-am-I/what-am-I-training-for style question. Prefer this over issuing multiple "
            "tool calls for race info + plan phase + baseline + coaching preferences. Cacheable per "
            "user for a single request. Do not call again mid-conversation unless the user has "
            "saved a new preference, generated a new plan, or a new run has landed (each of which "
            "invalidates the context)."
        ),
        "parameters_schema": {
            "type": "object",
            "properties": {
                "tz": {
                    "type": "string",
                    "description": (
                        "Optional IANA timezone name. Drives resolution of 'today' for "
                        "weeks_until_race and current_week_number. Defaults to UTC."
                    ),
                },
            },
        },
        "returns_description": (
            "schema_version, user_id, display_name (first name only), baseline_status, race_goal "
            "(race_name/race_distance/race_date/goal_time/primary_goal/weeks_until_race), plan "
            "(plan_id/plan_name/plan_start/plan_end/total_weeks/current_week_number/is_active/"
            "current_phase/phase_kpi_priority), coaching (coaching_level/verbosity/"
            "run_summary_priority/training_summary_priority/has_saved_preferences), preferences "
            "(training_days/long_run_day/unit_system/timezone), session_summary (null in V1.6), "
            "generated_at, today."
        ),
        "data_source": (
            "user_identity + user_profile + user_coach_preferences + user_athletes + plans + "
            "plan_workouts + compute_baseline_status_for_athlete + phase_kpi_priority_for_phase"
        ),
        "is_enabled": True,
        "sort_order": 39,
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

    tools = _tools_to_seed_from_argv(sys.argv)
    print(f"\nSeeding {len(tools)} tool(s)...")
    for tool in tools:
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

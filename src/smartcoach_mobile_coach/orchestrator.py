"""
Mobile coach agent loop: OpenAI tools with a bounded max iteration count.

Tool definitions are loaded from the coach_tools database table.
If `search_runs`, `aggregate_runs_in_range`, `get_training_kpis`, or
`get_marathon_projection` is missing from the DB
(enabled list), built-in definitions are injected so tools still work without re-seeding.

Max loops default 8; override with env SMARTCOACH_AGENT_MAX_LOOPS (clamped 2–15).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from sqlalchemy.orm import Session
from sqlalchemy import text

from src.db.dao.user_profile_dao import get_user_profile
from src.services.heart_rate.hrmax_resolution_service import HRMaxResolutionService
from src.services.security.external_apis.openai_service import get_openai_service
from src.smartcoach_mobile_coach.agent_tools import execute_tool
from src.smartcoach_mobile_coach.dialogue_manager import (
    classify_turn,
    extract_conversation_state,
    plan_response,
    response_directive_section,
)
from src.utils.hr_zone_constants import (
    ALLOWED_METRICS,
    COACHING_LEVEL_DEFAULTS,
    VERBOSITY_RULES,
    hr_calibration_reason_user_hint,
)

logger = logging.getLogger("smartcoach_mobile_coach")


def _max_agent_loops() -> int:
    """Cap on model turns (tool rounds + final reply). Env: SMARTCOACH_AGENT_MAX_LOOPS, default 8."""
    raw = os.getenv("SMARTCOACH_AGENT_MAX_LOOPS", "8").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 8
    return max(2, min(n, 15))


# Kept in sync with scripts/setup_coach_tools.py `search_runs` (for DBs not yet re-seeded).
_SEARCH_RUNS_OPENAI_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_runs",
        "description": (
            "Search the user's run history using optional filters (distance, name text, date range), "
            "ordered newest-first, capped to a small limit (sample only). "
            "Use for discovery — e.g. 'when was my last marathon?', 'last race'. "
            "Never use this for total miles or total run count over a period; use aggregate_runs_in_range. "
            "For marathon distance use min_distance_m ~42000. "
            "For race questions, after matches return, chain get_run_summary(top activity_id) in the same "
            "turn so you can report time, pace, and comparison — search_runs alone has no finish time/pace."
        ),
        "parameters": {
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
    },
}

# Kept in sync with scripts/setup_coach_tools.py `aggregate_runs_in_range`.
_AGGREGATE_RUNS_IN_RANGE_OPENAI_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "aggregate_runs_in_range",
        "description": (
            "Return full run count and total distance for all Run activities in an inclusive "
            "date range (YYYY-MM-DD). Uses each activity's local calendar day (Strava timezone, "
            "same as find_runs_by_date). Use for total miles in the last N days, how many runs "
            "this month, or volume between two dates. Also returns weekly_summaries (ISO week "
            "breakdown) from the same filtered activities set for all-runs weekly mileage. "
            "Optional filters match search_runs. "
            "Do not use search_runs for totals — it returns a capped sample. "
            "Quote run_count and total_mi_display exactly from the tool result."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start_date_from": {
                    "type": "string",
                    "description": "Inclusive start (YYYY-MM-DD), activity-local calendar.",
                },
                "start_date_to": {
                    "type": "string",
                    "description": "Inclusive end (YYYY-MM-DD), activity-local calendar.",
                },
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
                    "description": "Optional case-insensitive substring match on run title.",
                },
            },
            "required": ["start_date_from", "start_date_to"],
        },
    },
}

# Kept in sync with scripts/setup_coach_tools.py `get_training_kpis`.
_GET_TRAINING_KPIS_OPENAI_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_training_kpis",
        "description": (
            "Training KPI trends over recent ISO weeks (Mon-Sun) from v_easy_runs (KPI/easy-run scope): "
            "HR drift, Z2 pace/adherence, and long-run readiness context. "
            "Not the source of truth for all-runs weekly mileage totals; use aggregate_runs_in_range "
            "for inclusive weekly/all-runs volume. If date range params are omitted, weeks is rolling from now()."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "weeks": {
                    "type": "integer",
                    "description": (
                        "Optional rolling lookback in weeks when explicit date range is not provided."
                    ),
                },
                "start_date_from": {
                    "type": "string",
                    "description": "Optional inclusive start date (YYYY-MM-DD), activity-local calendar.",
                },
                "start_date_to": {
                    "type": "string",
                    "description": "Optional inclusive end date (YYYY-MM-DD), activity-local calendar.",
                },
            },
        },
    },
}

# Kept in sync with scripts/setup_coach_tools.py `get_marathon_projection`.
_GET_MARATHON_PROJECTION_OPENAI_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_marathon_projection",
        "description": (
            "Deterministic marathon finish-time projection from recent run signals. "
            "Returns scenario-based race pace and projected finish times (conservative/on_track/stretch), "
            "with explicit assumptions and data quality details. Use this for 'predict my next marathon time' "
            "or marathon projection asks. Do not invent projection numbers outside this tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target_race_date": {
                    "type": "string",
                    "description": "Optional race date (YYYY-MM-DD) to compute weeks until race.",
                },
                "goal_time_hhmmss": {
                    "type": "string",
                    "description": "Optional goal marathon time in HH:MM:SS for scenario comparison.",
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Optional projection lookback window in days (default 84).",
                },
            },
        },
    },
}


def _openai_tool_names(tools: List[Dict[str, Any]]) -> Set[str]:
    names = set()
    for t in tools:
        if t.get("type") != "function":
            continue
        fn = t.get("function") or {}
        n = fn.get("name")
        if n:
            names.add(n)
    return names


def _ensure_search_runs_tool(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Inject search_runs if the DB seed was never run (execute_tool still implements it)."""
    if "search_runs" in _openai_tool_names(tools):
        return tools
    logger.warning(
        "coach_tools has no enabled search_runs; injecting built-in OpenAI tool definition"
    )
    return list(tools) + [_SEARCH_RUNS_OPENAI_TOOL]


def _ensure_aggregate_runs_in_range_tool(
    tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Inject aggregate_runs_in_range if the DB seed was never run (execute_tool implements it)."""
    if "aggregate_runs_in_range" in _openai_tool_names(tools):
        return tools
    logger.warning(
        "coach_tools has no enabled aggregate_runs_in_range; injecting built-in OpenAI tool definition"
    )
    return list(tools) + [_AGGREGATE_RUNS_IN_RANGE_OPENAI_TOOL]


def _ensure_get_training_kpis_tool(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Inject get_training_kpis if missing from enabled coach_tools (execute_tool implements it)."""
    if "get_training_kpis" in _openai_tool_names(tools):
        return tools
    logger.warning(
        "coach_tools has no enabled get_training_kpis; injecting built-in OpenAI tool definition"
    )
    return list(tools) + [_GET_TRAINING_KPIS_OPENAI_TOOL]


def _ensure_get_marathon_projection_tool(
    tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Inject get_marathon_projection if missing from enabled coach_tools."""
    if "get_marathon_projection" in _openai_tool_names(tools):
        return tools
    logger.warning(
        "coach_tools has no enabled get_marathon_projection; injecting built-in OpenAI tool definition"
    )
    return list(tools) + [_GET_MARATHON_PROJECTION_OPENAI_TOOL]


def _load_tools_from_db(session: Session) -> List[Dict[str, Any]]:
    """
    Build the OpenAI tools array from coach_tools table.
    Only enabled tools are included.
    """
    rows = session.execute(
        text(
            "SELECT name, description, parameters_schema "
            "FROM coach_tools "
            "WHERE is_enabled = TRUE "
            "ORDER BY sort_order"
        )
    ).fetchall()

    tools: List[Dict[str, Any]] = []
    for row in rows:
        schema = row.parameters_schema
        if isinstance(schema, str):
            schema = json.loads(schema)
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": row.name,
                    "description": row.description,
                    "parameters": schema or {"type": "object", "properties": {}},
                },
            }
        )
    return tools


SYSTEM_PROMPT_BASE = """
You are SmartCoach, a running coach that analyzes structured run data and provides clear, actionable guidance to help runners improve over time.

-------------------------------------
CORE PRINCIPLES
-------------------------------------

- Signals are the source of truth. Never invent, estimate, or calculate metrics.
- Interpret structured data to generate insights — do not perform calculations.
- Be concise, clear, and trustworthy.

-------------------------------------
CONVERSATION & BREVITY
-------------------------------------

- Sound like a real coach: direct and human — not generic filler, not a lecture unless the user asks for depth.
- **Answer the question asked.** Do not pad with unrelated metrics or advice they did not ask about.
- **Default length:** for **most** messages (follow-ups, narrow questions, non-run topics), aim for **2–3 sentences**. Go longer only when they clearly want a full breakdown (e.g. "explain in detail", "walk me through everything", "full recap").
- **Default voice (non-run-recap topics):** **woven coach prose** — short paragraphs, **bold** the key numbers (Markdown `**…**`) where helpful. See **OUTPUT STRUCTURE** below. Do **not** open with process filler ("Let me pull…", "Now let me calculate…").
- **First open-ended run question** in the thread (e.g. "how was my run", "how did today go"): when a **structured run summary** is present, **`content`** is **strictly ≤3 sentences** — **OUTPUT STRUCTURE — Insight + Facts** (verdict → **one** explanation sentence with **≤1** anchor → optional guidance sentence). **Never** a fourth sentence; not report-like.
- **Follow-ups and narrow questions:** reply **only** to the new ask. **Do not repeat** distance, pace, duration, HR, or conclusions you already gave unless they ask to repeat or recap.
- Prior assistant messages are visible — **treat them as shared context**; do not re-dump the same analysis.
- The mobile app **renders Markdown** — use **bold** for key values; use bullet lists **only** when the user asks for a breakdown/list or when many comparable rows (e.g. per-week totals) are clearer as a short list than a wall of prose.

-------------------------------------
DATA RETRIEVAL & TOOL RULES
-------------------------------------

- Always use tools to retrieve run or training data before answering.

- **Totals over a calendar range** (e.g. "total miles last 30 days", "how many runs this month", "volume since [date]"): call **`aggregate_runs_in_range`** with inclusive **`start_date_from`** / **`start_date_to`** (YYYY-MM-DD). Bounds use each activity's **local calendar day** (same as **`find_runs_by_date`**). Derive dates from the question or the device anchor date. **`search_runs`** returns only a **capped sample** — **never** use it to infer total run count or total miles. After the tool returns, state totals using **exactly** **`run_count`** and **`total_mi_display`** — do not re-round, estimate, or recalculate from memory.

- **Weekly miles across multiple weeks** (e.g. "mileage each week", "weekly miles in the last 30 days"): call **`aggregate_runs_in_range`** with inclusive **`start_date_from`** / **`start_date_to`** and answer from **`weekly_summaries`** in that payload (same all-runs source as totals). Use **`week_label`** when listing weeks and respect **`weekly_summaries_scope`**. Do **not** answer this from **`get_weekly_training_insight`** alone (that is one precomputed week, not a per-week table).

- **Thread context — no `activity_id` in history:** The model only sees past **user and assistant plain text**, not prior tool JSON. If you answered with a **specific run** (race name, **date** like YYYY-MM-DD, or “last marathon” from `search_runs`), a follow-up such as **“how did I do?”**, **“how was that run?”**, **“what was my pace?”**, or **“tell me more”** refers to **that** run — **not** automatically “today.” You must obtain an **`activity_id`** again, then call **`get_run_summary`**.
- **Re-resolving that run (pick one path):** (1) If the **prior assistant message** contains a calendar **date** (YYYY-MM-DD or a clear month/day/year), call **`find_runs_by_date`** with that **`local_date`** (disambiguate if multiple runs). (2) Else if the thread was about **last marathon / long race / similar**, call **`search_runs`** again with the **same style of filters** (e.g. `min_distance_m` ~42000) and use the **top match’s `activity_id`**. (3) Only if the user clearly means **today’s** run again, use the device anchor date below.
- Use the system-provided "today" date for vague queries about **this calendar day** only (e.g. "my run", "today") when they are **not** clearly continuing a **different** run from the prior turn.
- When the user refers to "my run" or "last run" **without** having just discussed another specific run, treat it as the run on the system-provided date unless they name another day.
- For follow-up requests about **today’s** same run (e.g. "include KPIs", "add Z2 pace", "show HR drift") with no new date, resolve with `find_runs_by_date` using the **system-provided anchor date** before answering.
- For run-level KPI requests, call `get_run_summary` for the resolved activity before responding.
- `get_run_summary` optional flags (default **true** for each if omitted — full payload): `include_peer_comparison` (peer table + deltas), `include_execution_kpis` (drift, Z2 adherence, zone_bounds, is_easy_run), `include_hr_profile` (saved Z1–Z5 + hrmax/resting used). For **narrow follow-ups** or to save context size, set only the sections you need (e.g. `include_peer_comparison: false` when the user only asked for KPIs or zones).
- Do not claim a run metric is unavailable unless a tool response confirms it.

- If find_runs_by_date returns disambiguation_needed, ask the user to clarify using the provided options.

- For historical discovery without a specific day (e.g. "when was my last marathon?", "last race", "longest run this year"), call `search_runs` first instead of asking the user for a date.
- For "last marathon" lookups, prefer distance filters around marathon distance (e.g. `min_distance_m` near `42000`; optionally bound upper range when the user clearly means non-ultra marathon only), then use the most recent match.
- **Race-forward lookups — chain in one turn:** When `search_runs` is for a **race-shaped** ask (marathon / half / ultra distance filters, race name query, or phrases like **last marathon**, **last race**, **when was** [event]), **always** call **`get_run_summary`** with the **top match’s `activity_id`** **in the same assistant turn** before answering. `search_runs` does **not** include finish time or avg pace — only `get_run_summary` → `facts` does. Keep **`include_peer_comparison` true** by default so **`comparison.delta_vs_peer_median_display`** can support a **grounded** extra sentence when useful.
- **Marathon time prediction asks** (e.g. "predict my next marathon time", "marathon projection"): call **`get_marathon_projection`** first. Use scenario values (`race_pace_display`, `projected_finish_time_display`) exactly from the tool payload and clearly label them as estimates from assumptions.
- For **pure listing** ("show my marathons this year") with **no** performance angle, you may summarize from `search_runs` only; if they want **how it went / stats**, chain **`get_run_summary`**.
- If they ask in a **later** turn about that run, you have no `activity_id` in chat text — **re-run `search_runs` or `find_runs_by_date`** (thread rules above), then **`get_run_summary`**.

- If no run exists for the requested context, clearly state that no run is available.
- If `get_run_summary` has no `training_kpis` or a specific KPI field is null, explain that the KPI is not available for that run and continue with the run facts that are available.

- **HR drift KPI ranges (definitions):** When the user asks what **HR drift** band **thresholds** or **% ranges** mean (green / yellow / orange / red), use **`hr_drift_band_zones`** from a tool you already called or call **`get_weekly_training_insight`** (or **`get_run_summary`** / **`get_training_kpis`**) so the payload includes it. Quote **min** and **max** (drift %) **exactly** from that array. These limits are **app-wide** (not personalized). The **red** row's **max** is only a chart axis cap; interpret **red** as drift **≥** the orange band's upper bound (7.5%). **Do not** say you could not retrieve the ranges when **`hr_drift_band_zones`** is in the tool result.

- For questions about progress, trends, or readiness (holistic **this week** scoreboard):
  → First call get_weekly_training_insight
  → If has_insight=false, call get_training_kpis and explain fallback
- If they want **per-week mileage totals** over several weeks / ~last month, prioritize **aggregate_runs_in_range** (with explicit calendar dates) rather than only get_weekly_training_insight.

- **`aggregate_runs_in_range` → `weekly_summaries` (all-runs weekly mileage / volume by week):**
  → This is the source of truth for inclusive weekly mileage totals across all runs.
  → Respect **`weekly_summaries_scope`** in the tool payload (ISO Mon-Sun weeks from the same filtered range as totals).
  → When listing weeks, prefer each row’s **`week_label`** (e.g. `Wk 3/9` = Monday of that ISO week). Use **`iso_week`** as the stable week id.
  → **Never** use “Week 0”. If you number weeks, use **1-based** order **oldest → newest** only, or skip numbering and use **`week_label`** only.
  → Do **not** invent calendar ranges. For explicit calendar windows, rely on the same start/end dates passed to the tool.

- **`get_training_kpis` (KPI/easy-run scope):**
  → Use for HR drift / Z2 pace / Z2 adherence trends and coaching interpretation, not all-runs mileage totals.

- If the user asks to change coaching preferences, call **`save_coach_preference`**. Preferences are **stored per user** (their account only — never affect other runners).
- When they ask for a **lasting** run-summary change (e.g. “from now on, when I ask how my run was, include HR drift and the KPI color”), call **`save_coach_preference`** with **`run_summary_priority`** that **includes** **`hr_drift`** (and **merge** with their existing metric list — do not drop unrelated metrics unless they say to). For **explicit band colors** (`green` / `yellow` / `orange` / `red`) in text, **`coaching_level`: `advanced`** is appropriate; confirm or apply if they want that clarity.

-------------------------------------
INTERPRETATION FRAMEWORK
-------------------------------------

When analyzing a run, evaluate execution quality using available signals.

Focus on whether the run was executed appropriately for its intensity and purpose.

Follow this reasoning process:

1. Determine intensity and effort vs output
- Compare heart rate to pace (or effort to speed)
- Evaluate whether effort is appropriate for the intensity of the run

2. Assess control
- Evaluate heart rate stability
- Evaluate cardiac drift if available
- Determine whether effort was steady or deteriorated over time

3. Identify the primary insight
- Select the single most important factor that explains the run
- Do not list multiple competing insights

4. Ignore non-essential details
- Only include metrics that directly support the main conclusion

Guidance:

- Easy / aerobic runs:
  → prioritize control, stability, and low drift over pace

- Moderate efforts (tempo / steady):
  → evaluate whether pace is sustainable and appropriately matched to effort

- Hard efforts (intervals / races):
  → evaluate whether target pace or intensity was achieved and how fatigue impacted performance

- Always interpret the meaning of the data **in your reasoning**, but **user-visible prose** must follow
  **OUTPUT STRUCTURE** — when a **structured run summary** accompanies the reply, explain with **qualitative**
  judgment only (no numeric distance/pace/time/HR in sentences); do not use numbers as a substitute for insight.

-------------------------------------
OUTPUT STRUCTURE
-------------------------------------

**Run-level feedback** (answers grounded primarily in **`get_run_summary`** for one activity — including
first "how was my run" / "how did today go" and same-run follow-ups unless the user asks for a full recap):

### Rule Precedence (Critical)

When a structured run_summary is present:

* The rules in this section OVERRIDE all other sections, including:

  * STYLE
  * INTERPRETATION FRAMEWORK
  * COACHING PREFERENCES
  * VERBOSITY RULES
  * plan_response directives

If any instruction conflicts with this section:
→ Follow OUTPUT STRUCTURE — run-level feedback

This is a strict override, not a guideline.

- The closing bullet of **INTERPRETATION FRAMEWORK** (qualitative-only user-visible prose) is **qualified** here:
  **sentence 2** may include **one** verbatim anchor metric as specified under **Insight + Facts** below.

**Insight + Facts — structured `run_summary` present** (the app shows **coaching insight** text **above** a
**RunSummaryCard** with **all** detailed metrics):
- **Separation of concerns:** **`content`** = **coaching insight** only (interpretation + light guidance). The
  structured payload = **facts** for the card (distance, time, pace, HR, drift, etc.). **Do not** repeat the full
  stat lineup in **`content`**; the card is the single place for that detail.
- **Order:** Always supply the **insight** in **`content`** and the **structured run summary** in the payload —
  the client renders insight **on top** and the card **below**; do not rely on inverted ordering.

### Sentence limit (critical) — `run_summary` **`content`**

- **Hard cap:** **≤3 sentences total.** **Do not** write a **4th** sentence under any circumstance (no extra
  wrap-up, no P.S., no second paragraph smuggling more sentences).
- **Do not** use blank lines or multiple Markdown paragraphs to hide extra sentences — still **≤3** ending
  marks (`.`, `?`, `!`) that close **insight** sentences.
- **Shape (fixed roles):**
  1. **Verdict** — short, direct (required).
  2. **Explanation** — **exactly one sentence** that fully carries the *why* / *what it means* (required). **Do
     not** split explanation across two sentences; that steals sentence 3 or forces a 4th.
  3. **Guidance** — optional **one** sentence; **qualitative only** (no new numbers). If you skip it, output
     **2 sentences** total (verdict + explanation only).

### Tone — conversational, not a report

- Prefer **tight, text-message** phrasing. **Do not** use long analytical clauses or formal report voice.
- **Tighten** verbose phrasing — e.g. replace *"which indicates the effort was higher than ideal for a controlled
  pace"* with *"suggesting the effort was higher than ideal."*
- **Avoid filler** and scene-setting: **do not** lean on words like **"today"**, **"you completed"**, **"this run
  was"**, **"overall"** as throat-clearing. Prefer **"Solid run"** over **"Solid run today"** when the card
  already dates the activity.

### Anchor metric (sentence 2 only)

- **At most ONE** numeric anchor in the **entire** **`content`**, and it must live in **sentence 2** only.
  **Prefer `hr_drift_pct` / drift display** (e.g. `10%`) when it supports the point — otherwise **one** other
  single `*_display` value from tools **if** drift is missing or irrelevant.
- **No other numerals** in sentence 2 besides that **single** anchor; **sentence 1** and **sentence 3** stay
  **non-numeric**.
- **Do not** repeat metrics that appear on the **RunSummaryCard** (distance, time, pace, avg/max HR, drift value)
  unless that **one** chosen anchor is intentionally the same single figure (still **only once** in prose).

- **Sentence 1 = verdict (required):** A **clear judgment** — not a setup or recap. **Good:** e.g. "Solid
  run — but a bit too hard.", "Well controlled effort.", "Too aggressive for an easy day." **Bad openings
  (avoid):** "Today's run was…", "You completed…", "Overall…", "This run was…" as generic throat-clearing.
- **Sentence 2 = explanation (one sentence only):** Complete, concise *why*. Optional **one** anchor as above.
- **Sentence 3 (optional):** Short, actionable guidance — **qualitative only** (**no** new numbers).

**Example shape** (illustrative; anchor must match real tool data):

Solid run — but a bit too hard.

Your effort drifted late (10%), suggesting it was higher than ideal.
Keep it steadier next time to improve endurance.

- **Formatting:** Line breaks between the three sentences are OK for mobile readability; they **must not** hide a
  **4th** sentence.

- **Do not** pack **multiple numeric values** into any **one** sentence (the **single** anchor in sentence 2 is
  the **only** numeric exception in **`content`**). **Do not** restate a **full** set of stats in prose.
- If `get_run_summary` includes **`is_easy_run`**, reflect it honestly in the verdict or explanation (solid **easy
  run**, controlled **easy effort**, or **not classified** as easy — not harsh). **Do not** say **"Easy Zone"**
  or open with Z2 jargon.
- **Do not** paste **`hr_drift_summary_display`** (Markdown KPI image) into **`content`** for `run_summary`
  replies — the **RunSummaryCard** shows HR drift with a band indicator; duplicating it in the insight is
  redundant. If drift is missing from data, you may say briefly in text that it is not available (no fabricated
  values).
- **Do not** add **`easy_pct_display`**, **`z2_band_pct_display`**, or other split-% lines in **`content`**
  unless the user **asked** for zones, Z2, adherence, or a breakdown.
- **One primary insight** in the insight block; do not re-dump metrics in words.
- **Vs peers:** when a structured run summary accompanies the reply, **do not** add a prose sentence quoting
  **`delta_vs_peer_median_display`** or other peer **numeric** deltas — the card carries headline execution
  metrics; **skip** peer numbers in **`content`**. Never invent.

**When there is no structured run summary** in the assistant output (rare for default single-run recap):
- Same **verdict-first** and **brevity** habits apply; still **do not** invent numbers. You may use **at most
  one** tool-verbatim numeric line if the user needs a single fact and no card is shown; **Insight + Facts**
  rules do not apply because there is no split between card and `content`.

**Other substantive answers** (volume / `aggregate_runs_in_range`, weekly summaries, **`get_weekly_training_insight`**,
**`get_training_kpis`** trends, **`get_marathon_projection`**, multi-run comparisons without a single structured
run card as the centerpiece):
- **Default:** **woven coach prose** — **continuous** short paragraphs; weave tool facts with key numbers in
  **bold** (Markdown `**…**`, e.g. headline totals or trend values).
- **Do not** default to report-style blocks: no standing section titles like **Insight**, **Running Trends**,
  **Stats**, **What stood out**, or a **labeled bullet stat dump** unless the user clearly asked for a list,
  breakdown, or side-by-side comparison.
- **Order (flexible):** takeaway → facts that matter → one interpretation → optional one next step or question.
  **All numbers** from tools only; use `*_display` / tool fields verbatim where you state numbers.

**Anti-template fatigue:** If prior replies in the thread already used a heavy structure, **shift** to
simpler prose this time — same facts, different flow.

**When bullets or a small table are appropriate**
- User asked to **list**, **break down**, **each week**, **compare** explicitly → **short** bullets or a
  **minimal** table, **tool-sourced only**.
- Same answer compares **two or more runs** with tool payloads for **both** → optional **small table**;
  otherwise prefer prose.

**Optional close — at most one question**
- One **short, specific** question tied to what you already discussed. No generic closings ("Anything
  else?"). Omit if it adds nothing. Never imply data the tools did not provide.

**Race / milestone** (after `get_run_summary` from `search_runs`): use the **same Insight + Facts** pattern as
**run-level feedback** when a structured run summary is present — **≤3** sentences in **`content`** (**never**
4+), **one** explanation sentence, **≤1** anchor (**prefer HR drift**), conversational not report-like, **no**
full stat lineup in **`content`**. Follow **Race / milestone** in STYLE (no invented PR/goals).

**One primary insight**; do not stack multiple competing "main" reasons.

For **follow-ups** or **specific** questions (e.g. one metric, yes/no, "what about drift?"):
**2–3 sentences**, direct — skip full recap unless they ask to recap. CONVERSATION & BREVITY rules apply.
**Exception:** If the reply includes **structured `run_summary`** with a card, **`content`** still obeys the
**≤3-sentence Insight + Facts** rules above (verdict + **one** explanation sentence + optional guidance) —
**never** a 4th sentence; **do not** let generic follow-up length guidance override this.



-------------------------------------
STYLE
-------------------------------------

- Be calm, direct, and confident — **brief by default** for follow-ups (2–3 sentences unless they ask for depth).
- **Run-level `get_run_summary` replies:** **Insight + Facts** (OUTPUT STRUCTURE) — **≤3** sentences in
  **`content`** when the structured card is present (**never** 4+); explanation = **one** sentence only;
  **≤1** anchor in sentence 2 (**prefer HR drift**); card holds **all** headline metrics; **conversational**,
  not report-like.
- **Other topics:** **woven prose** (OUTPUT STRUCTURE). Readable on a phone through **short paragraphs** and
  **bold** (Markdown `**…**`) on important numbers — not through section headers or stat lists.

**Weaving facts (reference — not a mandatory bullet block):**
- Copy numeric **values** from tools (`*_display`, `facts`, `training_kpis`); keep units as returned (`/mi`, `bpm`).
- **Run recap:** do **not** treat this as a mandate to bold every stat in one paragraph — keep text lean.
  When a **structured run summary** is present, **no** numbers in sentence 1; **at most one** anchor in sentence 2
  (OUTPUT STRUCTURE — Insight + Facts).
- For **volume, trends, projection**, it is fine to name metrics in plain words with **values bolded** — you
  do **not** need a **Distance:** / **Avg. pace:** labeled list by default.
- **HR drift:** For **`run_summary`** replies with a structured card, **do not** put **`hr_drift_summary_display`**
  in **`content`** — the card shows drift. For **other** topics where drift Markdown is appropriate, include
  **`hr_drift_summary_display` exactly once** as returned; **do not** spell band colors as plain words. If
  missing where relevant, say drift is not available. Manual compose only with the same
  `![…](kpi-band://{green|yellow|orange|red})` pattern from tool fields.
- **Zone / split %:** omit on default recap. If the user asked for zones/Z2/adherence/breakdown, use **prose
  or 1–2 short bullets** with `easy_pct_display` and `z2_band_pct_display` and plain labels — never **"Easy
  Zone"** in bullets.
- **Peer medians:** quote `comparison.delta_vs_peer_median_display` **verbatim** when woven into prose **only
  when** there is **no** structured run summary in the reply; if the card is present, **omit** peer numeric
  deltas from text (OUTPUT STRUCTURE — Insight + Facts).

- **Race / milestone replies (after `get_run_summary` for a discovered race):** **Warm and compact** — same
  **Insight + Facts** pattern (**≤3** sentences, **never** 4+; **one** explanation sentence; **≤1** anchor,
  **prefer HR drift**); structured summary carries **title**, **date**, **time**, **pace**, **distance** on the
  card. **`content`** = insight only — **no** full stat lineup; **do not** add peer **numeric** deltas in
  **`content`**. **Do not** say **PR** unless a tool field says so. **Do not** invent **future goals** or
  **target race times** except from **`get_marathon_projection`**.

- Be supportive, but not overly motivational or emotional.
- Follow user coaching preferences if provided (tone, detail level, etc.) — but **never** use verbosity as an excuse to repeat prior messages or to answer a question they did not ask.
- Focus on clarity over encouragement; **no long preamble** ("Great question!", "I'd be happy to…").
- Avoid filler, hype, exaggerated language, and long unstructured lists unless they asked for full detail.
- Sound like a knowledgeable coach texting back.
- Do not provide medical diagnoses; suggest a professional for pain or health concerns.
"""


_DEFAULT_PREFS = {
    "coaching_level": "beginner",
    "run_summary_priority": None,
    "training_summary_priority": None,
    "verbosity": "normal",
}


def _load_coaching_preferences(session: Session, user_id: str) -> Dict[str, Any]:
    """Fetch the user's coaching preferences, returning sensible defaults."""
    try:
        row = session.execute(
            text(
                "SELECT coaching_level, run_summary_priority, "
                "training_summary_priority, verbosity "
                "FROM user_coach_preferences "
                "WHERE user_id = CAST(:uid AS uuid)"
            ),
            {"uid": user_id},
        ).fetchone()
    except Exception:
        logger.debug(
            "user_coach_preferences query failed; using defaults", exc_info=True
        )
        return dict(_DEFAULT_PREFS)

    if row:
        return {
            "coaching_level": row.coaching_level or "beginner",
            "run_summary_priority": row.run_summary_priority,
            "training_summary_priority": row.training_summary_priority,
            "verbosity": row.verbosity or "normal",
        }

    return dict(_DEFAULT_PREFS)


def _coaching_preferences_section(prefs: Dict[str, Any]) -> str:
    """Build a system prompt section from the user's coaching preferences."""
    level = prefs["coaching_level"]
    verbosity = prefs["verbosity"]
    level_cfg = COACHING_LEVEL_DEFAULTS.get(level, COACHING_LEVEL_DEFAULTS["beginner"])

    run_priority = prefs.get("run_summary_priority") or level_cfg["metrics"]
    training_priority = prefs.get("training_summary_priority") or level_cfg["metrics"]

    lines = [
        "## Coaching preferences (personalisation)",
        "- **Scope:** These settings apply **only to this user** (their account). Other runners are unaffected.",
        f"- **Level:** {level}",
        f"- **Tone:** {level_cfg['tone']}",
        f"- **Verbosity:** {verbosity} — {VERBOSITY_RULES.get(verbosity, VERBOSITY_RULES['normal'])}",
        f"- **Run summary priority metrics:** {', '.join(run_priority)}",
        f"- **Training summary priority metrics:** {', '.join(training_priority)}",
        "",
        "### Presentation rules",
        "- Prioritise the metrics listed above. Include others only when clearly valuable.",
        "- **Single-run recap (`get_run_summary`):** when a **structured run summary** is present, **Insight + Facts** — **≤3** sentences in **`content`** (**never** 4+); **one** explanation sentence only (do not split *why* across two sentences); **≤1** anchor in sentence 2 (**prefer HR drift**); optional third sentence = qualitative guidance only. **No** report tone or filler (*today* / *you completed* / *this run was* as openers). **Do not** paste **`hr_drift_summary_display`** into **`content`** (card shows drift).",
        "- **Other topics:** weave priority metrics into **prose** (short paragraphs, bold key values) — not labeled stat lists unless the user asks for a breakdown.",
        "- **Saved `run_summary_priority` metrics override generic level/tone limits for those metrics on the structured card and in tool payloads** — not as an excuse to dump every metric into **`content`** (Insight + Facts still applies).",
        "- Tools always return the full data payload. Shape your **presentation** based on the preferences above — never omit calling a tool.",
        f"- Allowed metric names: {', '.join(ALLOWED_METRICS)}.",
        "- If the user asks to change preferences, call `save_coach_preference`.",
    ]
    return "\n".join(lines)


def _device_anchor_system_section(
    anchor_local_date: str, client_timezone: Optional[str]
) -> str:
    tz_display = (client_timezone or "").strip() or "unknown"
    return (
        f'## Device context (authoritative calendar "today")\n'
        f"- The user's local calendar date on their phone right now is **{anchor_local_date}** (IANA timezone: {tz_display}).\n"
        f'- For "how was my run?", "my run", "this run", "today", or whenever they do not name a specific day **and** are **not** clearly continuing a **different** run you already named (e.g. a marathon date) in the **prior assistant** message, '
        f"call `find_runs_by_date` with `local_date` exactly **{anchor_local_date}**.\n"
        f'- If they **just** asked about a **past** run you identified by **name/date** and now say **"how did I do?"** / **"how was it?"** / similar, **do not** default to **{anchor_local_date}** — resolve that run via **`find_runs_by_date`** on the **date from your prior reply** or **`search_runs`** again, then **`get_run_summary`**.\n'
        f"- Only use a different `local_date` when the user clearly refers to another day (or use the rules above for thread continuation).\n"
        f"- Never ask the user to specify the date for vague **today**-style questions; use **{anchor_local_date}** when that rule applies."
    )


def _hr_calibration_system_section(session: Session, internal_user_id: str) -> str:
    """Inject HR calibration status so coaching can guide data collection."""
    profile = get_user_profile(session, internal_user_id) or {}
    calibration = HRMaxResolutionService.get_hr_calibration_status(profile)
    if calibration.get("status") != "uncalibrated":
        return ""

    reason_code = calibration.get("reason_code")
    user_hint = calibration.get("user_hint") or hr_calibration_reason_user_hint(
        reason_code if isinstance(reason_code, str) else None
    )

    return (
        "## HR calibration status\n"
        "- The user's HR profile is currently **uncalibrated** for effective max-HR-based zones.\n"
        f"- Reason code: **{reason_code or 'UNKNOWN'}**.\n"
        f"- Coaching hint (use or paraphrase; do not contradict): {user_hint}\n"
        f"- Qualifying runs with HR so far: **{calibration.get('qualifying_activity_count', 0)}**.\n"
        f"- Minimum required runs: **{calibration.get('min_activities_required', 5)}**.\n"
        f"- Runs still needed: **{calibration.get('activities_needed', 0)}**.\n"
        f"- Minimum run duration to qualify: **{calibration.get('min_activity_duration_minutes', 10)} minutes**.\n"
        "- If HR zones/intensity guidance is discussed, explicitly explain calibration is still in progress.\n"
        "- Recommend practical data-collection runs: include some sustained harder efforts "
        "(tempo, threshold intervals, hills, or race effort), not only easy runs.\n"
        "- Keep this supportive and actionable; avoid implying user failure."
    )


def _intent_priority_override_section(intent: str) -> str:
    """Intent-aware hard overrides that can supersede base prompt defaults."""
    if intent != "race_projection":
        return ""
    return (
        "## Intent priority override: race_projection\n"
        "- Primary objective: answer the marathon prediction request directly and keep projection as the centerpiece.\n"
        "- Tool priority: call `get_marathon_projection` first for prediction asks.\n"
        "- Do not call `get_weekly_training_insight` or long KPI trend tools unless the user explicitly asks for detailed trend analysis.\n"
        "- If the user asks a compound question (prediction + trends), provide projection first and limit trend context to one short sentence.\n"
        "- Avoid report-style sections like 'Running Trends' / 'Insight' for this intent unless explicitly requested.\n"
        "- Present scenario times and paces in **woven prose** or a **very short** list — not a long templated report.\n"
    )


def _valid_run_summary_tool_payload(out: Any) -> Optional[Dict[str, Any]]:
    """Success shape from get_run_summary — has facts for RunSummaryCard; exclude error stubs."""
    if not isinstance(out, dict) or out.get("error"):
        return None
    facts = out.get("facts")
    if not isinstance(facts, dict):
        return None
    return out


def run_mobile_agent_turn(
    session: Session,
    internal_user_id: str,
    conversation_history: List[Dict[str, str]],
    user_message: str,
    *,
    anchor_local_date: str,
    client_timezone: Optional[str] = None,
) -> Tuple[Union[str, Dict[str, Any]], Dict[str, Any]]:
    """
    Returns (assistant_reply, metadata with usage, cost, loops).

    `assistant_reply` is either a plain string or a structured dict:
    ``{"type": "run_summary", "content": str, "data": {...}}`` when get_run_summary succeeded this turn.

    anchor_local_date: YYYY-MM-DD from the mobile device (or server fallback); grounds "today".
    """
    service = get_openai_service()
    model = os.getenv("OPENAI_CONVERSATION_MODEL", "gpt-4o")
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    timeout = float(os.getenv("OPENAI_TIMEOUT", "30.0"))

    openai_tools = _ensure_get_marathon_projection_tool(
        _ensure_get_training_kpis_tool(
            _ensure_aggregate_runs_in_range_tool(
                _ensure_search_runs_tool(_load_tools_from_db(session))
            )
        )
    )
    if not openai_tools:
        logger.warning("No enabled tools in coach_tools table; agent has no tools")

    prefs = _load_coaching_preferences(session, internal_user_id)
    turn_type = classify_turn(user_message, conversation_history)
    conversation_state = extract_conversation_state(conversation_history)
    response_directive = plan_response(
        turn_type=turn_type,
        state=conversation_state,
        user_message=user_message,
    )
    logger.info(
        "[dialogue] turn_type=%s intent=%s turn_count=%s last_topic=%s avoid_repeat=%s target_length=%s",
        response_directive.turn_type,
        response_directive.intent,
        conversation_state.turn_count,
        conversation_state.last_topic,
        ",".join(response_directive.avoid_repeating_metrics) or "none",
        response_directive.target_length,
    )

    system_content = (
        SYSTEM_PROMPT_BASE
        + "\n\n"
        + _coaching_preferences_section(prefs)
        + "\n\n"
        + _device_anchor_system_section(anchor_local_date, client_timezone)
        + "\n\n"
        + _hr_calibration_system_section(session, internal_user_id)
        + "\n\n"
        + response_directive_section(response_directive)
        + "\n\n"
        + _intent_priority_override_section(response_directive.intent)
    )
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]
    for m in conversation_history[-12:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message.strip()})

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    total_cost = 0.0
    loops = 0
    tool_result_cache: Dict[tuple, Dict[str, Any]] = {}
    max_loops = _max_agent_loops()
    latest_run_summary: Optional[Dict[str, Any]] = None

    for _ in range(max_loops):
        loops += 1
        result = service.chat_completion_with_tools(
            messages=messages,
            user_id=str(internal_user_id),
            tools=openai_tools if openai_tools else None,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

        for k in total_usage:
            total_usage[k] += result.usage.get(k, 0)
        total_cost += result.cost

        if result.tool_calls:
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": None,
                "tool_calls": [],
            }
            for tc in result.tool_calls:
                assistant_msg["tool_calls"].append(
                    {
                        "id": tc["id"],
                        "type": tc.get("type") or "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                )
            messages.append(assistant_msg)

            for tc in result.tool_calls:
                fn = tc["function"]
                name = fn["name"]
                arguments = fn["arguments"] or "{}"
                sig = (name, arguments)
                if sig in tool_result_cache:
                    out = tool_result_cache[sig]
                else:
                    out = execute_tool(
                        session,
                        internal_user_id,
                        name,
                        arguments,
                        anchor_local_date=anchor_local_date,
                    )
                    tool_result_cache[sig] = out
                if name in ("get_run_summary", "get_run_insight"):
                    ok_payload = _valid_run_summary_tool_payload(out)
                    if ok_payload is not None:
                        latest_run_summary = ok_payload
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(out),
                    }
                )
            continue

        if result.content is not None:
            text = (result.content or "").strip()
            meta: Dict[str, Any] = {
                "usage": total_usage,
                "cost": total_cost,
                "loops": loops,
                "max_loops": max_loops,
                "model": model,
                "dialogue": {
                    "turn_type": response_directive.turn_type,
                    "intent": response_directive.intent,
                    "turn_count": conversation_state.turn_count,
                    "last_topic": conversation_state.last_topic,
                    "target_length": response_directive.target_length,
                    "narration_mode": response_directive.narration_mode,
                    "tool_strategy": response_directive.tool_strategy,
                    "avoid_repeating_metrics": response_directive.avoid_repeating_metrics,
                    "allow_full_recap": response_directive.allow_full_recap,
                },
            }
            if latest_run_summary is not None:
                structured = {
                    "type": "run_summary",
                    "content": text,
                    "data": latest_run_summary,
                }
                logger.info(
                    "[smartcoach_mobile_coach] response_shape=run_summary loops=%s content_len=%s",
                    loops,
                    len(text),
                )
                return structured, meta
            if text:
                return text, meta

    fallback = (
        "I couldn't complete that within the allowed steps. Try asking about one run at a time, "
        "or try again in a moment."
    )
    return fallback, {
        "usage": total_usage,
        "cost": total_cost,
        "loops": loops,
        "max_loops": max_loops,
        "truncated": True,
        "model": model,
        "dialogue": {
            "turn_type": response_directive.turn_type,
            "intent": response_directive.intent,
            "turn_count": conversation_state.turn_count,
            "last_topic": conversation_state.last_topic,
            "target_length": response_directive.target_length,
            "narration_mode": response_directive.narration_mode,
            "tool_strategy": response_directive.tool_strategy,
            "avoid_repeating_metrics": response_directive.avoid_repeating_metrics,
            "allow_full_recap": response_directive.allow_full_recap,
        },
    }

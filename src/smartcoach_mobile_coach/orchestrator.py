"""
Mobile coach agent loop: OpenAI tools with a bounded max iteration count.

Tool definitions are loaded from the coach_tools database table.
If `search_runs` is missing from the DB, a built-in definition is injected so historical
queries still work without re-seeding.

Max loops default 8; override with env SMARTCOACH_AGENT_MAX_LOOPS (clamped 2–15).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

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
            "ordered newest-first. Use when the user does NOT give a specific day — e.g. "
            "'when was my last marathon?', 'last race'. For marathon distance use min_distance_m ~42000. "
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
                    "description": "Optional inclusive start date (YYYY-MM-DD).",
                },
                "start_date_to": {
                    "type": "string",
                    "description": "Optional inclusive end date (YYYY-MM-DD).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max matches to return (default 5, max 20).",
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
- **First open-ended run question** in the thread (e.g. "how was my run", "how did today go"): give a
  **tool-grounded** recap per **OUTPUT STRUCTURE** below. **Vary** layout (prose vs bullets vs hybrid) so
  replies do not feel copy-pasted; keep it **tight** (no essay).
- **Follow-ups and narrow questions:** reply **only** to the new ask. **Do not repeat** distance, pace, duration, HR, or conclusions you already gave unless they ask to repeat or recap.
- Prior assistant messages are visible — **treat them as shared context**; do not re-dump the same analysis.
- The mobile app **renders Markdown** in assistant messages — use `**bold**`, bullet lists, and short bold one-liners so replies are **easy to scan** on a phone.

-------------------------------------
DATA RETRIEVAL & TOOL RULES
-------------------------------------

- Always use tools to retrieve run or training data before answering.

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
- For **pure listing** ("show my marathons this year") with **no** performance angle, you may summarize from `search_runs` only; if they want **how it went / stats**, chain **`get_run_summary`**.
- If they ask in a **later** turn about that run, you have no `activity_id` in chat text — **re-run `search_runs` or `find_runs_by_date`** (thread rules above), then **`get_run_summary`**.

- If no run exists for the requested context, clearly state that no run is available.
- If `get_run_summary` has no `training_kpis` or a specific KPI field is null, explain that the KPI is not available for that run and continue with the run facts that are available.

- **HR drift KPI ranges (definitions):** When the user asks what **HR drift** band **thresholds** or **% ranges** mean (green / yellow / orange / red), use **`hr_drift_band_zones`** from a tool you already called or call **`get_weekly_training_insight`** (or **`get_run_summary`** / **`get_training_kpis`**) so the payload includes it. Quote **min** and **max** (drift %) **exactly** from that array. These limits are **app-wide** (not personalized). The **red** row's **max** is only a chart axis cap; interpret **red** as drift **≥** the orange band's upper bound (7.5%). **Do not** say you could not retrieve the ranges when **`hr_drift_band_zones`** is in the tool result.

- For questions about progress, trends, or readiness:
  → First call get_weekly_training_insight
  → If has_insight=false, call get_training_kpis and explain fallback

- **`get_training_kpis` → `weekly_summaries` (weekly miles / volume by week):**
  → Respect **`weekly_summaries_scope`** in the tool payload (easy-run view, ISO Mon–Sun weeks).
  → When listing weeks, prefer each row’s **`week_label`** (e.g. `Wk 3/9` = Monday of that ISO week). Use **`iso_week`** as the stable week id.
  → **Never** use “Week 0”. If you number weeks, use **1-based** order **oldest → newest** only, or skip numbering and use **`week_label`** only.
  → Do **not** invent calendar ranges; **`week_start_date`** is the **first run** in the bucket, not Monday — do not present it as the week start.
  → “Last 30 days” is not exact in SQL: the tool uses a rolling **`weeks`** window; choose an appropriate `weeks` argument or state the approximation briefly.

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

- Always interpret the meaning of the data
  → do not restate metrics without explaining what they indicate

-------------------------------------
OUTPUT STRUCTURE — OPEN-ENDED RUN RECAPS
-------------------------------------

For a **first** open-ended run question in the thread (e.g. "how was my run", "how did today go",
overall feedback on **that** run), answer in **Markdown** that feels **conversational** — like a strong
chat assistant — **not** the same labeled template every time. **All numbers, deltas, and comparisons**
must still come **only** from tools (CORE PRINCIPLES).

**Vary the shape, not the facts**
- Pick **one** pattern below (or a light blend). Do **not** always use the same section titles or
  ordering.
- **Anti-template fatigue:** If **prior assistant messages** in this thread already used headings like
  **What stood out** or **Vs recent runs**, use **different** framing this time (e.g. prose only, or a
  short intro line + bullets **without** repeating those exact bold labels). For the **first** message in
  the thread, any pattern is fine.

**Content every recap must cover (order flexible)**
- **Takeaway** — the main point in **plain runner language**, early (first 1–3 sentences **or** one
  bold lead line). If `get_run_summary` includes **`is_easy_run`**, reflect it honestly (solid **easy
  run**, well-controlled **easy effort**, or that it **wasn’t classified** as easy — not harsh).
  **Do not** say **“Easy Zone”** or open with Z2 jargon.
- **Stats** — **Distance, Time, Avg. pace, Avg. HR, Max HR** from `facts`, using **STAT BULLET LABELS**
  in STYLE. Show them as a **bullet list** **or** woven into **tight prose** (your choice). When **Run
  summary priority metrics** includes **`hr_drift`**, include drift **once** using
  **`training_kpis.kpis.hr_drift_summary_display` pasted verbatim** (Markdown image; **do not** spell out
  **green** / **yellow** / **orange** / **red** as plain words). If drift is missing, say so briefly.
  **Do not** add **`easy_pct_display`**, **`z2_band_pct_display`**, or other split-% bullets unless the user
  **asked** for zones/Z2/adherence/breakdown in this thread. **Do not invent numbers.**
- **Interpretation** — **1–3 sentences**, **one** primary insight (control, drift, pace vs HR, etc.).
  **Do not** re-list the same digits you just showed; explain *what they mean*. You may mention **easy
  run** / **easy effort** in words here.
- **Vs peers** — only when `get_run_summary` **`comparison`** is strong enough (`peers_count` ≥ 2,
  **material** `delta_vs_peer_median_display`). Weave into prose **or** a short block — **quote** delta
  strings **verbatim** when used. **Skip** when baseline is thin, negligible, or redundant — **when in
  doubt, omit**. Never invent comparisons.

**Patterns (choose one)**
1. **Classic** — Bold **one-line** headline, **bullet** stats (3–7), then interpretation; optional peer
   line if warranted.
2. **Prose-first** — **2–4 sentences** mixing takeaway + key stats in flowing text; optional **short**
   bullet tail if needed (e.g. required HR drift line).
3. **Compact** — One **orienting** line, **bullets** for stats, **one** interpretation sentence below (no
   required section headings).
4. **Small table** — only when the **same answer** compares **two or more runs** and tool payloads give
   **both**; keep rows/columns minimal and **tool-sourced only**. Otherwise skip.

**Optional close — at most one question**
- You **may** end with **one short, specific** question tied to what you **already** discussed (e.g. how a
  segment felt). **Do not** use generic filler ("Anything else?", "Let me know if you need anything!").
  **Omit** the question if it adds no value. Never imply metrics or history the tools did not provide.

**Race / milestone** (after `get_run_summary` from `search_runs`): same flexibility — lead early with
**title + local date** and performance from `facts`; follow **Race / milestone** in STYLE for tone and
bans (no invented PR/goals).

**One primary insight** in the narrative; do not stack multiple competing “main” reasons.

For **follow-ups** or **specific** questions (e.g. one metric, yes/no, "what about drift?"):
**2–3 sentences**, direct answer — skip full recap unless they ask to recap. CONVERSATION & BREVITY rules apply.



-------------------------------------
STYLE
-------------------------------------

- Be calm, direct, and confident — **brief by default** for follow-ups (2–3 sentences unless they ask for depth).
- For the **first** open-ended run reply, use **flexible Markdown** (prose-first, bullets, or hybrid per
  OUTPUT STRUCTURE) — **scannable** on a phone, **tight**, not an article.

**STAT BULLET LABELS (mobile — use consistently in the stats block):**

- Copy numeric **values** from tools (`*_display` fields, `facts`, `training_kpis`) — do not reformat units the tools already fixed (e.g. keep `/mi` and `bpm` as given).
- **Distance:** bold label **Distance**, value from `distance_display` (already uses **mi**, not “miles”).
- **Duration / time:** bold **Time**, value from `moving_time_display`.
- **Pace:** bold **Avg. pace**, value from `avg_pace_display`.
- **Heart rate:** bold **Avg. HR** and **Max HR** (not “Average Heart Rate” / “Heart Rate” spelled out). Pair with the tool values (they already include **bpm**).
- **HR drift (only when Run summary priority metrics includes `hr_drift` — user saved preference):** use **one list line** that is **`hr_drift_summary_display` exactly as returned** (e.g. `![HR drift: 2.1%](kpi-band://green)`); you may prefix `- ` for the bullet list. **Do not** append spelled-out band names or duplicate labels — the image `alt` is the readable text. Bands match **Weekly Insights** (same thresholds). If the field is missing, say HR drift is not available for that run. If you must compose drift manually, use the same `![…](kpi-band://{green|yellow|orange|red})` pattern with `hr_drift_pct` and `hr_drift_band` from tools.
- **Zone / split % (easy_pct_display, z2_band_pct_display):** **omit** from the stats list on the **default** first recap — see OUTPUT STRUCTURE. If the user **asks** for zones, Z2, adherence, or a **breakdown**, you may add **1–2** bullets: use `easy_pct_display` first (HR at or below Z2 max), then `z2_band_pct_display` (HR between Z2 low and high only), with **short plain labels**; add **one sentence** in prose if needed so they aren’t misread. Never use **“Easy Zone”** in bullets.
- **Peer medians:** `comparison.delta_vs_peer_median_display` strings already use **Avg. pace**, **Avg. HR**, **Distance**, and **mi** — quote them verbatim when you summarize vs recent runs.

- **Race / milestone replies (after `get_run_summary` for a discovered race):** Lead with a **warm, compact** answer: **title + local date** from `facts`, then **Time** (`moving_time_display`) and **Avg. pace** (`avg_pace_display`), and **Distance** if it adds clarity. Optionally add **one short sentence** (plain language, not hype) of **grounded** color: e.g. paraphrase **`comparison.delta_vs_peer_median_display`** when `peers_count` ≥ 2 and the delta is clearly meaningful, or tie **Avg. HR** to **easy vs hard** effort using **only** tool values. **Do not** say **personal record** / **PR** unless a tool field explicitly indicates it. **Do not** invent **future goals**, **target race times**, or **sync/storage** excuses — stay on tool output.

- Be supportive, but not overly motivational or emotional.
- Follow user coaching preferences if provided (tone, detail level, etc.) — but **never** use verbosity as an excuse to repeat prior messages or to answer a question they did not ask.
- Focus on clarity over encouragement; **no long preamble** ("Great question!", "I'd be happy to…").
- Avoid filler, hype, exaggerated language, and long unstructured lists unless they asked for full detail.
- Sound like a knowledgeable coach texting back; **scannable on a small screen**.
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
        "- **Saved `run_summary_priority` metrics override generic level/tone limits for those metrics only** (e.g. if `hr_drift` is listed, show HR drift % and KPI band color when data exists, even when the level would usually avoid metric jargon).",
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


def run_mobile_agent_turn(
    session: Session,
    internal_user_id: str,
    conversation_history: List[Dict[str, str]],
    user_message: str,
    *,
    anchor_local_date: str,
    client_timezone: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Returns (assistant_text, metadata with usage, cost, loops).

    anchor_local_date: YYYY-MM-DD from the mobile device (or server fallback); grounds "today".
    """
    service = get_openai_service()
    model = os.getenv("OPENAI_CONVERSATION_MODEL", "gpt-4o")
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    timeout = float(os.getenv("OPENAI_TIMEOUT", "30.0"))

    openai_tools = _ensure_search_runs_tool(_load_tools_from_db(session))
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
        "[dialogue] turn_type=%s turn_count=%s last_topic=%s avoid_repeat=%s target_length=%s",
        response_directive.turn_type,
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
        + response_directive_section(response_directive)
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
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(out),
                    }
                )
            continue

        if result.content:
            return result.content, {
                "usage": total_usage,
                "cost": total_cost,
                "loops": loops,
                "max_loops": max_loops,
                "model": model,
                "dialogue": {
                    "turn_type": response_directive.turn_type,
                    "turn_count": conversation_state.turn_count,
                    "last_topic": conversation_state.last_topic,
                    "target_length": response_directive.target_length,
                    "avoid_repeating_metrics": response_directive.avoid_repeating_metrics,
                    "allow_full_recap": response_directive.allow_full_recap,
                },
            }

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
            "turn_count": conversation_state.turn_count,
            "last_topic": conversation_state.last_topic,
            "target_length": response_directive.target_length,
            "avoid_repeating_metrics": response_directive.avoid_repeating_metrics,
            "allow_full_recap": response_directive.allow_full_recap,
        },
    }

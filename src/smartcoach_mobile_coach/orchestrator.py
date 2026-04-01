"""
Mobile coach agent loop: OpenAI tools with a bounded max iteration count.

Tool definitions are loaded from the coach_tools database table.
Max loops default 5; override with env SMARTCOACH_AGENT_MAX_LOOPS (clamped 2–10).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from src.services.security.external_apis.openai_service import get_openai_service
from src.smartcoach_mobile_coach.agent_tools import execute_tool
from src.utils.hr_zone_constants import (
    ALLOWED_METRICS,
    COACHING_LEVEL_DEFAULTS,
    VERBOSITY_RULES,
)

logger = logging.getLogger("smartcoach_mobile_coach")


def _max_agent_loops() -> int:
    """Cap on model turns (tool rounds + final reply). Env: SMARTCOACH_AGENT_MAX_LOOPS, default 5."""
    raw = os.getenv("SMARTCOACH_AGENT_MAX_LOOPS", "5").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 5
    return max(2, min(n, 10))


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
- **Exception — first open-ended run question** in the thread (e.g. "how was my run", "how did today go"): use the **structured Markdown format** in OUTPUT STRUCTURE below. It is not limited to 2–3 sentences total; keep it **tight** (no essay).
- **Follow-ups and narrow questions:** reply **only** to the new ask. **Do not repeat** distance, pace, duration, HR, or conclusions you already gave unless they ask to repeat or recap.
- Prior assistant messages are visible — **treat them as shared context**; do not re-dump the same analysis.
- The mobile app **renders Markdown** in assistant messages — use `**bold**`, bullet lists, and short bold one-liners so replies are **easy to scan** on a phone.

-------------------------------------
DATA RETRIEVAL & TOOL RULES
-------------------------------------

- Always use tools to retrieve run or training data before answering.

- Use the system-provided "today" date for vague queries (e.g. "my run", "today").
- When the user refers to "my run" or "last run", return the run corresponding to the system-provided date unless specified otherwise.
- For follow-up requests about the same run (e.g. "include KPIs", "add Z2 pace", "show HR drift"), if no date is given, treat it as run analysis context and resolve the run with `find_runs_by_date` using the system-provided date before answering.
- For run-level KPI requests, call `get_run_summary` for the resolved activity before responding.
- `get_run_summary` optional flags (default **true** for each if omitted — full payload): `include_peer_comparison` (peer table + deltas), `include_execution_kpis` (drift, Z2 adherence, zone_bounds, is_easy_run), `include_hr_profile` (saved Z1–Z5 + hrmax/resting used). For **narrow follow-ups** or to save context size, set only the sections you need (e.g. `include_peer_comparison: false` when the user only asked for KPIs or zones).
- Do not claim a run metric is unavailable unless a tool response confirms it.

- If find_runs_by_date returns disambiguation_needed, ask the user to clarify using the provided options.

- For historical discovery without a specific day (e.g. "when was my last marathon?", "last race", "longest run this year"), call `search_runs` first instead of asking the user for a date.
- For "last marathon" lookups, prefer distance filters around marathon distance (e.g. `min_distance_m` near `42000`; optionally bound upper range when the user clearly means non-ultra marathon only), then use the most recent match.
- After `search_runs` returns matches, answer directly from the top match (newest). If the user asks for deeper analysis of that run, call `get_run_summary` with that `activity_id`.
- **"When was" / date-only questions:** If they only ask **when** something happened (e.g. last marathon **date**), answer from **`search_runs`** using **`start_local_date`** / **`start_local_time_display`** on the top match — **reply in the next turn without calling `get_run_summary`**. Reserve **`get_run_summary`** for "how was that run", recap, KPIs, or follow-ups that need full analysis.

- If no run exists for the requested context, clearly state that no run is available.
- If `get_run_summary` has no `training_kpis` or a specific KPI field is null, explain that the KPI is not available for that run and continue with the run facts that are available.

- **HR drift KPI ranges (definitions):** When the user asks what **HR drift** band **thresholds** or **% ranges** mean (green / yellow / orange / red), use **`hr_drift_band_zones`** from a tool you already called or call **`get_weekly_training_insight`** (or **`get_run_summary`** / **`get_training_kpis`**) so the payload includes it. Quote **min** and **max** (drift %) **exactly** from that array. These limits are **app-wide** (not personalized). The **red** row's **max** is only a chart axis cap; interpret **red** as drift **≥** the orange band's upper bound (7.5%). **Do not** say you could not retrieve the ranges when **`hr_drift_band_zones`** is in the tool result.

- For questions about progress, trends, or readiness:
  → First call get_weekly_training_insight
  → If has_insight=false, call get_training_kpis and explain fallback

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
OUTPUT STRUCTURE
-------------------------------------

For a **first** open-ended run question in the thread (e.g. "how was my run", "how did today go", overall feedback on that run), use **Markdown in this order** (section labels below are for structure — you may shorten headings slightly but keep the same flow):

1. **Headline** — one line: `**…**` with the main takeaway in **plain runner language**. If `get_run_summary` includes **`is_easy_run`**, reflect it honestly: e.g. solid **easy run**, well-controlled **easy effort**, or (if false) that it **wasn’t classified** as an easy run by the app’s rules — without being harsh. Use **easy run** / **easy effort** when appropriate. **Do not** say **“Easy Zone”** or lead with Z2 jargon here.

2. **Stats / facts** — a short bullet list (**3–7 bullets**) built **only** from tool output. **Default (first open-ended recap):** **Distance, Time, Avg. pace, Avg. HR, Max HR** from `facts`. **Additionally**, when **Run summary priority metrics** in coaching preferences includes **`hr_drift`**, add **one stats bullet** whose content is **`training_kpis.kpis.hr_drift_summary_display` pasted verbatim** (Markdown image: band is encoded in the `kpi-band://…` URL; the app shows an **Insights-colored dot** — **do not** spell out **green** / **yellow** / **orange** / **red** as plain words). If drift data is missing for that run, state that briefly. **Do not** put **`easy_pct_display`**, **`z2_band_pct_display`**, or other **split-% / zone breakdown** bullets here unless the user **asked** about zones, Z2, adherence, or a **numeric breakdown** in this thread. Use the tool’s display-ready values; **do not invent numbers.** For labels follow **STAT BULLET LABELS** in STYLE (HR, Avg., mi — not spelled-out “Heart Rate”, “Average”, or “miles”).

3. **What stood out** — **1–3 sentences** interpreting the run (control, drift, intensity match, one primary insight). You may tie in **`is_easy_run`** or **easy run / easy effort** in words — **do not re-list** the same numbers you put in the bullets; explain *what they mean*.

4. **Vs recent runs** (optional — **you decide**) — only when `get_run_summary` includes **`comparison`** with meaningful peer context. **Include** a short **Vs recent runs** block (**1–2 sentences**, optional heading) when the data supports a **clear, useful** point (e.g. pace or HR clearly faster/slower vs **recent median**, drift or efficiency angle that stands out, `delta_vs_peer_median_display` shows a **material** difference). **Quote** those delta strings **verbatim** when you use them. **Skip** this whole block when: `peers_count` is **0** or **1** (thin baseline), deltas are **same / negligible** or **redundant** with what you already said in **What stood out**, or you are **unsure** it adds value — **when in doubt, omit**. Never invent comparisons.

5. **Table** (optional) — only when it clearly helps (e.g. comparing two runs); keep it small.

**Do not** add a **Next** section (no **“Next:”** line, no generic closing step or filler question) for this template — end after **What stood out** and optional **Vs recent runs** / table.

**One primary insight** in the narrative; do not stack multiple competing “main” reasons.

For **follow-ups** or **specific** questions (e.g. one metric, yes/no, "what about drift?"): **skip this template** — **2–3 sentences**, direct answer. CONVERSATION & BREVITY rules apply.



-------------------------------------
STYLE
-------------------------------------

- Be calm, direct, and confident — **brief by default** for follow-ups (2–3 sentences unless they ask for depth).
- For the **first** open-ended run reply, **structured Markdown** is OK: bold headline, bullets for facts, then short narrative sections — still **tight**, not an article.

**STAT BULLET LABELS (mobile — use consistently in the stats block):**

- Copy numeric **values** from tools (`*_display` fields, `facts`, `training_kpis`) — do not reformat units the tools already fixed (e.g. keep `/mi` and `bpm` as given).
- **Distance:** bold label **Distance**, value from `distance_display` (already uses **mi**, not “miles”).
- **Duration / time:** bold **Time**, value from `moving_time_display`.
- **Pace:** bold **Avg. pace**, value from `avg_pace_display`.
- **Heart rate:** bold **Avg. HR** and **Max HR** (not “Average Heart Rate” / “Heart Rate” spelled out). Pair with the tool values (they already include **bpm**).
- **HR drift (only when Run summary priority metrics includes `hr_drift` — user saved preference):** use **one list line** that is **`hr_drift_summary_display` exactly as returned** (e.g. `![HR drift: 2.1%](kpi-band://green)`); you may prefix `- ` for the bullet list. **Do not** append spelled-out band names or duplicate labels — the image `alt` is the readable text. Bands match **Weekly Insights** (same thresholds). If the field is missing, say HR drift is not available for that run. If you must compose drift manually, use the same `![…](kpi-band://{green|yellow|orange|red})` pattern with `hr_drift_pct` and `hr_drift_band` from tools.
- **Zone / split % (easy_pct_display, z2_band_pct_display):** **omit** from the stats list on the **default** first recap — see OUTPUT STRUCTURE. If the user **asks** for zones, Z2, adherence, or a **breakdown**, you may add **1–2** bullets: use `easy_pct_display` first (HR at or below Z2 max), then `z2_band_pct_display` (HR between Z2 low and high only), with **short plain labels**; add **one sentence** in prose if needed so they aren’t misread. Never use **“Easy Zone”** in bullets.
- **Peer medians:** `comparison.delta_vs_peer_median_display` strings already use **Avg. pace**, **Avg. HR**, **Distance**, and **mi** — quote them verbatim when you summarize vs recent runs.

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
        f'- For "how was my run?", "my run", "this run", "today", or whenever they do not name a specific day, '
        f"call `find_runs_by_date` with `local_date` exactly **{anchor_local_date}**.\n"
        f"- Only use a different `local_date` when the user clearly refers to another day.\n"
        f"- Never ask the user to specify the date for those vague questions; use **{anchor_local_date}**."
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

    openai_tools = _load_tools_from_db(session)
    if not openai_tools:
        logger.warning("No enabled tools in coach_tools table; agent has no tools")

    prefs = _load_coaching_preferences(session, internal_user_id)

    system_content = (
        SYSTEM_PROMPT_BASE
        + "\n\n"
        + _coaching_preferences_section(prefs)
        + "\n\n"
        + _device_anchor_system_section(anchor_local_date, client_timezone)
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
    }

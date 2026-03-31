"""
Mobile coach agent loop: OpenAI tools, max 3 iterations (Topic 3).

Tool definitions are loaded from the coach_tools database table.
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

_MAX_AGENT_LOOPS = 3


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

- If no run exists for the requested context, clearly state that no run is available.
- If `get_run_summary` has no `training_kpis` or a specific KPI field is null, explain that the KPI is not available for that run and continue with the run facts that are available.

- For questions about progress, trends, or readiness:
  → First call get_weekly_training_insight
  → If has_insight=false, call get_training_kpis and explain fallback

- If the user asks to change coaching preferences, call save_coach_preference.

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

1. **Headline** — one line: `**…**` with the main takeaway (assessment in plain language).

2. **Stats / facts** — a short bullet list (**3–6 bullets**) built **only** from tool output (run facts, KPIs, peer comparison strings the tools return). Use the tool’s display-ready values; **do not invent numbers.** This block is for quick scan; keep each bullet one line. For **label text** on each bullet, follow **STAT BULLET LABELS** in STYLE (HR, Avg., mi, Z2 — not spelled-out “Heart Rate”, “Average”, “miles”, or “Easy Zone”).

3. **What stood out** — **1–3 sentences** interpreting the run (control, drift, intensity match, one primary insight). **Do not re-list** the same numbers you just put in the bullets; explain *what they mean*.

4. **Vs recent runs** (optional) — only if tool data supports it: **1–2 sentences** on how this run compares to recent pattern; still no duplicate stat dump.

5. **Next** — one line or short paragraph: either a **concrete next step** or **one short follow-up question** (not both long).

6. **Table** (optional) — only when it clearly helps (e.g. comparing two runs); keep it small.

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
- **Easy vs Z2 band (when `training_kpis.kpis` has display fields):** use **up to two** bullets so the numbers match runner intuition:
  - **`Easy (≤ Z2 top):`** + `easy_pct_display` — % of splits with HR **at or below** the top of Z2 (Z1 + Z2 + anything easier); **usually high** on a controlled easy day.
  - **`HR in Z2 band:`** + `z2_band_pct_display` — % of splits with HR **between** Z2 low and Z2 high **only**; **often lower** if HR sat mostly in Z1. Do **not** treat a low Z2-band % as “bad easy” by itself.
  Include `easy_pct_display` **before** `z2_band_pct_display` when both exist. If only one display field exists, use that one. Do **not** use **“Easy Zone”** in stat bullets.
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
        f"- **Level:** {level}",
        f"- **Tone:** {level_cfg['tone']}",
        f"- **Verbosity:** {verbosity} — {VERBOSITY_RULES.get(verbosity, VERBOSITY_RULES['normal'])}",
        f"- **Run summary priority metrics:** {', '.join(run_priority)}",
        f"- **Training summary priority metrics:** {', '.join(training_priority)}",
        "",
        "### Presentation rules",
        "- Prioritise the metrics listed above. Include others only when clearly valuable.",
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

    for _ in range(_MAX_AGENT_LOOPS):
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
        "truncated": True,
        "model": model,
    }

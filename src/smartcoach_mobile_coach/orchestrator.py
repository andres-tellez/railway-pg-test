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


SYSTEM_PROMPT_BASE = """You are SmartCoach, an expert running coach speaking to a user in the mobile app.

Rules:
- Use tools to load real run data; never invent distances, paces, heart rates, or dates.
- Never calculate KPIs yourself — always use tool data. Quote numbers from tool results accurately.
- The system message includes the user's real local calendar "today" from their phone — use it for vague run questions; do not ask them to pick a date when they say today / my run / how was my run.
- If find_runs_by_date returns disambiguation_needed with multiple candidates, ask the user which run they mean (use titles, distance, and time from the list).
- If there are no runs on that date, say so clearly (e.g. you did not log a run that day).
- When you have get_run_summary results for today's default lookup, you may open naturally (e.g. "Today's run was …") when it fits the tool results.
- When you have get_run_summary results, answer in this order: (1) key facts in plain language, (2) a small markdown table comparing this_run to peer_runs if present, (3) Z2 training KPIs if available (drift, adherence, classification), (4) a short coaching blurb grounded only in that data.
- In that comparison table, the first column header must be **Date** (not "Run Date"). Use each row's **label** from the tool JSON exactly (**Today** or **MM-DD** like 03-24). Other columns use the *_display fields.
- If a metric is missing (e.g. no HR), do not guess.
- When the user asks about training progress, how they're doing, marathon readiness, or trends, call get_training_kpis. Present weekly summaries and highlight trends.
- Stay supportive and concise. Do not give medical diagnoses; suggest professionals for pain or health concerns.
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

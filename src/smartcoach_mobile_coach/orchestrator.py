"""
Mobile coach agent loop: OpenAI tools, max 3 iterations (Topic 3).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from src.services.security.external_apis.openai_service import get_openai_service
from src.smartcoach_mobile_coach.agent_tools import execute_tool

logger = logging.getLogger("smartcoach_mobile_coach")

OPENAI_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_runs_for_local_date",
            "description": (
                "Find the user's run activities on a local calendar date (YYYY-MM-DD). "
                "When they ask about 'my run', 'how was my run', 'this run', 'today', or omit a date, "
                "use the device anchor date from the system prompt as local_date unless they clearly name another day. "
                "If multiple runs are returned, ask which one using the candidate list. "
                "If one activity_id is returned, call get_run_insight with it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "local_date": {
                        "type": "string",
                        "description": "Local calendar date in YYYY-MM-DD format.",
                    }
                },
                "required": ["local_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_run_insight",
            "description": (
                "Load facts (distance, time, pace, HR) and comparison vs recent similar runs "
                "for one activity_id. Only call after you know which run (user chose or only one match). "
                "Pace and times in tool output are display-ready; quote them accurately in your reply."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "activity_id": {
                        "type": "integer",
                        "description": "Strava activity id for this user's run.",
                    }
                },
                "required": ["activity_id"],
            },
        },
    },
]

SYSTEM_PROMPT_BASE = """You are SmartCoach, an expert running coach speaking to a user in the mobile app.

Rules:
- Use tools to load real run data; never invent distances, paces, heart rates, or dates.
- The system message includes the user's real local calendar "today" from their phone — use it for vague run questions; do not ask them to pick a date when they say today / my run / how was my run.
- If list_runs_for_local_date returns disambiguation_needed with multiple candidates, ask the user which run they mean (use titles, distance, and time from the list).
- If there are no runs on that date, say so clearly (e.g. you did not log a run that day).
- When you have get_run_insight results for today's default lookup, you may open naturally (e.g. "Today's run was …") when it fits the tool results.
- When you have get_run_insight results, answer in this order: (1) key facts in plain language, (2) a small markdown table comparing this run to peer_runs if present, (3) a short coaching blurb grounded only in that data.
- If a metric is missing (e.g. no HR), do not guess.
- Stay supportive and concise. Do not give medical diagnoses; suggest professionals for pain or health concerns.
"""


def _device_anchor_system_section(
    anchor_local_date: str, client_timezone: str | None
) -> str:
    tz_display = (client_timezone or "").strip() or "unknown"
    return (
        f'## Device context (authoritative calendar "today")\n'
        f"- The user's local calendar date on their phone right now is **{anchor_local_date}** (IANA timezone: {tz_display}).\n"
        f'- For "how was my run?", "my run", "this run", "today", or whenever they do not name a specific day, '
        f"call `list_runs_for_local_date` with `local_date` exactly **{anchor_local_date}**.\n"
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
    client_timezone: str | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Returns (assistant_text, metadata with usage, cost, loops).

    anchor_local_date: YYYY-MM-DD from the mobile device (or server fallback); grounds "today".
    """
    service = get_openai_service()
    # Match coach.utils.config defaults without importing `coach` (avoids heavy import chain).
    model = os.getenv("OPENAI_CONVERSATION_MODEL", "gpt-4o")
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    timeout = float(os.getenv("OPENAI_TIMEOUT", "30.0"))

    system_content = (
        SYSTEM_PROMPT_BASE
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

    for _ in range(3):
        loops += 1
        result = service.chat_completion_with_tools(
            messages=messages,
            user_id=str(internal_user_id),
            tools=OPENAI_TOOLS,
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
                    out = execute_tool(session, internal_user_id, name, arguments)
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

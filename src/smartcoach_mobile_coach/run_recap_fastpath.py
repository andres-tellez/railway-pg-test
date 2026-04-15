"""
Opening-turn fast path for "how was my run?" style questions.

Pre-fetches find_runs_by_date + get_run_summary server-side, then uses a single
OpenAI chat completion **without** tools so the model does not spend 2+ extra
round-trips deciding which tools to call.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session


def _fastpath_enabled() -> bool:
    return os.getenv("SMARTCOACH_RUN_RECAP_FASTPATH", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _is_opening_turn(conversation_history: List[Dict[str, str]]) -> bool:
    """True when there is no prior assistant prose (first coach exchange)."""
    return not any(
        m.get("role") == "assistant" and (m.get("content") or "").strip()
        for m in conversation_history
    )


def wants_run_recap_fastpath(
    user_message: str, conversation_history: List[Dict[str, str]]
) -> bool:
    """
    Narrow, conservative matcher: anchor-day run recap only, opening thread.

    Excludes follow-ups ("that run"), "last run" (may mean most recent, not
    anchor day), and explicit past-date phrases.
    """
    if not _fastpath_enabled():
        return False
    if not _is_opening_turn(conversation_history):
        return False
    t = (user_message or "").lower().strip()
    if not t:
        return False
    blocked = (
        "last run",
        "that run",
        "last race",
        "this run",
        "yesterday",
        "last week",
        "last sunday",
        "last monday",
        "on sunday",
        "on monday",
    )
    if any(b in t for b in blocked):
        return False
    phrases = (
        "how was my run",
        "how did my run go",
        "how did today go",
        "how was today",
        "how did today",
        "analyze my run",
    )
    return any(p in t for p in phrases)


def prefetch_opening_anchor_run_recap(
    session: Session,
    internal_user_id: str,
    anchor_local_date: str,
) -> Optional[Dict[str, Any]]:
    """
    Resolve exactly one Run on anchor_local_date and build get_run_summary payload.

    Returns None if disambiguation, no runs, errors, or invalid anchor.
    """
    from src.smartcoach_mobile_coach.agent_tools import (
        tool_find_runs_by_date,
        tool_get_run_summary,
    )

    ld = (anchor_local_date or "").strip()[:10]
    if len(ld) != 10:
        return None

    fr = tool_find_runs_by_date(session, internal_user_id, ld)
    if fr.get("error") or fr.get("no_runs") or fr.get("disambiguation_needed"):
        return None
    aid = fr.get("activity_id")
    if not isinstance(aid, int):
        return None

    summary = tool_get_run_summary(
        session,
        internal_user_id,
        aid,
        anchor_local_date=ld,
        include_peer_comparison=True,
        include_execution_kpis=True,
        include_hr_profile=True,
    )
    if summary.get("error"):
        return None

    return {"activity_id": aid, "find_runs_by_date": fr, "get_run_summary": summary}


def system_appendix_for_prefetch(
    prefetch: Dict[str, Any], anchor_local_date: str
) -> str:
    """Append to system prompt: JSON tool payloads + no-tools instruction."""
    ld = (anchor_local_date or "").strip()[:10]
    lines = [
        "",
        "## Pre-loaded run data (server-side)",
        f"The user is asking about their run on **{ld}** (device-local calendar day).",
        "Exact `find_runs_by_date` tool result:",
        "```json",
        json.dumps(prefetch["find_runs_by_date"], default=str),
        "```",
        "Exact `get_run_summary` tool result:",
        "```json",
        json.dumps(prefetch["get_run_summary"], default=str),
        "```",
        "**Do not call any tools** — all authoritative numbers are in the JSON above.",
        "Answer using the same coaching rules as when you had called those tools yourself "
        "(Insight + Facts; interpretation-first opener for this kind of question).",
    ]
    return "\n".join(lines)

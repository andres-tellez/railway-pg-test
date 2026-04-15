"""
Opening-turn fast path for "how was my run?" style questions.

Pre-fetches find_runs_by_date + get_run_summary server-side, then uses a single
OpenAI chat completion **without** tools so the model does not spend 2+ extra
round-trips deciding which tools to call.

Prefetch uses a **slim** get_run_summary (no peer comparison, no saved HR profile)
plus **compact** JSON in the system appendix (facts + training KPIs only) to
keep prompt tokens low. The API still returns the full prefetch summary for
RunSummaryCard fields (facts + training_kpis + drift bands).
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

    # Opening recap: skip peer tables + saved HR profile (large / slow). Keep execution
    # KPIs so RunSummaryCard drift row and coaching still have drift + Z2 signals.
    summary = tool_get_run_summary(
        session,
        internal_user_id,
        aid,
        anchor_local_date=ld,
        include_peer_comparison=False,
        include_execution_kpis=True,
        include_hr_profile=False,
    )
    if summary.get("error"):
        return None

    return {"activity_id": aid, "find_runs_by_date": fr, "get_run_summary": summary}


def _compact_run_context_for_llm(
    prefetch: Dict[str, Any], anchor_local_date: str
) -> Dict[str, Any]:
    """
    Minimal JSON for the fast-path system prompt: facts + KPI slice only.
    Full `get_run_summary` remains in prefetch for the structured API response / card.
    """
    summary = prefetch.get("get_run_summary") or {}
    facts = summary.get("facts") if isinstance(summary.get("facts"), dict) else {}
    kpis = summary.get("training_kpis")
    if kpis is not None and not isinstance(kpis, dict):
        kpis = None
    ld = (anchor_local_date or "").strip()[:10]
    out: Dict[str, Any] = {
        "anchor_local_date": ld,
        "activity_id": prefetch.get("activity_id"),
        "facts": facts,
    }
    if kpis:
        out["training_kpis"] = kpis
    if summary.get("is_easy_run") is not None:
        out["is_easy_run"] = summary.get("is_easy_run")
    zb = summary.get("zone_bounds")
    if isinstance(zb, dict) and zb:
        out["zone_bounds"] = zb
    zones = summary.get("hr_drift_band_zones")
    if zones is not None:
        out["hr_drift_band_zones"] = zones
    return out


def system_appendix_for_prefetch(
    prefetch: Dict[str, Any], anchor_local_date: str
) -> str:
    """Append compact run context JSON + no-tools instruction (minimal tokens)."""
    ld = (anchor_local_date or "").strip()[:10]
    compact = _compact_run_context_for_llm(prefetch, ld)
    lines = [
        "",
        "## Pre-loaded run data (server-side, compact)",
        f"The user is asking about their run on **{ld}** (device-local calendar day).",
        f"Resolved **activity_id** `{prefetch.get('activity_id')}` for that anchor day.",
        "Authoritative metrics for this turn (same source as `get_run_summary`, trimmed for speed):",
        "```json",
        json.dumps(compact, default=str),
        "```",
        "**Do not call any tools** — use only the JSON above for numbers.",
        "Answer using the same coaching rules as when you had called those tools yourself "
        "(Insight + Facts; interpretation-first opener for this kind of question).",
    ]
    return "\n".join(lines)

"""
Opening-turn fast path for "how was my run?" style questions.

Pre-fetches find_runs_by_date + get_run_summary server-side, then uses a single
OpenAI chat completion **without** tools so the model does not spend 2+ extra
round-trips deciding which tools to call.

Prefetch uses **get_run_summary** with execution KPIs for the **HTTP/card**
payload (RunSummaryCard drift row, etc.). The **LLM system appendix** uses a
**compact** JSON slice: by default **facts only** (session headline: distance,
pace, time, HR averages when present) so the opener does not anchor on drift /
Z2 / band KPIs. Set ``SMARTCOACH_RUN_RECAP_PREFETCH_SLIM=0`` to put
``training_kpis``, ``is_easy_run``, ``zone_bounds``, and
``hr_drift_band_zones`` back into the compact JSON (legacy behavior).
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


def _split_fastpath_enabled() -> bool:
    return os.getenv("SMARTCOACH_SPLIT_DETAIL_FASTPATH", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _run_recap_prefetch_slim_for_llm() -> bool:
    """
    When true (default), compact JSON for the recap fastpath omits execution
    KPIs / drift bands so the opener stays interpretation-first. Full
    ``get_run_summary`` remains in prefetch for structured API responses.
    """
    raw = (os.getenv("SMARTCOACH_RUN_RECAP_PREFETCH_SLIM") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


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
    # Opening message asks for KPI/drift detail: fastpath has no tools — use
    # the normal loop so get_run_summary can supply execution KPIs.
    if "drift" in t:
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


def wants_split_detail_fastpath(intent: str) -> bool:
    """Allow split-detail fast path when intent is already known."""
    if not _split_fastpath_enabled():
        return False
    return (intent or "").strip() == "split_detail"


def prefetch_split_detail(
    session: Session,
    internal_user_id: str,
    anchor_local_date: str,
    *,
    last_activity_id_hint: Optional[int] = None,
    thread_activity_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Resolve one run activity and prefetch split rows for single-call split detail replies.

    Resolution order:
    1) last_activity_id_hint (client/server hint from prior run_summary)
    2) thread_activity_id (derived from stored thread context)
    3) find_runs_by_date(anchor_local_date), only when exactly one run exists
    """
    from src.smartcoach_mobile_coach.agent_tools import (
        tool_find_runs_by_date,
        tool_get_run_splits,
    )

    ld = (anchor_local_date or "").strip()[:10]
    if len(ld) != 10:
        return None

    activity_id: Optional[int] = None
    resolved_from = "none"

    if isinstance(last_activity_id_hint, int) and last_activity_id_hint > 0:
        activity_id = int(last_activity_id_hint)
        resolved_from = "last_activity_id_hint"
    elif isinstance(thread_activity_id, int) and thread_activity_id > 0:
        activity_id = int(thread_activity_id)
        resolved_from = "thread_context"

    fr: Optional[Dict[str, Any]] = None
    if activity_id is None:
        fr = tool_find_runs_by_date(session, internal_user_id, ld)
        if fr.get("error") or fr.get("no_runs") or fr.get("disambiguation_needed"):
            return None
        raw_aid = fr.get("activity_id")
        if not isinstance(raw_aid, int):
            return None
        activity_id = raw_aid
        resolved_from = "find_runs_by_date"

    splits = tool_get_run_splits(session, internal_user_id, int(activity_id))
    if splits.get("error"):
        return None

    out: Dict[str, Any] = {
        "activity_id": int(activity_id),
        "resolved_from": resolved_from,
        "get_run_splits": splits,
    }
    if fr is not None:
        out["find_runs_by_date"] = fr
    return out


def _compact_run_context_for_llm(
    prefetch: Dict[str, Any], anchor_local_date: str
) -> Dict[str, Any]:
    """
    Minimal JSON for the fast-path system prompt.

    Default (slim): ``facts`` + ids/dates only — no execution KPI / drift slice
    in the appendix (full ``get_run_summary`` still in prefetch for the card).
    Legacy: set ``SMARTCOACH_RUN_RECAP_PREFETCH_SLIM=0`` to include KPIs and
    zone/drift bands in the compact JSON.
    """
    summary = prefetch.get("get_run_summary") or {}
    facts = summary.get("facts") if isinstance(summary.get("facts"), dict) else {}
    ld = (anchor_local_date or "").strip()[:10]
    out: Dict[str, Any] = {
        "anchor_local_date": ld,
        "activity_id": prefetch.get("activity_id"),
        "facts": facts,
    }
    if not _run_recap_prefetch_slim_for_llm():
        kpis = summary.get("training_kpis")
        if kpis is not None and not isinstance(kpis, dict):
            kpis = None
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


def _compact_split_context_for_llm(
    prefetch: Dict[str, Any], anchor_local_date: str
) -> Dict[str, Any]:
    """Minimal split payload for the split-detail fast path prompt."""
    splits_payload = prefetch.get("get_run_splits") or {}
    splits_rows = splits_payload.get("splits")
    if not isinstance(splits_rows, list):
        splits_rows = []
    ld = (anchor_local_date or "").strip()[:10]
    out: Dict[str, Any] = {
        "anchor_local_date": ld,
        "activity_id": prefetch.get("activity_id"),
        "title": splits_payload.get("title"),
        "splits_count": splits_payload.get("splits_count"),
        "splits_total_count": splits_payload.get("splits_total_count"),
        "splits_returned": splits_payload.get("splits_returned"),
        "splits_truncated": splits_payload.get("splits_truncated"),
        "splits": splits_rows,
        "scope": splits_payload.get("scope"),
    }
    if isinstance(splits_payload.get("splits_cap"), dict):
        out["splits_cap"] = splits_payload.get("splits_cap")
    return out


def system_appendix_for_prefetch(
    prefetch: Dict[str, Any], anchor_local_date: str
) -> str:
    """Append compact run context JSON + no-tools instruction (minimal tokens)."""
    ld = (anchor_local_date or "").strip()[:10]
    slim = _run_recap_prefetch_slim_for_llm()
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
    if slim:
        lines.extend(
            [
                "**This opener (slim pre-load):** The JSON has **session headline** fields under "
                "`facts` only (distance, pace, moving time, HR averages when present). "
                "**Do not** cite HR drift %, drift bands (green/yellow/orange/red), Z2 pace or "
                "adherence, `is_easy_run`, or zone thresholds — they are **omitted** here on purpose. "
                "Do **not** invent or guess those values. The next user turn uses the normal tool "
                "loop if they ask for drift/KPIs. **Ignore** any global instruction to “prefer HR drift” "
                "as a numeric anchor **for this reply** when those fields are absent from the JSON.",
            ]
        )
    return "\n".join(lines)


def system_appendix_for_split_prefetch(
    prefetch: Dict[str, Any], anchor_local_date: str
) -> str:
    """Append compact split data JSON + no-tools instruction."""
    ld = (anchor_local_date or "").strip()[:10]
    compact = _compact_split_context_for_llm(prefetch, ld)
    lines = [
        "",
        "## Pre-loaded split data (server-side, compact)",
        f"The user is asking for split detail on their run near **{ld}**.",
        f"Resolved **activity_id** `{prefetch.get('activity_id')}` via `{prefetch.get('resolved_from')}`.",
        "Authoritative per-lap rows for this turn (`get_run_splits` source):",
        "```json",
        json.dumps(compact, default=str),
        "```",
        "**Do not call any tools** — use only the JSON above for split rows and numbers.",
        "Answer with a short list/table of split rows when helpful plus a concise coaching read.",
        "Do not re-state session recap stats unless the user explicitly asks for recap.",
    ]
    return "\n".join(lines)

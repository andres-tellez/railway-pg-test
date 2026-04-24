"""
Anchor-day run recap fast path for "how was my run?" style questions.

Eligibility (phrase match, blocks, first user turn) lives in
``run_recap_policy.decide_run_recap_fastpath`` — see that module for reason codes
logged in orchestrator metadata.

Pre-fetches find_runs_by_date + get_run_summary server-side, optionally adds
**comparison_sessions** (prior days, facts-only, no KPIs) via
``run_recap_comparison_bundle``, and **week_volume_context** (this ISO week vs
last ISO week run count + miles via ``run_recap_week_volume_bundle``). When
``comparison_sessions`` is non-empty, the system appendix **requires** one
grounded day-to-day contrast from that JSON only. Then uses a single OpenAI chat completion
**without** tools so the model does not spend 2+ extra round-trips deciding
which tools to call.

Prefetch uses **get_run_summary** with execution KPIs for the **HTTP/card**
payload (structured run summary). The **LLM system appendix** uses a
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

from src.smartcoach_mobile_coach.dialogue_manager import INTENT_SPLIT_DETAIL
from src.smartcoach_mobile_coach.run_recap_comparison_bundle import (
    build_comparison_sessions_facts_only,
    run_recap_comparison_bundle_enabled,
)
from src.smartcoach_mobile_coach.run_recap_policy import decide_run_recap_fastpath
from src.smartcoach_mobile_coach.run_recap_week_volume_bundle import (
    build_week_volume_context_for_llm,
    run_recap_week_volume_bundle_enabled,
)


def run_recap_fastpath_retry_on_empty_enabled() -> bool:
    """Second completion when the first fastpath reply is empty (saves full tool loop)."""
    return (
        os.getenv("SMARTCOACH_RUN_RECAP_FASTPATH_RETRY", "1")
    ).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


# Appended to system on empty first completion only.
RUN_RECAP_FASTPATH_RETRY_APPENDIX = (
    "\n\n## Required output\n"
    "Your previous attempt produced no text. Reply with **2–4 sentences** of coaching "
    "about this run using only the pre-loaded JSON. **Do not** leave the reply empty."
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


def wants_run_recap_fastpath(
    user_message: str,
    conversation_history: List[Dict[str, str]],
    anchor_local_date: str = "",
) -> bool:
    """
    Anchor-day run recap fastpath gate.

    Delegates to :func:`run_recap_policy.decide_run_recap_fastpath` (phrase
    match, safety blocks, first user turn in thread). Pass ``anchor_local_date``
    (YYYY-MM-DD) so questions that name **yesterday** can resolve the run day.
    """
    return decide_run_recap_fastpath(
        user_message, conversation_history, anchor_local_date
    ).eligible


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
    # KPIs in the structured payload for the app card / continuity.
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

    comparison_for_llm: List[Dict[str, Any]] = []
    if run_recap_comparison_bundle_enabled():
        comparison_for_llm = build_comparison_sessions_facts_only(
            session,
            internal_user_id,
            ld,
            exclude_activity_id=aid,
        )

    week_volume_for_llm: Optional[Dict[str, Any]] = None
    if run_recap_week_volume_bundle_enabled():
        week_volume_for_llm = build_week_volume_context_for_llm(
            session, internal_user_id, ld
        )

    return {
        "activity_id": aid,
        "find_runs_by_date": fr,
        "get_run_summary": summary,
        "comparison_for_llm": comparison_for_llm,
        "week_volume_for_llm": week_volume_for_llm,
    }


def wants_split_detail_fastpath(intent: str) -> bool:
    """Allow split-detail fast path when intent is already known."""
    if not _split_fastpath_enabled():
        return False
    return (intent or "").strip() == INTENT_SPLIT_DETAIL


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
    comp = prefetch.get("comparison_for_llm")
    if isinstance(comp, list) and comp:
        out["comparison_sessions"] = comp
    wv = prefetch.get("week_volume_for_llm")
    if isinstance(wv, dict) and wv.get("this_week") and wv.get("last_week"):
        out["week_volume_context"] = {
            "scope": wv.get("scope"),
            "anchor_local_date": wv.get("anchor_local_date"),
            "this_week": wv.get("this_week"),
            "last_week": wv.get("last_week"),
        }
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
    prefetch: Dict[str, Any],
    recap_run_local_date: str,
    *,
    prose_anchor_day: str = "today",
) -> str:
    """Append compact run context JSON + no-tools instruction (minimal tokens)."""
    ld = (recap_run_local_date or "").strip()[:10]
    day = (prose_anchor_day or "today").strip().lower()
    if day not in ("today", "yesterday"):
        day = "today"
    poss = "today's" if day == "today" else "yesterday's"
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
        "**Layout (mobile):** The app shows the **RunSummaryCard** (from anchor `facts`) **above** your "
        "Markdown. Your **`content` must not repeat** distance, duration, avg pace, avg/max HR, or any "
        "other headline stat on that card — even paraphrased. Use **`content`** only for **learning**: "
        "kudos, watch-out, or a non-obvious contrast **when** `comparison_sessions`, KPI fields in JSON, "
        "or optional week-volume context justify it. If you ask a follow-up question, put it **after** "
        "a blank line (paragraph break) following the learning block.",
        f"**User-facing dates:** In prose to the athlete, say **{day}** for the anchor run — **never** "
        "read out `anchor_local_date`, `calendar_local_date`, or `week_monday` as YYYY-MM-DD or "
        "numeric slash dates. Use `when_vs_anchor` for prior single-run days and `spoken_timeframe` "
        "for week volume rows.",
    ]
    if slim:
        lines.extend(
            [
                "**This opener (slim pre-load):** Anchor `facts` in the JSON populate the **card only** — "
                "your **`content` must not quote** distance, pace, moving time, or HR averages from `facts`. "
                "**Do not** cite HR drift %, drift bands, Z2 pace or adherence, `is_easy_run`, or zone "
                "thresholds — they are **omitted** here on purpose. Do **not** invent them. The next user "
                "turn uses the normal tool loop if they ask for drift/KPIs. **Ignore** any global instruction "
                "to “prefer HR drift” **for this reply** when those fields are absent from the JSON.",
            ]
        )
    if compact.get("week_volume_context"):
        lines.extend(
            [
                "**Week volume (`week_volume_context`):** Compare **`this_week`** vs **`last_week`** "
                "using **only** `run_count`, `total_mi_display`, and each row’s **`spoken_timeframe`** "
                "(say “this week” / “last week” — **not** `week_monday` in the reply). **Optional:** "
                f"add **at most one** short clause **only** if it surfaces something **non-obvious** "
                f"(e.g. a sharp load swing the athlete might not already feel from the app). If the "
                f"delta is routine, **omit** week volume entirely — do not recap totals for their own sake. "
                "**Do not** invent other weekly stats, KPIs, or trends not in this JSON.",
            ]
        )
    if compact.get("comparison_sessions"):
        lines.extend(
            [
                "**Optional — `comparison_sessions`:** Each item is a **prior** calendar day (before "
                "the anchor) with **exactly one** run — **headline facts only** (no KPIs). You **may** "
                f"add **at most one** short contrast sentence vs **{poss}** run **only** if it surfaces "
                "something **non-obvious** (pace/HR/distance shift the athlete might not notice vs a "
                "same-type easy day). If the contrast is trivial or repeats what they already see on "
                "the card, **omit**. Use **only** fields present in the JSON for anchor `facts` and that "
                "item. When you name that prior day in prose, use **`when_vs_anchor`** — **never** quote "
                "`calendar_local_date` or ISO dates to the user. Avoid sweeping claims (“you’re clearly "
                "improving”) unless the numbers plainly support it. **Do not** invent runs, dates, or "
                "numbers outside this JSON.",
            ]
        )
    else:
        lines.append(
            "**Prior-run contrast:** The JSON has **no** `comparison_sessions` — do **not** describe "
            f"another **specific day's** run from memory. Do **not** restate anchor `facts` headline "
            f"metrics in `content` (the card shows them). `week_volume_context`: only under the optional "
            "non-obvious rule above."
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

"""
KPI-free comparison context for anchor-day run recap fastpath.

Looks back a few calendar days before the anchor date, finds days with exactly
one run, and loads ``get_run_summary`` with **execution KPIs off** so the LLM
appendix can include grounded pace/HR/distance contrasts without drift/Z2
payloads (insight cache may still hold full rows — we only expose trimmed facts).
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

_FACT_KEYS_FOR_COMPARISON = (
    "title",
    "local_date",
    "distance_display",
    "moving_time_display",
    "avg_pace_display",
    "avg_heart_rate_display",
    "max_heart_rate_display",
    "start_time_utc_iso",
)


def run_recap_comparison_bundle_enabled() -> bool:
    raw = (os.getenv("SMARTCOACH_RUN_RECAP_COMPARISON_BUNDLE") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def comparison_lookback_days() -> int:
    try:
        v = int(os.getenv("SMARTCOACH_RUN_RECAP_COMPARISON_LOOKBACK_DAYS", "7"))
    except ValueError:
        v = 7
    return max(1, min(v, 21))


def comparison_max_sessions() -> int:
    try:
        v = int(os.getenv("SMARTCOACH_RUN_RECAP_COMPARISON_MAX", "2"))
    except ValueError:
        v = 2
    return max(1, min(v, 3))


def _parse_anchor_date(anchor_local_date: str) -> Optional[date]:
    ld = (anchor_local_date or "").strip()[:10]
    if len(ld) != 10:
        return None
    try:
        return datetime.strptime(ld, "%Y-%m-%d").date()
    except ValueError:
        return None


def _trim_facts_for_comparison(facts: Any) -> Dict[str, Any]:
    if not isinstance(facts, dict):
        return {}
    out: Dict[str, Any] = {}
    for k in _FACT_KEYS_FOR_COMPARISON:
        v = facts.get(k)
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        out[k] = v
    return out


def build_comparison_sessions_facts_only(
    session: Session,
    internal_user_id: str,
    anchor_local_date: str,
    *,
    exclude_activity_id: int,
) -> List[Dict[str, Any]]:
    """
    Return up to ``comparison_max_sessions()`` prior single-run days before anchor.

    Each entry: ``calendar_local_date``, ``activity_id``, ``facts`` (trimmed).
    """
    from src.smartcoach_mobile_coach.agent_tools import (
        tool_find_runs_by_date,
        tool_get_run_summary,
    )

    anchor = _parse_anchor_date(anchor_local_date)
    if anchor is None:
        return []

    max_sessions = comparison_max_sessions()
    lookback = comparison_lookback_days()
    out: List[Dict[str, Any]] = []

    for offset in range(1, lookback + 1):
        if len(out) >= max_sessions:
            break
        day = anchor - timedelta(days=offset)
        ds = day.isoformat()
        fr = tool_find_runs_by_date(session, internal_user_id, ds)
        if fr.get("error") or fr.get("no_runs") or fr.get("disambiguation_needed"):
            continue
        aid = fr.get("activity_id")
        if not isinstance(aid, int) or aid <= 0:
            continue
        if aid == exclude_activity_id:
            continue

        summary = tool_get_run_summary(
            session,
            internal_user_id,
            aid,
            anchor_local_date=ds,
            include_peer_comparison=False,
            include_execution_kpis=False,
            include_hr_profile=False,
        )
        if summary.get("error"):
            continue
        facts = _trim_facts_for_comparison(summary.get("facts"))
        if not facts:
            continue

        out.append(
            {
                "calendar_local_date": ds,
                "activity_id": aid,
                "facts": facts,
            }
        )

    return out

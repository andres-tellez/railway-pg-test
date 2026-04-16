"""
This ISO week vs last ISO week volume for run recap fastpath.

Uses ``tool_aggregate_runs_in_range`` over a 14-day window (last week's Monday
through this week's Sunday) and maps ``weekly_summaries`` to **this_week** /
**last_week** only — ``run_count`` and ``total_mi_display`` (no KPIs). Weeks
with no runs appear as zeros (summary rows are absent from SQL GROUP BY).
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.smartcoach_mobile_coach.display_format import format_distance_mi


def run_recap_week_volume_bundle_enabled() -> bool:
    raw = (os.getenv("SMARTCOACH_RUN_RECAP_WEEK_VOLUME_BUNDLE") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _parse_anchor_date(anchor_local_date: str) -> Optional[date]:
    ld = (anchor_local_date or "").strip()[:10]
    if len(ld) != 10:
        return None
    try:
        return datetime.strptime(ld, "%Y-%m-%d").date()
    except ValueError:
        return None


def _week_label_for_monday(monday: date) -> str:
    return f"Week of {monday.month}/{monday.day}"


def build_week_volume_context_for_llm(
    session: Session,
    internal_user_id: str,
    anchor_local_date: str,
) -> Optional[Dict[str, Any]]:
    """
    Return slim ``this_week`` / ``last_week`` dicts for the LLM, or None on error.

    Weeks are ISO Monday–Sunday in **activity local calendar date** space, aligned
    with ``aggregate_runs_in_range`` / ``weekly_summaries_scope``.
    """
    from src.smartcoach_mobile_coach.agent_tools import tool_aggregate_runs_in_range

    anchor = _parse_anchor_date(anchor_local_date)
    if anchor is None:
        return None

    this_week_monday = anchor - timedelta(days=anchor.weekday())
    this_week_sunday = this_week_monday + timedelta(days=6)
    last_week_monday = this_week_monday - timedelta(days=7)

    agg = tool_aggregate_runs_in_range(
        session,
        internal_user_id,
        start_date_from=last_week_monday,
        start_date_to=this_week_sunday,
    )
    if agg.get("error"):
        return None

    rows = agg.get("weekly_summaries") or []
    by_monday: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        wm = row.get("week_monday")
        if isinstance(wm, str) and len(wm) >= 10:
            by_monday[wm[:10]] = row

    def pack(mon: date) -> Dict[str, Any]:
        iso = mon.isoformat()
        r = by_monday.get(iso)
        if not r:
            return {
                "week_monday": iso,
                "week_label": _week_label_for_monday(mon),
                "run_count": 0,
                "total_mi_display": format_distance_mi(0.0),
            }
        mi_disp = r.get("total_mi_display")
        if not isinstance(mi_disp, str) or not mi_disp.strip():
            try:
                miles = float(r.get("total_distance_miles", 0) or 0.0)
            except (TypeError, ValueError):
                miles = 0.0
            mi_disp = format_distance_mi(miles)
        wl = r.get("week_label")
        if not isinstance(wl, str) or not wl.strip():
            wl = _week_label_for_monday(mon)
        return {
            "week_monday": iso,
            "week_label": wl.strip(),
            "run_count": int(r.get("run_count") or 0),
            "total_mi_display": mi_disp.strip(),
        }

    ld = anchor_local_date.strip()[:10]
    return {
        "scope": (
            "ISO weeks Monday–Sunday; each activity counted on its **local calendar day** "
            "(same basis as `aggregate_runs_in_range` weekly_summaries)."
        ),
        "anchor_local_date": ld,
        "this_week": pack(this_week_monday),
        "last_week": pack(last_week_monday),
    }

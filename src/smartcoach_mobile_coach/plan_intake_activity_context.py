"""
Plan-intake activity snapshot for coach prompts.

Loads the same Strava-backed run window used by plan generation (Layer 1) so the
model sees weekly volume / long-run hints during intake—without extra tool calls
when plan_creation_mode restricts tools to intake only.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.services.training_plan.data_collection_service import DataCollectionService


def _lookback_weeks_from_env() -> int:
    raw = (os.getenv("SMARTCOACH_PLAN_INTAKE_ACTIVITY_WEEKS") or "12").strip()
    try:
        w = int(raw)
    except ValueError:
        w = 12
    return max(4, min(w, 24))


def compute_plan_intake_activity_summary(
    session: Session,
    internal_user_id: str,
    *,
    lookback_weeks: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Return a small dict of facts from DB runs (type Run) in the lookback window.

    ``activities_found == 0`` means no ingested runs in that window (Strava empty
    or not linked)—not a judgment about account link state.
    """
    w = lookback_weeks if lookback_weeks is not None else _lookback_weeks_from_env()
    activities: List[Dict[str, Any]] = DataCollectionService.fetch_strava_activities(
        session, str(internal_user_id), weeks=w
    )
    n = len(activities)
    total_miles = 0.0
    for a in activities:
        try:
            total_miles += float(a.get("distance") or 0.0)
        except (TypeError, ValueError):
            continue
    avg_week = (total_miles / float(w)) if w else 0.0
    longest_miles = 0.0
    longest_date: Optional[str] = None
    if activities:
        best = max(
            activities,
            key=lambda x: float(x.get("distance") or 0.0),
        )
        try:
            longest_miles = float(best.get("distance") or 0.0)
        except (TypeError, ValueError):
            longest_miles = 0.0
        ld = best.get("date")
        longest_date = str(ld) if ld else None
    latest_date: Optional[str] = None
    if activities:
        d0 = activities[0].get("date")
        latest_date = str(d0) if d0 else None
    return {
        "lookback_weeks": w,
        "activities_found": n,
        "has_running_data": n > 0,
        "total_miles_window": round(total_miles, 1),
        "avg_miles_per_week_approx": round(avg_week, 1),
        "longest_run_miles": round(longest_miles, 1) if longest_miles else 0.0,
        "longest_run_date": longest_date,
        "latest_run_date": latest_date,
    }


def format_plan_intake_activity_context_block(summary: Dict[str, Any]) -> str:
    """Markdown system section: rules + numbers (no user-facing quiz)."""
    w = int(summary.get("lookback_weeks") or 12)
    n = int(summary.get("activities_found") or 0)
    has = bool(summary.get("has_running_data"))
    total = summary.get("total_miles_window")
    avg = summary.get("avg_miles_per_week_approx")
    long_mi = summary.get("longest_run_miles")
    long_dt = summary.get("longest_run_date") or "—"
    latest = summary.get("latest_run_date") or "—"

    lines = [
        "## Athlete activity snapshot (server — do not read aloud as a survey)",
        f"- **Lookback:** last **{w}** weeks of **Run** activities stored for this user (same family of data plan generation uses).",
        f"- **Runs in window:** **{n}**",
    ]
    if has:
        lines.extend(
            [
                f"- **Total miles (window):** ~**{total}** mi",
                f"- **Approx. average per week** (total ÷ {w}): ~**{avg}** mi/wk",
                f"- **Longest single run in window:** **{long_mi}** mi on **{long_dt}**",
                f"- **Most recent run date:** **{latest}**",
                "",
                "### Coaching rules for plan intake",
                "- **Do not** ask for self-reported weekly mileage, years running, or generic “experience level” — "
                "baseline for the plan comes from this snapshot + generation-time tools.",
                "- Ask only the structured plan fields: **race distance**, **race date**, optional **race name**, "
                "**primary goal** (Just Finish vs Target Time + **target time** when needed), **training days**.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "### Coaching rules for plan intake (no runs in this window)",
                "- There are **no** stored runs in this lookback — the server has little volume signal yet.",
                "- You **may** ask **one** short, respectful question whether they also run **outside Strava** "
                "(other apps, treadmill-only, etc.) so we can gauge fitness; then merge any free-text detail into "
                "`update_plan_intake` `notes` if useful.",
                "- Do **not** run a long interview; still collect the same structured fields (race distance, date, goal, training days).",
            ]
        )
    return "\n".join(lines)


def build_plan_intake_activity_context_block(
    session: Session,
    internal_user_id: str,
) -> str:
    summary = compute_plan_intake_activity_summary(session, internal_user_id)
    return format_plan_intake_activity_context_block(summary)

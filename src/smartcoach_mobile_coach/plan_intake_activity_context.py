"""
Plan-intake activity snapshot for coach prompts.

Loads the same Strava-backed run window used by plan generation (Layer 1) so the
model sees weekly volume / long-run hints during intake—without extra tool calls
when plan_creation_mode restricts tools to intake only.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.services.training_plan.data_collection_service import DataCollectionService


def _lookback_weeks_from_env() -> int:
    raw = (os.getenv("SMARTCOACH_PLAN_INTAKE_ACTIVITY_WEEKS") or "6").strip()
    try:
        w = int(raw)
    except ValueError:
        w = 6
    return max(4, min(w, 24))


def _parse_activity_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d")
        except ValueError:
            return None


def _weekly_mileage_stats(
    activities: List[Dict[str, Any]], lookback_weeks: int
) -> Dict[str, Any]:
    weekly = [0.0 for _ in range(max(lookback_weeks, 1))]
    dated: List[tuple[datetime, float]] = []
    for a in activities:
        dt = _parse_activity_date(a.get("date"))
        if dt is None:
            continue
        try:
            miles = float(a.get("distance") or 0.0)
        except (TypeError, ValueError):
            miles = 0.0
        dated.append((dt, miles))
    if dated:
        latest_dt = max(dt for dt, _ in dated)
        for dt, miles in dated:
            idx = min(max((latest_dt.date() - dt.date()).days // 7, 0), len(weekly) - 1)
            weekly[idx] += miles
    active_weeks = [m for m in weekly if m > 0]
    return {
        "weekly_miles": [round(m, 1) for m in weekly],
        "active_weeks": len(active_weeks),
        "weekly_miles_min_active": round(min(active_weeks), 1) if active_weeks else 0.0,
        "weekly_miles_max_active": round(max(active_weeks), 1) if active_weeks else 0.0,
    }


def _effort_control_summary(activities: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {"too_hard": 0, "too_easy": 0, "on_target": 0}
    for a in activities:
        raw = a.get("deviation_direction")
        if raw in counts:
            counts[str(raw)] += 1
    total = sum(counts.values())
    dominant: Optional[str] = None
    if total >= 4:
        dominant_key = max(counts, key=lambda k: counts[k])
        if counts[dominant_key] / float(total) >= 0.5:
            dominant = dominant_key
    return {
        "effort_signal_runs": total,
        "deviation_direction_distribution": counts,
        "dominant_deviation_direction": dominant,
        "has_effort_control_signal": dominant is not None,
    }


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
    weekly_stats = _weekly_mileage_stats(activities, w)
    effort_stats = _effort_control_summary(activities)
    return {
        "lookback_weeks": w,
        "activities_found": n,
        "has_running_data": n > 0,
        "total_miles_window": round(total_miles, 1),
        "avg_miles_per_week_approx": round(avg_week, 1),
        "longest_run_miles": round(longest_miles, 1) if longest_miles else 0.0,
        "longest_run_date": longest_date,
        "latest_run_date": latest_date,
        "runs_per_week_approx": round(n / float(w), 1) if w else 0.0,
        **weekly_stats,
        **effort_stats,
    }


def format_plan_intake_activity_context_block(summary: Dict[str, Any]) -> str:
    """Markdown system section: rules + numbers (no user-facing quiz)."""
    w = int(summary.get("lookback_weeks") or 6)
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
                "- First make the runner feel understood in brief coach language, then ask natural questions that map "
                "to the structured fields: **race distance**, **race date**, optional **race name**, "
                "**primary goal** (Just Finish vs Target Time + **target time** when needed), **training days**.",
                "- Mention effort control only when `has_effort_control_signal=true`; otherwise omit it or keep phrasing generic.",
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


def _mileage_band_phrase(value: float) -> str:
    n = int(round(value))
    if n <= 0:
        return "very light mileage"
    if n < 10:
        return "single-digit mileage"
    if n < 15:
        return "low-teens mileage"
    if n < 20:
        return "mid-to-high teens mileage"
    if n < 25:
        return "low-20s mileage"
    if n < 30:
        return "mid-to-high 20s mileage"
    if n < 35:
        return "low-30s mileage"
    if n < 45:
        return "solid 30s to low-40s mileage"
    return "strong weekly mileage"


def _volume_phrase(summary: Dict[str, Any], *, include_long_run_number: bool) -> str:
    min_week = float(summary.get("weekly_miles_min_active") or 0.0)
    max_week = float(summary.get("weekly_miles_max_active") or 0.0)
    avg = float(summary.get("avg_miles_per_week_approx") or 0.0)
    if (
        not include_long_run_number
        and min_week > 0
        and max_week > 0
        and (max_week - min_week) >= 6
    ):
        return f"around **{round(min_week / 5) * 5:.0f}–{round(max_week / 5) * 5:.0f} miles per week**"
    if include_long_run_number and avg > 0:
        return f"around **{round(avg / 5) * 5:.0f} miles per week**"
    return _mileage_band_phrase(avg)


def format_user_visible_activity_overview(summary: Dict[str, Any]) -> str:
    """
    Short, coach-voice markdown for the chat transcript: what synced runs show.

    Returns a brief no-data transition when there are no runs in the lookback window.
    """
    if not summary.get("has_running_data"):
        return (
            "I don’t have enough recent running data synced to judge your current base yet, "
            "so I’ll guide this with a few quick questions."
        )
    active_weeks = int(summary.get("active_weeks") or 0)
    long_mi = summary.get("longest_run_miles")
    include_long_run_number = bool(long_mi)
    volume_phrase = _volume_phrase(
        summary, include_long_run_number=include_long_run_number
    )

    lines = [
        f"Here’s what I’m seeing from your recent training: you’ve been running {volume_phrase} with solid consistency.",
    ]
    if long_mi:
        lines.append(
            f"Your long run is around **{float(long_mi):.0f} miles**, which gives us a useful base to build from."
        )
    elif active_weeks:
        lines.append(
            "You’ve got recent consistency, so we can shape the plan from your current rhythm."
        )

    dominant = summary.get("dominant_deviation_direction")
    if summary.get("has_effort_control_signal") and dominant == "too_hard":
        lines.append(
            "The main opportunity is effort control, so the easy days stay easy enough to support the bigger work."
        )
    elif summary.get("has_effort_control_signal") and dominant == "on_target":
        lines.append(
            "The opportunity is turning that control into a clearer progression toward the race."
        )
    else:
        lines.append(
            "The opportunity is adding structure so that consistency turns into race-specific progress."
        )
    return "\n".join(lines)


def apply_plan_activity_preamble_to_assistant_markdown(
    content: str,
    *,
    plan_creation_mode: bool,
    activity_summary: Optional[Dict[str, Any]],
    runner_understanding_already_shown: bool,
) -> str:
    """
    Prepend the one-time activity overview in plan-creation turns when we have run data.
    """
    if not plan_creation_mode or not activity_summary:
        return content
    if runner_understanding_already_shown:
        return content
    overview = format_user_visible_activity_overview(activity_summary).strip()
    if not overview:
        return content
    base = (content or "").strip()
    return f"{overview}\n\n{base}" if base else overview


def build_plan_intake_activity_context_block(
    session: Session,
    internal_user_id: str,
) -> str:
    summary = compute_plan_intake_activity_summary(session, internal_user_id)
    return format_plan_intake_activity_context_block(summary)

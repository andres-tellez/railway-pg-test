"""
Plan-intake activity snapshot for coach prompts.

Loads the same Strava-backed run window used by plan generation (Layer 1) so the
model sees weekly volume / long-run hints during intake—without extra tool calls
when plan_creation_mode restricts tools to intake only.
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from src.coaching_intelligence.contracts.runner_evidence import RunnerEvidenceSummary
from src.services.training_plan.data_collection_service import DataCollectionService


def parse_anchor_local_date_yyyy_mm_dd(raw: Optional[str]) -> Optional[date]:
    """Parse mobile ``YYYY-MM-DD`` device anchor; used for ISO week boundaries."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.strptime(raw.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _lookback_weeks_from_env() -> int:
    raw = (os.getenv("SMARTCOACH_PLAN_INTAKE_ACTIVITY_WEEKS") or "6").strip()
    try:
        w = int(raw)
    except ValueError:
        w = 6
    return max(4, min(w, 24))


def _history_lookback_weeks_from_env() -> int:
    raw = (os.getenv("SMARTCOACH_PLAN_INTAKE_HISTORY_WEEKS") or "12").strip()
    try:
        w = int(raw)
    except ValueError:
        w = 12
    return max(6, min(w, 52))


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


def _filter_activities_to_lookback(
    activities: List[Dict[str, Any]],
    *,
    anchor_date: date,
    lookback_weeks: int,
) -> List[Dict[str, Any]]:
    """Keep runs on or after ``anchor_date - lookback_weeks * 7 days``."""
    if lookback_weeks <= 0:
        return []
    cutoff = anchor_date - timedelta(days=lookback_weeks * 7)
    out: List[Dict[str, Any]] = []
    for a in activities:
        dt = _parse_activity_date(a.get("date"))
        if dt is None:
            continue
        if dt.date() >= cutoff:
            out.append(a)
    return out


def _weekly_mileage_history_for_calendar_weeks(
    activities: List[Dict[str, Any]],
    *,
    anchor_date: date,
    history_weeks: int,
) -> tuple[List[Dict[str, Any]], int]:
    """
    ``history_weeks`` ISO weeks (Mon start), ending in the week that contains ``anchor_date``.
    Returns (payload oldest-first, count of weeks with miles > 0).
    """
    this_monday = _monday_of_calendar_week(anchor_date)
    rows: List[Dict[str, Any]] = []
    active_weeks = 0
    for k in range(history_weeks - 1, -1, -1):
        week_start = this_monday - timedelta(weeks=k)
        week_end = week_start + timedelta(days=7)
        miles = 0.0
        for a in activities:
            dt = _parse_activity_date(a.get("date"))
            if dt is None:
                continue
            d = dt.date()
            if week_start <= d < week_end:
                try:
                    miles += float(a.get("distance") or 0.0)
                except (TypeError, ValueError):
                    pass
        rounded = round(miles, 1)
        rows.append({"week_start": week_start.isoformat(), "miles": rounded})
        if rounded > 0:
            active_weeks += 1
    return rows, active_weeks


_EVIDENCE_HISTORY_ONLY_KEYS = frozenset(
    {
        "weekly_mileage_history",
        "consistency_weeks_active_in_history",
        "history_lookback_weeks",
    }
)


def strip_runner_evidence_to_activity_summary(
    evidence_api: Dict[str, Any]
) -> Dict[str, Any]:
    """Drop Wave 3 history-only keys so ``activity_summary`` matches pre-Wave 3 shape."""
    return {
        k: v
        for k, v in evidence_api.items()
        if k != "schema_version" and k not in _EVIDENCE_HISTORY_ONLY_KEYS
    }


def _compute_plan_intake_activity_summary_from_activities(
    activities: List[Dict[str, Any]],
    *,
    lookback_weeks: int,
    anchor_local_date: date,
) -> Dict[str, Any]:
    w = lookback_weeks
    anchor = anchor_local_date
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
    perf_lr_stats = _performance_and_long_run_signals(
        activities, anchor_date=anchor, lookback_weeks=w
    )
    cal_stats = _calendar_week_volume_stats(activities, anchor_date=anchor)
    completed_n = int(cal_stats.get("completed_calendar_weeks_count") or 0)
    avg_primary = (
        float(cal_stats.get("avg_miles_completed_calendar_weeks") or 0.0)
        if completed_n > 0
        else avg_week
    )
    if completed_n > 0:
        weekly_stats["weekly_miles_min_active"] = float(
            cal_stats.get("weekly_miles_min_completed") or 0.0
        )
        weekly_stats["weekly_miles_max_active"] = float(
            cal_stats.get("weekly_miles_max_completed") or 0.0
        )

    return {
        "lookback_weeks": w,
        "activities_found": n,
        "has_running_data": n > 0,
        "total_miles_window": round(total_miles, 1),
        "avg_miles_per_week_raw_window": round(avg_week, 1),
        "avg_miles_per_week_approx": round(avg_primary, 1),
        "longest_run_miles": round(longest_miles, 1) if longest_miles else 0.0,
        "longest_run_date": longest_date,
        "latest_run_date": latest_date,
        "runs_per_week_approx": round(n / float(w), 1) if w else 0.0,
        **cal_stats,
        **weekly_stats,
        **effort_stats,
        **perf_lr_stats,
    }


def _monday_of_calendar_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _calendar_week_volume_stats(
    activities: List[Dict[str, Any]],
    *,
    anchor_date: date,
) -> Dict[str, Any]:
    """
    Group miles by ISO weeks (Monday start). Baseline excludes the **current**
    calendar week (the week containing ``anchor_date``), so partial in-progress
    weeks do not drag the typical-week number down (trust UX).
    """
    totals: Dict[date, float] = defaultdict(float)
    for a in activities:
        dt = _parse_activity_date(a.get("date"))
        if dt is None:
            continue
        d = dt.date()
        try:
            miles = float(a.get("distance") or 0.0)
        except (TypeError, ValueError):
            miles = 0.0
        totals[_monday_of_calendar_week(d)] += miles

    this_monday = _monday_of_calendar_week(anchor_date)
    completed_totals = [totals[m] for m in totals if m < this_monday]
    avg_completed = (
        sum(completed_totals) / float(len(completed_totals))
        if completed_totals
        else 0.0
    )
    min_c = min(completed_totals) if completed_totals else 0.0
    max_c = max(completed_totals) if completed_totals else 0.0
    current_partial = float(totals.get(this_monday, 0.0))

    return {
        "calendar_anchor_date": anchor_date.isoformat(),
        "current_calendar_week_monday": this_monday.isoformat(),
        "current_calendar_week_miles_partial": round(current_partial, 1),
        "completed_calendar_weeks_count": len(completed_totals),
        "avg_miles_completed_calendar_weeks": round(avg_completed, 1),
        "weekly_miles_min_completed": round(min_c, 1),
        "weekly_miles_max_completed": round(max_c, 1),
    }


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


_MIN_MOVING_TIME_SEC_FOR_PACE = 20 * 60
_MIN_DISTANCE_MI_PACE_SAMPLE = 3.0
_MIN_DISTANCE_MI_SUSTAINED = 8.0
_LONG_RUN_GEOFENCE_MI = 10.0
_LONG_RUN_12_MI = 12.0


def _pace_sec_per_mile(distance_mi: float, moving_time_s: int) -> Optional[float]:
    if distance_mi <= 0 or moving_time_s <= 0:
        return None
    return float(moving_time_s) / float(distance_mi)


def _median_float(values: List[float]) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return (float(s[mid - 1]) + float(s[mid])) / 2.0


def _performance_and_long_run_signals(
    activities: List[Dict[str, Any]],
    *,
    anchor_date: date,
    lookback_weeks: int,
) -> Dict[str, Any]:
    """
    P0/P2 deterministic signals for readiness — pace proxies, reliability, long-run pattern.

    Pace is **observational** (Strava distance + moving time), not a physiology model.
    """
    empty = {
        "pace_reliability": "none",
        "runs_usable_pace_count": 0,
        "typical_easy_pace_sec_per_mi": None,
        "best_sustained_endurance_pace_sec_per_mi": None,
        "hr_coverage_ratio": None,
        "long_runs_ge_10_mi_count": 0,
        "long_runs_ge_12_mi_count": 0,
        "weeks_with_long_run_10plus": 0,
        "long_run_progression_trend": "unknown",
    }
    if not activities or lookback_weeks <= 0:
        return dict(empty)

    max_dist = 0.0
    dated_rows: List[tuple[date, float, int]] = []
    usable_paces: List[float] = []
    sustained_paces: List[float] = []

    for a in activities:
        try:
            d_mi = float(a.get("distance") or 0.0)
        except (TypeError, ValueError):
            continue
        try:
            mt = int(a.get("moving_time") or 0)
        except (TypeError, ValueError):
            mt = 0
        dt = _parse_activity_date(a.get("date"))
        if dt is None:
            continue
        d_only = dt.date()
        pace = _pace_sec_per_mile(d_mi, mt)
        dated_rows.append((d_only, d_mi, mt))
        max_dist = max(max_dist, d_mi)
        if (
            pace is not None
            and mt >= _MIN_MOVING_TIME_SEC_FOR_PACE
            and d_mi >= _MIN_DISTANCE_MI_PACE_SAMPLE
        ):
            usable_paces.append(pace)
            if d_mi >= _MIN_DISTANCE_MI_SUSTAINED:
                sustained_paces.append(pace)

    easy_threshold = max(6.0, max_dist * 0.88) if max_dist > 0 else 6.0
    easy_paces: List[float] = []
    for a in activities:
        try:
            d_mi = float(a.get("distance") or 0.0)
        except (TypeError, ValueError):
            continue
        try:
            mt = int(a.get("moving_time") or 0)
        except (TypeError, ValueError):
            mt = 0
        pace = _pace_sec_per_mile(d_mi, mt)
        if (
            pace is not None
            and mt >= _MIN_MOVING_TIME_SEC_FOR_PACE
            and d_mi >= _MIN_DISTANCE_MI_PACE_SAMPLE
            and d_mi <= easy_threshold
        ):
            easy_paces.append(pace)

    typical_easy = (
        _median_float(easy_paces) if easy_paces else _median_float(usable_paces)
    )
    best_sustained = min(sustained_paces) if sustained_paces else None

    n_pace = len(usable_paces)
    if n_pace < 3:
        pace_rel = "none"
    elif n_pace < 5:
        pace_rel = "low"
    elif n_pace < 12:
        pace_rel = "medium"
    else:
        pace_rel = "high"

    hr_n = 0
    for a in activities:
        hr = a.get("average_heartrate")
        if hr is None:
            continue
        try:
            float(hr)
        except (TypeError, ValueError):
            continue
        hr_n += 1
    hr_ratio = hr_n / float(len(activities)) if activities else None

    n10 = n12 = 0
    weeks_lr: Set[date] = set()
    for d_only, d_mi, _mt in dated_rows:
        if d_mi >= _LONG_RUN_12_MI:
            n12 += 1
        if d_mi >= _LONG_RUN_GEOFENCE_MI:
            n10 += 1
            weeks_lr.add(_monday_of_calendar_week(d_only))

    trend = "unknown"
    if dated_rows:
        all_dates = sorted({d for d, _, _ in dated_rows})
        if len(all_dates) >= 2:
            mid_date = all_dates[len(all_dates) // 2]
            first_half_max = max(
                (dm for d, dm, _ in dated_rows if d < mid_date and dm >= 8.0),
                default=0.0,
            )
            second_half_max = max(
                (dm for d, dm, _ in dated_rows if d >= mid_date and dm >= 8.0),
                default=0.0,
            )
            if first_half_max <= 0 and second_half_max <= 0:
                trend = "unknown"
            elif second_half_max > first_half_max + 1.5:
                trend = "up"
            elif first_half_max > second_half_max + 1.5:
                trend = "down"
            else:
                trend = "flat"

    out: Dict[str, Any] = {
        "pace_reliability": pace_rel,
        "runs_usable_pace_count": n_pace,
        "typical_easy_pace_sec_per_mi": (
            round(typical_easy, 1) if typical_easy else None
        ),
        "best_sustained_endurance_pace_sec_per_mi": (
            round(best_sustained, 1) if best_sustained else None
        ),
        "hr_coverage_ratio": round(hr_ratio, 3) if hr_ratio is not None else None,
        "long_runs_ge_10_mi_count": n10,
        "long_runs_ge_12_mi_count": n12,
        "weeks_with_long_run_10plus": len(weeks_lr),
        "long_run_progression_trend": trend,
    }
    return out


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
    anchor_local_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Return a small dict of facts from DB runs (type Run) in the lookback window.

    ``activities_found == 0`` means no ingested runs in that window (Strava empty
    or not linked)—not a judgment about account link state.

    ``anchor_local_date`` should be the athlete's local calendar **today** when
    available so ISO-week boundaries match their week; otherwise defaults to
    server **date.today()**.
    """
    w = lookback_weeks if lookback_weeks is not None else _lookback_weeks_from_env()
    activities: List[Dict[str, Any]] = DataCollectionService.fetch_strava_activities(
        session, str(internal_user_id), weeks=w
    )
    anchor = anchor_local_date if anchor_local_date is not None else date.today()
    return _compute_plan_intake_activity_summary_from_activities(
        activities, lookback_weeks=w, anchor_local_date=anchor
    )


def build_runner_evidence(
    session: Session,
    internal_user_id: str,
    *,
    anchor_local_date: Optional[date] = None,
) -> RunnerEvidenceSummary:
    """
    Single fetch for max(recent, history) weeks; packs recent summary + 12w history
    into ``RunnerEvidenceSummary`` (includes ``weekly_mileage_history`` and
    ``consistency_weeks_active_in_history``).
    """
    recent_w = _lookback_weeks_from_env()
    history_w = _history_lookback_weeks_from_env()
    fetch_w = max(recent_w, history_w)
    activities: List[Dict[str, Any]] = DataCollectionService.fetch_strava_activities(
        session, str(internal_user_id), weeks=fetch_w
    )
    anchor = anchor_local_date if anchor_local_date is not None else date.today()
    recent_activities = _filter_activities_to_lookback(
        activities, anchor_date=anchor, lookback_weeks=recent_w
    )
    summary = _compute_plan_intake_activity_summary_from_activities(
        recent_activities, lookback_weeks=recent_w, anchor_local_date=anchor
    )
    history_rows, consistency = _weekly_mileage_history_for_calendar_weeks(
        activities, anchor_date=anchor, history_weeks=history_w
    )
    merged = {
        **summary,
        "weekly_mileage_history": history_rows,
        "consistency_weeks_active_in_history": consistency,
        "history_lookback_weeks": history_w,
    }
    return RunnerEvidenceSummary.from_activity_summary(merged)


def format_plan_intake_activity_context_block(summary: Dict[str, Any]) -> str:
    """Markdown system section: rules + numbers (no user-facing quiz)."""
    w = int(summary.get("lookback_weeks") or 6)
    n = int(summary.get("activities_found") or 0)
    has = bool(summary.get("has_running_data"))
    total = summary.get("total_miles_window")
    avg = summary.get("avg_miles_per_week_approx")
    avg_raw = summary.get("avg_miles_per_week_raw_window")
    partial = summary.get("current_calendar_week_miles_partial")
    completed_wk = int(summary.get("completed_calendar_weeks_count") or 0)
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
            ]
        )
        if completed_wk > 0:
            lines.append(
                f"- **Typical weekly volume** (mean of **{completed_wk}** completed Mon–Sun week(s), "
                f"**excluding** the current partial week): ~**{avg}** mi/wk"
            )
        else:
            lines.append(
                f"- **Approx. average per week** (total ÷ {w}, no prior full week in window): ~**{avg}** mi/wk"
            )
        if avg_raw is not None and completed_wk > 0:
            lines.append(
                f"- **Raw average** (total ÷ {w}, includes partial current week): ~**{avg_raw}** mi/wk "
                "(do **not** treat as typical volume — use **Typical weekly volume** for coaching)."
            )
        if partial is not None and float(partial) > 0:
            lines.append(
                f"- **Current calendar week to date (partial):** ~**{partial}** mi "
                "(in progress — not a full week)."
            )
        lines.extend(
            [
                f"- **Longest single run in window:** **{long_mi}** mi on **{long_dt}**",
                f"- **Most recent run date:** **{latest}**",
                "",
                "### Coaching rules for plan intake",
            ]
        )
        lines.extend(
            [
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
    *,
    anchor_local_date: Optional[date] = None,
) -> str:
    summary = compute_plan_intake_activity_summary(
        session, internal_user_id, anchor_local_date=anchor_local_date
    )
    return format_plan_intake_activity_context_block(summary)

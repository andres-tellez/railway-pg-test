from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime, timedelta

from src.services.training_plan.calculations.week_utils import get_complete_weeks
from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig


def round_to_half(value: float) -> float:
    """Round a float to the nearest 0.5 for presentation/plan values."""
    return round(value * 2) / 2.0


def recent_longest_3w(activities: List[Dict[str, Any]], *, days: int = 21) -> float:
    """Return the longest single run within the last `days` days."""
    if not activities:
        return 0.0

    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)
    longest = 0.0

    for activity in activities:
        date_str = (
            activity.get("date")
            or activity.get("start_date")
            or activity.get("startTime")
        )
        if not date_str:
            continue
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            continue
        if dt < cutoff:
            continue

        miles = _extract_miles(activity)
        if miles > longest:
            longest = miles

    return round(longest, 2)


def detect_consecutive_long_runs(
    activities: List[Dict[str, Any]], *, min_consecutive_weeks: int = 3
) -> Dict[str, Any]:
    """
    Detect whether the athlete has accumulated consecutive long runs that should
    trigger a recovery week.

    Also detects if the athlete has already self-regulated (recent reduction from peak)
    to avoid forcing a double recovery.
    """
    if not activities:
        return {
            "has_consecutive_runs": False,
            "consecutive_count": 0,
            "weekly_long_runs": [],
            "longest_recent": 0.0,
            "has_recent_reduction": False,
            "most_recent_long_run": 0.0,
        }

    weekly_data = get_complete_weeks(activities, max_weeks=4)
    if len(weekly_data) < min_consecutive_weeks:
        return {
            "has_consecutive_runs": False,
            "consecutive_count": 0,
            "weekly_long_runs": [],
            "longest_recent": 0.0,
            "has_recent_reduction": False,
            "most_recent_long_run": 0.0,
        }

    weekly_long_runs: List[float] = []
    for _, week_activities in list(weekly_data.items())[:4]:
        longest_in_week = 0.0
        has_any_runs = False

        for activity in week_activities:
            miles = _extract_miles(activity)
            if miles > 0:
                has_any_runs = True
            if miles > longest_in_week:
                longest_in_week = miles

        if has_any_runs or longest_in_week > 0:
            weekly_long_runs.append(round(longest_in_week, 2))

    if len(weekly_long_runs) < min_consecutive_weeks:
        most_recent = weekly_long_runs[0] if weekly_long_runs else 0.0
        return {
            "has_consecutive_runs": False,
            "consecutive_count": len(weekly_long_runs),
            "weekly_long_runs": weekly_long_runs,
            "longest_recent": max(weekly_long_runs) if weekly_long_runs else 0.0,
            "has_recent_reduction": False,
            "most_recent_long_run": most_recent,
        }

    consecutive_count = 0
    for lr in weekly_long_runs:
        if lr >= 8.0:
            consecutive_count += 1
        else:
            break

    has_consecutive = consecutive_count >= min_consecutive_weeks
    longest_recent = (
        max(weekly_long_runs[:consecutive_count]) if consecutive_count > 0 else 0.0
    )

    # Detect if user has already self-regulated (recent reduction from peak)
    # Pattern: [most_recent, ...previous weeks]
    # If most_recent < peak, user may have already reduced
    most_recent_long_run = weekly_long_runs[0] if weekly_long_runs else 0.0
    has_recent_reduction = False

    if len(weekly_long_runs) >= 2 and most_recent_long_run > 0 and longest_recent > 0:
        # Check if most recent week is lower than peak
        # Any reduction suggests user may have intentionally self-regulated
        # This avoids forcing double recovery when user already pulled back

        # If most recent is at least 5% lower than peak, it's likely intentional
        reduction_threshold = 0.05  # 5% reduction suggests intentional adjustment
        reduction_pct = (longest_recent - most_recent_long_run) / longest_recent

        if reduction_pct >= reduction_threshold:
            # Check if it's part of a downward trend (most recent < previous)
            # Pattern [14, 15, 15, 14] means most recent (14) < previous week (15)
            if (
                len(weekly_long_runs) >= 2
                and most_recent_long_run < weekly_long_runs[1]
            ):
                has_recent_reduction = True
            # Or if reduction is substantial (15%+), definitely intentional
            elif reduction_pct >= 0.15:
                has_recent_reduction = True

    return {
        "has_consecutive_runs": has_consecutive,
        "consecutive_count": consecutive_count,
        "weekly_long_runs": weekly_long_runs,
        "longest_recent": longest_recent,
        "has_recent_reduction": has_recent_reduction,
        "most_recent_long_run": most_recent_long_run,
    }


def calculate_recovery_week_long_run(
    longest_recent: float, *, config: RaceDistanceConfig
) -> float:
    """Compute a safe recovery-week long run using config guardrails."""
    min_reduction = max(3.0, config.long_run_increment * 3)
    max_reduction = max(5.0, config.long_run_increment * 5)
    reduction_miles = min(
        max_reduction,
        max(min_reduction, longest_recent * 0.30),
    )
    recovery_by_reduction = longest_recent - reduction_miles

    recovery_by_percent = longest_recent * config.recovery_reduction_ratio

    recovery = min(recovery_by_reduction, recovery_by_percent)
    recovery = max(config.recovery_long_run_floor, recovery)

    return round_to_half(recovery)


def _extract_miles(activity: Dict[str, Any]) -> float:
    """Best-effort extraction of miles from a Strava activity payload."""
    for key in ("miles", "distance_miles", "distance"):
        value = activity.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)

    meters = activity.get("distance_meters") or activity.get("meters")
    if isinstance(meters, (int, float)) and meters > 0:
        return float(meters) / 1609.34

    return 0.0

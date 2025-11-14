"""
Pace Seed Service V2 (shared)

Forked from src/services.training_plan.pace_seed_service to keep v2 isolated.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class PaceSeed:
    """Pace zones in seconds per mile."""

    E_min: float
    E_max: float
    S_min: float
    S_max: float
    M: float
    T_min: float
    T_max: float
    week1_long_cap: float


def _time_add(p: float, delta_sec: float) -> float:
    return p + delta_sec


def _rng(center: float, low_off: float, high_off: float) -> Tuple[float, float]:
    return (center + low_off, center + high_off)


def _calculate_pace_per_mile(
    distance_mi: float, duration_sec: float
) -> Optional[float]:
    if distance_mi <= 0 or duration_sec <= 0:
        return None
    return duration_sec / distance_mi


def median_easy_pace(runs: List[Dict[str, Any]]) -> Optional[float]:
    easy_paces = []
    for run in runs:
        distance = run.get("distance", 0) or 0
        duration = run.get("moving_time", 0) or 0
        if distance >= 2.0 and duration > 0:
            pace = _calculate_pace_per_mile(distance, duration)
            if pace is not None and 360 <= pace <= 1200:
                easy_paces.append(pace)

    if not easy_paces:
        return None

    sorted_paces = sorted(easy_paces)
    median_idx = len(sorted_paces) // 2
    return sorted_paces[median_idx]


def longest_recent_long_run(runs: List[Dict[str, Any]]) -> float:
    long_runs = [
        run.get("distance", 0) or 0
        for run in runs
        if (run.get("distance", 0) or 0) >= 10.0
    ]
    return max(long_runs) if long_runs else 0.0


def get_initial_pace_seed(
    strava_activities: List[Dict[str, Any]],
    plan_week1_total: float,
    plan_week1_long: float,
    goal_mp_sec_per_mi: Optional[float] = None,
) -> PaceSeed:
    logger.info(
        "Generating initial pace seed from %s activities", len(strava_activities)
    )

    cutoff_date = datetime.now() - timedelta(weeks=6)
    recent_activities = []
    for activity in strava_activities:
        activity_date_str = activity.get("date")
        if not activity_date_str:
            continue
        try:
            activity_date = datetime.strptime(activity_date_str, "%Y-%m-%d")
            if activity_date >= cutoff_date:
                recent_activities.append(activity)
        except Exception:
            continue

    enough_recent = len(recent_activities) >= 6

    if enough_recent:
        e_med = median_easy_pace(recent_activities)
        if e_med:
            logger.info(
                "Seeding from Strava data: median easy pace = %.1f sec/mi", e_med
            )
            E_min, E_max = _rng(e_med, +15, +45)
            S_min, S_max = _rng(e_med, -15, +15)
            M = _time_add(e_med, -60)
            T_min, T_max = _rng(M, -30, -20)

            longest = longest_recent_long_run(recent_activities)
            if longest > 0:
                week1_cap = min(plan_week1_long, max(plan_week1_long, longest + 2.0))
            else:
                week1_cap = plan_week1_long

            return PaceSeed(
                E_min=E_min,
                E_max=E_max,
                S_min=S_min,
                S_max=S_max,
                M=M,
                T_min=T_min,
                T_max=T_max,
                week1_long_cap=week1_cap,
            )

    logger.info("Using calibration-based pace seed (no recent Strava data)")

    if goal_mp_sec_per_mi is None:
        goal_mp_sec_per_mi = 10 * 60

    M = goal_mp_sec_per_mi
    T_min, T_max = _rng(M, -30, -20)
    S_min, S_max = _rng(M, +30, +60)
    E_min, E_max = _rng(M, +60, +90)

    week1_cap = min(plan_week1_long, 16.0)

    logger.info(
        "Calibration-based seed: M=%.1fs/mi, E=%.1f-%.1fs/mi, week1_cap=%.1fmi",
        M,
        E_min,
        E_max,
        week1_cap,
    )

    return PaceSeed(
        E_min=E_min,
        E_max=E_max,
        S_min=S_min,
        S_max=S_max,
        M=M,
        T_min=T_min,
        T_max=T_max,
        week1_long_cap=week1_cap,
    )

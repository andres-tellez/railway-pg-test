"""
Pace Seed Service

Purpose:
    Generate initial pace zones (E, S, M, T) for workout details generation.
    Uses two-path logic:
    1. Recent Strava data (≤6 weeks) → seed from historical pace patterns
    2. Calibration-based → conservative default paces for "Just Finish" runners

Integration:
    Uses DataCollectionService to fetch Strava activities from activities table.
    Called by Pass4WorkoutDetails to generate initial pace zones.

Database Infrastructure:
    - Leverages existing DataCollectionService.fetch_strava_activities()
    - Queries activities table via user_id (no athlete_id lookup needed)
    - Activities table contains: distance (miles), moving_time (seconds), etc.
    - Splits table exists but not needed (sufficient aggregated data in activities)

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class PaceSeed:
    """Pace zones in seconds per mile."""

    E_min: float  # Easy pace range (min)
    E_max: float  # Easy pace range (max)
    S_min: float  # Steady pace range (min)
    S_max: float  # Steady pace range (max)
    M: float  # Marathon pace (single value)
    T_min: float  # Threshold pace range (min)
    T_max: float  # Threshold pace range (max)
    week1_long_cap: float  # Week 1 long run cap in miles


# ---------- Helper Functions ----------


def _time_add(p: float, delta_sec: float) -> float:
    """Add seconds to a pace (seconds per mile)."""
    return p + delta_sec


def _rng(center: float, low_off: float, high_off: float) -> Tuple[float, float]:
    """Create a range around a center value."""
    return (center + low_off, center + high_off)


def _calculate_pace_per_mile(
    distance_mi: float, duration_sec: float
) -> Optional[float]:
    """Calculate pace in seconds per mile."""
    if distance_mi <= 0 or duration_sec <= 0:
        return None
    return duration_sec / distance_mi


# ---------- Strava Data Processing ----------


def median_easy_pace(runs: List[Dict[str, Any]]) -> Optional[float]:
    """
    Calculate median easy pace from recent runs.

    Args:
        runs: List of activity dicts with 'distance' (miles) and 'moving_time' (seconds)

    Returns:
        Median pace in seconds per mile, or None if insufficient data
    """
    easy_paces = []
    for run in runs:
        distance = run.get("distance", 0) or 0
        duration = run.get("moving_time", 0) or 0

        # Filter for easy runs (2+ miles, reasonable pace for easy effort)
        # For "Just Finish" runners, we assume most runs are easy unless marked otherwise
        if distance >= 2.0 and duration > 0:
            pace = _calculate_pace_per_mile(distance, duration)
            if (
                pace is not None and 360 <= pace <= 1200
            ):  # Reasonable range: 6:00/mi to 20:00/mi
                easy_paces.append(pace)

    if not easy_paces:
        return None

    sorted_paces = sorted(easy_paces)
    median_idx = len(sorted_paces) // 2
    return sorted_paces[median_idx]


def longest_recent_long_run(runs: List[Dict[str, Any]]) -> float:
    """
    Find longest recent run (10+ miles considered long run).

    Args:
        runs: List of activity dicts with 'distance' (miles)

    Returns:
        Longest distance in miles, or 0.0 if none found
    """
    long_runs = [
        run.get("distance", 0) or 0
        for run in runs
        if (run.get("distance", 0) or 0) >= 10.0
    ]
    return max(long_runs) if long_runs else 0.0


# ---------- Public API ----------


def get_initial_pace_seed(
    strava_activities: List[Dict[str, Any]],
    plan_week1_total: float,
    plan_week1_long: float,
    goal_mp_sec_per_mi: Optional[float] = None,
) -> PaceSeed:
    """
    Generate initial pace seed using two-path logic.

    Args:
        strava_activities: List of activity dictionaries already collected from L1/L2
                          (reuse data from orchestrator instead of making duplicate queries)
        plan_week1_total: Planned Week 1 total mileage
        plan_week1_long: Planned Week 1 long run distance (miles)
        goal_mp_sec_per_mi: Optional goal marathon pace in seconds per mile

    Returns:
        PaceSeed with all pace zones initialized

    Paths:
        1. Recent Strava (≤6 weeks, ≥6 runs) → seed from median easy pace
        2. Calibration-based → conservative defaults for "Just Finish" runners

    Note:
        This function accepts activities already collected in L1/L2 to avoid
        duplicate database queries. If called without activities, falls back to
        calibration-based seeding.
    """
    logger.info(
        f"Generating initial pace seed from {len(strava_activities)} activities"
    )

    # Filter for recent activities (last 6 weeks)
    # Activities from L1/L2 are already fetched, just filter by recency
    from datetime import datetime, timedelta

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
                f"Seeding from Strava data: median easy pace = {e_med:.1f} sec/mi"
            )
            # E = median easy (+/- 15-45s range for flexibility)
            E_min, E_max = _rng(e_med, +15, +45)  # Keep on the easy side
            S_min, S_max = _rng(e_med, -15, +15)  # Steady slightly faster than easy
            M = _time_add(e_med, -60)  # Marathon ~60s faster than easy
            T_min, T_max = _rng(M, -30, -20)  # Threshold ~20-30s faster than M

            # Cap Week 1 long run based on recent longest
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

    # Calibration-based fallback (no data or insufficient data)
    logger.info("Using calibration-based pace seed (no recent Strava data)")

    # If goal MP provided, use it; else conservative default for "Just Finish"
    if goal_mp_sec_per_mi is None:
        # Very conservative default for finisher context: 10:00/mi (600 sec/mi)
        goal_mp_sec_per_mi = 10 * 60

    M = goal_mp_sec_per_mi
    # Emulate 20-minute calibration test relationships
    # T = ~20-30s faster than M
    T_min, T_max = _rng(M, -30, -20)
    # S = ~30-60s slower than M
    S_min, S_max = _rng(M, +30, +60)
    # E = ~60-90s slower than M
    E_min, E_max = _rng(M, +60, +90)

    # Conservative Week 1 cap for finishers
    week1_cap = min(plan_week1_long, 16.0)

    logger.info(
        f"Calibration-based seed: M={M:.1f}s/mi, E={E_min:.1f}-{E_max:.1f}s/mi, "
        f"week1_cap={week1_cap:.1f}mi"
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


if __name__ == "__main__":
    # Quick test
    # Test with empty activities (calibration-based fallback)
    seed_empty = get_initial_pace_seed(
        strava_activities=[],
        plan_week1_total=20.0,
        plan_week1_long=8.0,
    )
    print(
        f"Calibration-based seed: E={seed_empty.E_min:.1f}-{seed_empty.E_max:.1f}s/mi, M={seed_empty.M:.1f}s/mi"
    )

    # Test with sample activities (Strava-based)
    sample_activities = [
        {"date": "2025-01-20", "distance": 5.0, "moving_time": 2400},  # 8:00/mi
        {"date": "2025-01-18", "distance": 4.0, "moving_time": 1920},  # 8:00/mi
        {"date": "2025-01-15", "distance": 6.0, "moving_time": 2880},  # 8:00/mi
        {"date": "2025-01-13", "distance": 5.0, "moving_time": 2400},  # 8:00/mi
        {"date": "2025-01-10", "distance": 7.0, "moving_time": 3360},  # 8:00/mi
        {"date": "2025-01-08", "distance": 4.0, "moving_time": 1920},  # 8:00/mi
    ]
    seed_with_data = get_initial_pace_seed(
        strava_activities=sample_activities,
        plan_week1_total=20.0,
        plan_week1_long=8.0,
    )
    print(
        f"Strava-based seed: E={seed_with_data.E_min:.1f}-{seed_with_data.E_max:.1f}s/mi, M={seed_with_data.M:.1f}s/mi"
    )

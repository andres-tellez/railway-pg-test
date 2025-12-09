"""
Performance-Based Pace Calculator

Calculate all pace zones from recent run performance using SQL.
Simple, clean, reliable approach.
"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta

from .models import PaceSeed


def calculate_paces_from_performance(
    session: Session,
    user_id: str,
    lookback_weeks: int = 6,
    min_distance_miles: float = 2.0,
) -> Optional[PaceSeed]:
    """
    Calculate all pace zones from recent run performance.

    Strategy:
    1. Calculate median easy pace from recent runs (2+ miles, last 6 weeks)
    2. Build all pace zones around that median

    Formula (from TARGET_PACE_EXPLAINER.md):
    - Easy: Median - 15 to + 45 seconds
    - Steady: Median - 15 to + 15 seconds
    - Marathon: Median - 60 seconds
    - Threshold: Marathon - 20 to 30 seconds

    Returns:
        PaceSeed with all pace zones, or None if insufficient data (< 6 runs)
    """
    cutoff = datetime.now() - timedelta(weeks=lookback_weeks)

    # SQL query to calculate median easy pace
    query = text(
        """
        WITH valid_runs AS (
            SELECT
                moving_time::float / conv_distance AS pace_sec_per_mile
            FROM activities
            WHERE user_id = :user_id
              AND type = 'Run'
              AND start_date >= :cutoff
              AND conv_distance >= :min_distance
              AND moving_time IS NOT NULL
              AND moving_time > 0
              AND conv_distance > 0
              AND (moving_time::float / conv_distance) BETWEEN 360 AND 1200
        )
        SELECT
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pace_sec_per_mile) AS median_pace,
            COUNT(*) AS run_count
        FROM valid_runs
    """
    )

    result = session.execute(
        query,
        {
            "user_id": user_id,
            "cutoff": cutoff,
            "min_distance": min_distance_miles,
        },
    ).first()

    if not result or result.run_count < 6:
        return None  # Insufficient data

    median_easy_pace = float(result.median_pace)

    # Calculate week1_long_cap from longest recent run
    week1_long_cap = _calculate_week1_long_cap(session, user_id, cutoff)

    # Build all pace zones from median easy pace
    return _build_pace_zones_from_median(median_easy_pace, week1_long_cap)


def _build_pace_zones_from_median(
    median_easy_pace: float,
    week1_long_cap: float,
) -> PaceSeed:
    """
    Build all pace zones from median easy pace.

    Formula (from TARGET_PACE_EXPLAINER.md):
    - Easy: Median - 15 to + 45 seconds (conversational pace)
    - Steady: Median - 15 to + 15 seconds (slightly faster)
    - Marathon: Median - 60 seconds (race goal)
    - Threshold: Marathon - 20 to 30 seconds (hard efforts)
    """
    return PaceSeed(
        E_min=median_easy_pace - 15,  # Easy min
        E_max=median_easy_pace + 45,  # Easy max
        S_min=median_easy_pace - 15,  # Steady min
        S_max=median_easy_pace + 15,  # Steady max
        M=median_easy_pace - 60,  # Marathon pace
        T_min=(median_easy_pace - 60) - 30,  # Threshold min (Marathon - 30s)
        T_max=(median_easy_pace - 60) - 20,  # Threshold max (Marathon - 20s)
        week1_long_cap=week1_long_cap,
    )


def _calculate_week1_long_cap(
    session: Session,
    user_id: str,
    cutoff: datetime,
) -> float:
    """Calculate max long run for week 1 from recent longest run."""
    query = text(
        """
        SELECT conv_distance
        FROM activities
        WHERE user_id = :user_id
          AND type = 'Run'
          AND start_date >= :cutoff
          AND conv_distance >= 10.0
        ORDER BY conv_distance DESC
        LIMIT 1
    """
    )

    result = session.execute(query, {"user_id": user_id, "cutoff": cutoff}).scalar()

    if result:
        return max(8.0, float(result) + 2.0)
    return 8.0

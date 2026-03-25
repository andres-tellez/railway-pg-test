"""
Performance-Based Pace Calculator

Calculate all pace zones from recent run performance using SQL.
Simple, clean, reliable approach.
"""

import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta, timezone

from .models import PaceSeed
from .config import PaceConfig, DEFAULT_CONFIG
from .validation import validate_input_parameters, validate_pace_seed

logger = logging.getLogger(__name__)
# Ensure logger is configured to show INFO level logs
if not logger.handlers:
    import sys

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
logger.propagate = True


def calculate_paces_from_performance(
    session: Session,
    user_id: str,
    lookback_weeks: int = None,
    min_distance_miles: float = None,
    config: PaceConfig = None,
) -> Optional[PaceSeed]:
    """
    Calculate all pace zones from recent run performance.

    Strategy:
    1. Calculate median easy pace from recent runs (2+ miles, last 6 weeks)
    2. Build all pace zones around that median

    Formula (from TARGET_PACE_EXPLAINER.md):
    - Easy: Median - 15 to + 45 seconds
    - Steady: Median - 30 to - 10 seconds (between Easy and Marathon)
    - Marathon: Median - 60 seconds
    - Threshold: Marathon - 20 to 30 seconds

    Args:
        session: Database session
        user_id: User UUID string
        lookback_weeks: Weeks of history to analyze (default: from config)
        min_distance_miles: Minimum distance for runs (default: from config)
        config: PaceConfig instance (defaults to DEFAULT_CONFIG)

    Returns:
        PaceSeed with all pace zones, or None if insufficient data (< 6 runs)

    Raises:
        ValueError: If input parameters are invalid
        RuntimeError: If database query fails
    """
    config = config or DEFAULT_CONFIG
    lookback_weeks = lookback_weeks or config.LOOKBACK_WEEKS
    min_distance_miles = min_distance_miles or config.MIN_DISTANCE_MILES

    # Validate input parameters
    is_valid, error_msg = validate_input_parameters(
        user_id=user_id,
        lookback_weeks=lookback_weeks,
        min_distance_miles=min_distance_miles,
    )
    if not is_valid:
        logger.error(f"Invalid input parameters: {error_msg}")
        raise ValueError(f"Invalid input parameters: {error_msg}")

    # Debug: Print to verify function is called
    print(
        f"[DEBUG] calculate_paces_from_performance called: user_id={user_id}, lookback_weeks={lookback_weeks}"
    )

    logger.info(
        f"Calculating paces from performance: user_id={user_id}, "
        f"lookback_weeks={lookback_weeks}, min_distance={min_distance_miles}"
    )

    try:
        # First, get the actual cutoff date that PostgreSQL will use
        # Use DATE() to ensure cutoff is always at midnight UTC, making it consistent
        # regardless of when the query runs (avoids time-of-day differences)
        cutoff_query = text(
            """
            SELECT
                DATE(NOW() AT TIME ZONE 'UTC') AS current_date_utc,
                (DATE(NOW() AT TIME ZONE 'UTC') - make_interval(weeks => :lookback_weeks)) AS cutoff_date_utc
            """
        )
        cutoff_result = session.execute(
            cutoff_query, {"lookback_weeks": lookback_weeks}
        ).first()

        if cutoff_result:
            current_date_utc = cutoff_result.current_date_utc
            cutoff_date_utc = cutoff_result.cutoff_date_utc
            logger.info(
                f"[Pace Calculation Debug] PostgreSQL current date UTC: {current_date_utc}, "
                f"Cutoff date (current date - {lookback_weeks} weeks): {cutoff_date_utc}"
            )

        # Calculate cutoff directly in PostgreSQL to ensure consistency across all environments
        # Use DATE() to ensure cutoff is always at midnight UTC, making it consistent
        # regardless of when the query runs (avoids time-of-day differences between local/prod)
        query = text(
            """
            WITH valid_runs AS (
                SELECT
                    moving_time::float / conv_distance AS pace_sec_per_mile,
                    start_date
                FROM activities
                WHERE user_id = :user_id
                  AND type = 'Run'
                  AND DATE(start_date AT TIME ZONE 'UTC') >= (DATE(NOW() AT TIME ZONE 'UTC') - make_interval(weeks => :lookback_weeks))
                  AND conv_distance >= :min_distance
                  AND moving_time IS NOT NULL
                  AND moving_time > 0
                  AND conv_distance > 0
                  AND (moving_time::float / conv_distance) BETWEEN :min_pace AND :max_pace
            )
            SELECT
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pace_sec_per_mile) AS median_pace,
                COUNT(*) AS run_count,
                MIN(start_date) AS earliest_run,
                MAX(start_date) AS latest_run
            FROM valid_runs
        """
        )

        logger.info(
            f"[Pace Calculation Debug] Query parameters: user_id={user_id}, "
            f"lookback_weeks={lookback_weeks}, min_distance={min_distance_miles}, "
            f"min_pace={config.MIN_PACE_SEC_PER_MILE}, max_pace={config.MAX_PACE_SEC_PER_MILE}"
        )

        result = session.execute(
            query,
            {
                "user_id": user_id,
                "lookback_weeks": lookback_weeks,
                "min_distance": min_distance_miles,
                "min_pace": config.MIN_PACE_SEC_PER_MILE,
                "max_pace": config.MAX_PACE_SEC_PER_MILE,
            },
        ).first()

        if not result:
            logger.warning(
                f"No results from database query for user {user_id} "
                f"(lookback_weeks={lookback_weeks})"
            )
            return None

        run_count = result.run_count or 0
        if run_count < config.MIN_RUNS_REQUIRED:
            logger.info(
                f"Insufficient data: {run_count} runs found "
                f"(minimum: {config.MIN_RUNS_REQUIRED})"
            )
            return None

        median_easy_pace = float(result.median_pace)
        earliest_run = result.earliest_run if hasattr(result, "earliest_run") else None
        latest_run = result.latest_run if hasattr(result, "latest_run") else None

        logger.info(
            f"[Pace Calculation Debug] Query results: "
            f"run_count={run_count}, median_pace={median_easy_pace:.2f}s/mi ({median_easy_pace/60:.2f} min/mi), "
            f"earliest_run={earliest_run}, latest_run={latest_run}"
        )

        logger.debug(
            f"Found {run_count} valid runs, median easy pace: {median_easy_pace:.1f}s/mi"
        )

        # Calculate week1_long_cap from longest recent run
        week1_long_cap = _calculate_week1_long_cap(session, user_id, lookback_weeks)

        # Build all pace zones from median easy pace
        seed = _build_pace_zones_from_median(median_easy_pace, week1_long_cap)

        # Validate the calculated seed
        is_valid, error_msg = validate_pace_seed(seed)
        if not is_valid:
            logger.error(f"Calculated pace seed failed validation: {error_msg}")
            raise RuntimeError(f"Calculated pace seed failed validation: {error_msg}")

        logger.info(
            f"Successfully calculated pace zones: "
            f"Easy={seed.E_min:.1f}-{seed.E_max:.1f}s/mi, "
            f"Marathon={seed.M:.1f}s/mi"
        )

        return seed

    except Exception as e:
        if isinstance(e, (ValueError, RuntimeError)):
            raise
        logger.error(
            f"Database error calculating paces for user {user_id}: {e}", exc_info=True
        )
        raise RuntimeError(f"Failed to calculate paces from performance: {e}") from e


def _build_pace_zones_from_median(
    median_easy_pace: float,
    week1_long_cap: float,
) -> PaceSeed:
    """
    Build all pace zones from median easy pace.

    Formula (from TARGET_PACE_EXPLAINER.md):
    - Easy: Median - 15 to + 45 seconds (conversational pace)
    - Steady: Median - 30 to - 10 seconds (moderate effort, between Easy and Marathon)
    - Marathon: Median - 60 seconds (race goal)
    - Threshold: Marathon - 20 to 30 seconds (hard efforts)

    Args:
        median_easy_pace: Median easy pace in seconds per mile
        week1_long_cap: Maximum long run distance for week 1

    Returns:
        PaceSeed with all pace zones
    """
    config = DEFAULT_CONFIG

    marathon_pace = median_easy_pace + config.MARATHON_OFFSET

    return PaceSeed(
        E_min=median_easy_pace + config.EASY_MIN_OFFSET,
        E_max=median_easy_pace + config.EASY_MAX_OFFSET,
        S_min=median_easy_pace + config.STEADY_MIN_OFFSET,
        S_max=median_easy_pace + config.STEADY_MAX_OFFSET,
        M=marathon_pace,
        T_min=marathon_pace + config.THRESHOLD_MIN_OFFSET,
        T_max=marathon_pace + config.THRESHOLD_MAX_OFFSET,
        week1_long_cap=week1_long_cap,
    )


def _calculate_week1_long_cap(
    session: Session,
    user_id: str,
    lookback_weeks: int,
) -> float:
    """
    Calculate max long run for week 1 from recent longest run.

    Args:
        session: Database session
        user_id: User UUID string
        lookback_weeks: Number of weeks to look back

    Returns:
        Maximum long run distance for week 1 (miles)
    """
    config = DEFAULT_CONFIG

    try:
        # Calculate cutoff directly in PostgreSQL to ensure consistency
        # Use DATE() to ensure cutoff is always at midnight UTC, making it consistent
        # regardless of when the query runs (avoids time-of-day differences between local/prod)
        query = text(
            """
            SELECT conv_distance
            FROM activities
            WHERE user_id = :user_id
              AND type = 'Run'
              AND DATE(start_date AT TIME ZONE 'UTC') >= (DATE(NOW() AT TIME ZONE 'UTC') - make_interval(weeks => :lookback_weeks))
              AND conv_distance >= :min_distance
            ORDER BY conv_distance DESC
            LIMIT 1
        """
        )

        result = session.execute(
            query,
            {
                "user_id": user_id,
                "lookback_weeks": lookback_weeks,
                "min_distance": config.MIN_RUN_FOR_LONG_CAP,
            },
        ).scalar()

        if result:
            calculated_cap = max(
                config.MIN_WEEK1_LONG_CAP,
                float(result) + config.WEEK1_LONG_CAP_BUFFER,
            )
            logger.debug(
                f"Week1 long cap: {calculated_cap:.1f} miles "
                f"(based on longest run: {float(result):.1f} miles)"
            )
            return calculated_cap

        logger.debug(
            f"No runs >= {config.MIN_RUN_FOR_LONG_CAP} miles found, "
            f"using default: {config.MIN_WEEK1_LONG_CAP} miles"
        )
        return config.MIN_WEEK1_LONG_CAP

    except Exception as e:
        logger.warning(
            f"Error calculating week1_long_cap for user {user_id}: {e}. "
            f"Using default: {config.MIN_WEEK1_LONG_CAP} miles"
        )
        return config.MIN_WEEK1_LONG_CAP

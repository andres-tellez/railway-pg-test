"""
Pace Zone Calculator

Main entry point for calculating pace zones.
Uses strategy pattern to try multiple calculation methods.
"""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from .models import PaceSeed
from .config import PaceConfig, DEFAULT_CONFIG
from .validation import validate_input_parameters
from .strategies import (
    PaceCalculationStrategy,
    PerformanceBasedStrategy,
    CalibrationStrategy,
    DEFAULT_STRATEGIES,
)

logger = logging.getLogger(__name__)


def get_initial_pace_seed(
    session: Session,
    user_id: str,
    week1_long: float = None,
    lookback_weeks: int = None,
    config: PaceConfig = None,
    strategies: List[PaceCalculationStrategy] = None,
) -> PaceSeed:
    """
    Calculate initial pace zones for a user using strategy pattern.

    Tries strategies in order until one succeeds:
    1. Performance-based calculation (median easy pace from recent runs)
    2. Calibration (conservative defaults)

    Args:
        session: Database session
        user_id: User UUID string
        week1_long: Planned long run distance for week 1 (default: from config)
        lookback_weeks: Weeks of history to analyze (default: from config)
        config: PaceConfig instance (defaults to DEFAULT_CONFIG)
        strategies: List of strategies to try (defaults to DEFAULT_STRATEGIES)

    Returns:
        PaceSeed with all pace zones

    Raises:
        ValueError: If input parameters are invalid
        RuntimeError: If all strategies fail
    """
    config = config or DEFAULT_CONFIG
    strategies = strategies or DEFAULT_STRATEGIES
    week1_long = week1_long or config.MIN_WEEK1_LONG_CAP
    lookback_weeks = lookback_weeks or config.LOOKBACK_WEEKS

    # Validate input parameters
    is_valid, error_msg = validate_input_parameters(
        user_id=user_id,
        lookback_weeks=lookback_weeks,
        week1_long=week1_long,
    )
    if not is_valid:
        logger.error(f"Invalid input parameters: {error_msg}")
        raise ValueError(f"Invalid input parameters: {error_msg}")

    logger.info(
        f"Calculating initial pace seed: user_id={user_id}, "
        f"week1_long={week1_long}, lookback_weeks={lookback_weeks}, "
        f"strategies={[s.name for s in strategies]}"
    )

    # Try each strategy in order
    last_error = None
    for strategy in strategies:
        try:
            result = strategy.calculate(
                session=session,
                user_id=user_id,
                week1_long=week1_long,
                lookback_weeks=lookback_weeks,
            )

            if result:
                logger.info(f"Successfully calculated pace using {strategy.name}")
                return result
            else:
                logger.debug(
                    f"{strategy.name} returned None (insufficient data), "
                    f"trying next strategy"
                )
        except Exception as e:
            logger.warning(f"{strategy.name} failed: {e}, trying next strategy")
            last_error = e

    # All strategies failed
    error_msg = (
        f"All pace calculation strategies failed. " f"Last error: {last_error}"
        if last_error
        else "No strategies succeeded"
    )
    logger.error(error_msg)
    raise RuntimeError(error_msg)

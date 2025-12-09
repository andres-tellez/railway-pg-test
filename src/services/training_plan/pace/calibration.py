"""
Calibration Pace Zones

Conservative defaults for users without sufficient run data.
"""

import logging

from .models import PaceSeed
from .config import PaceConfig, DEFAULT_CONFIG
from .validation import validate_input_parameters, validate_pace_seed

logger = logging.getLogger(__name__)


def get_calibration_pace_seed(
    week1_long: float = None, config: PaceConfig = None
) -> PaceSeed:
    """
    Return conservative pace zones for "Just Finish" runners.

    Default: 10:00/mile marathon pace

    Args:
        week1_long: Planned long run distance for week 1 (default: from config)
        config: PaceConfig instance (defaults to DEFAULT_CONFIG)

    Returns:
        PaceSeed with conservative pace zones

    Raises:
        ValueError: If week1_long is invalid
        RuntimeError: If calculated seed fails validation
    """
    config = config or DEFAULT_CONFIG
    week1_long = week1_long or config.MIN_WEEK1_LONG_CAP

    # Validate input
    is_valid, error_msg = validate_input_parameters(week1_long=week1_long)
    if not is_valid:
        logger.error(f"Invalid week1_long parameter: {error_msg}")
        raise ValueError(f"Invalid week1_long parameter: {error_msg}")

    seed = PaceSeed(
        E_min=config.CALIBRATION_EASY_MIN,
        E_max=config.CALIBRATION_EASY_MAX,
        S_min=config.CALIBRATION_STEADY_MIN,
        S_max=config.CALIBRATION_STEADY_MAX,
        M=config.CALIBRATION_MARATHON_PACE,
        T_min=config.CALIBRATION_THRESHOLD_MIN,
        T_max=config.CALIBRATION_THRESHOLD_MAX,
        week1_long_cap=max(week1_long, config.MIN_WEEK1_LONG_CAP),
    )

    # Validate the seed
    is_valid, error_msg = validate_pace_seed(seed)
    if not is_valid:
        logger.error(f"Calibration pace seed failed validation: {error_msg}")
        raise RuntimeError(f"Calibration pace seed failed validation: {error_msg}")

    logger.info(
        f"Generated calibration pace seed: "
        f"Marathon={seed.M:.1f}s/mi, week1_long_cap={seed.week1_long_cap:.1f}mi"
    )

    return seed

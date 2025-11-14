"""
Race Distance Factory V2

Routes requests to race-distance-specific services and configurations.
"""

import logging
from typing import Dict, Any, Optional

from .race_configs.base_config import RaceDistanceConfig
from .race_configs.marathon_config import MarathonConfig

logger = logging.getLogger(__name__)


def _is_half_marathon(race_distance: str) -> bool:
    """
    Determine if race distance is half marathon.

    Args:
        race_distance: Race distance string (e.g., "Half Marathon", "13.1", "Marathon")

    Returns:
        True if half marathon, False otherwise
    """
    if not race_distance:
        return False

    race_lower = race_distance.lower()
    return "half" in race_lower or "13.1" in race_lower


def get_race_config(race_distance: str) -> RaceDistanceConfig:
    """
    Get race-distance-specific configuration.

    Args:
        race_distance: Race distance string (e.g., "Marathon", "Half Marathon")

    Returns:
        RaceDistanceConfig instance
    """
    if _is_half_marathon(race_distance):
        logger.info("Using half-marathon configuration")
        # TODO: Implement HalfMarathonConfig when ready
        raise NotImplementedError("Half marathon config not yet implemented")
    else:
        logger.info("Using marathon configuration (default)")
        return MarathonConfig()


def normalize_race_distance(race_distance: str) -> str:
    """
    Normalize race distance string to canonical form.

    Args:
        race_distance: Race distance string (e.g., "Marathon", "26.2", "Full Marathon")

    Returns:
        Normalized race distance ("Marathon" or "Half Marathon")
    """
    if not race_distance:
        return "Marathon"  # Default

    race_lower = race_distance.lower()

    if _is_half_marathon(race_distance):
        return "Half Marathon"
    else:
        return "Marathon"


def get_race_distance_services(race_distance: str) -> Dict[str, Any]:
    """
    Return race-distance-specific services (currently config + normalized label).
    """
    normalized = normalize_race_distance(race_distance)
    config = get_race_config(race_distance)
    return {
        "race_config": config,
        "race_distance": normalized,
    }

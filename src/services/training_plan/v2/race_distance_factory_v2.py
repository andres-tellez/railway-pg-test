"""
Race Distance Factory V2

Routes requests to race-distance-specific services and configurations.
"""

import logging
from typing import Dict, Any, Optional

from .race_configs.base_config import RaceDistanceConfig
from .race_configs.marathon_config import MarathonConfig
from .race_configs.half_marathon_config import HalfMarathonConfig

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


def get_race_type_key(race_distance: str) -> str:
    """
    Convert normalized race distance to template key for WEEKLY_TEMPLATES lookup.

    Args:
        race_distance: Normalized race distance ("Marathon", "Half Marathon")

    Returns:
        Template key ("marathon", "half", etc.) used in WEEKLY_TEMPLATES dictionary
    """
    if not race_distance:
        return "marathon"

    race_lower = race_distance.lower()
    if "half" in race_lower or "13.1" in race_lower:
        return "half"
    else:
        return "marathon"


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
        return HalfMarathonConfig()
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
    Return race-distance-specific services (config + normalized label + template key).

    Returns:
        Dictionary containing:
        - "race_config": RaceDistanceConfig instance
        - "race_distance": Normalized race distance ("Marathon", "Half Marathon")
        - "race_type": Template key ("marathon", "half") for WEEKLY_TEMPLATES lookup
    """
    normalized = normalize_race_distance(race_distance)
    config = get_race_config(race_distance)
    race_type_key = get_race_type_key(normalized)
    return {
        "race_config": config,
        "race_distance": normalized,
        "race_type": race_type_key,
    }

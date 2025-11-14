"""
Race Distance Configuration Module

Provides race-distance-specific configuration for plan generation.
"""

from .base_config import RaceDistanceConfig
from .marathon_config import MarathonConfig

__all__ = ["RaceDistanceConfig", "MarathonConfig"]

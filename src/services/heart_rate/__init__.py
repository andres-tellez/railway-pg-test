"""
Heart Rate Zone Services

Provides HRmax estimation and Karvonen zone calculation.
All services follow pure function patterns with dataclass returns.
"""

from .heart_rate_orchestration_service import (
    HeartRateZoneOrchestrationService,
)
from .hrmax_estimation_service import HRMaxEstimationService, HRMaxEstimationResult
from .karvonen_zone_service import KarvonenZoneService, KarvonenZonesResult
from .hrmax_resolution_service import HRMaxResolutionService
from .estimation_helpers import (
    parse_age_from_group,
    estimate_resting_hr_from_age,
    estimate_resting_hr_from_age_group,
    zone_percentage_to_bpm,
)

__all__ = [
    "HeartRateZoneOrchestrationService",
    "HRMaxEstimationService",
    "HRMaxEstimationResult",
    "KarvonenZoneService",
    "KarvonenZonesResult",
    "HRMaxResolutionService",
    "parse_age_from_group",
    "estimate_resting_hr_from_age",
    "estimate_resting_hr_from_age_group",
    "zone_percentage_to_bpm",
]

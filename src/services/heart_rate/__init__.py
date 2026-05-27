"""
Heart Rate Zone Services

Provides HRmax estimation and Karvonen zone calculation.
All services follow pure function patterns with dataclass returns.
"""

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
    "refresh_user_zones",
]

_LAZY_EXPORTS = {
    "HeartRateZoneOrchestrationService": (
        ".heart_rate_orchestration_service",
        "HeartRateZoneOrchestrationService",
    ),
    "refresh_user_zones": (".zone_population_service", "refresh_user_zones"),
}


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        module_path, attr = _LAZY_EXPORTS[name]
        import importlib

        module = importlib.import_module(module_path, __name__)
        return getattr(module, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

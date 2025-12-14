"""
Karvonen Zone Service

Pure calculation service for Karvonen heart rate zone calculation.
No database access.

This service calculates HR zones using the Karvonen method:
HRR (Heart Rate Reserve) = HRmax - Resting HR
Zone HR = HRR × ZonePercentage + Resting HR
"""

import logging
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Any

from src.utils.hr_zone_constants import (
    HRMAX_ESTIMATION,
    KARVONEN_ZONE_PERCENTAGES,
)

logger = logging.getLogger(__name__)


@dataclass
class KarvonenZonesResult:
    """Result of Karvonen zone calculation."""

    success: bool
    zones: Optional[Dict[str, Tuple[float, float]]] = None
    hrr: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "zones": self.zones,
            "hrr": self.hrr,
        }


class KarvonenZoneService:
    """
    Pure calculation service for Karvonen zone calculation.

    ERROR HANDLING:
    - Raises ValueError: Invalid input ranges (hrmax or resting_hr out of valid range)

    GUARDRAILS:
    - No imports from other heart_rate services
    - No database access
    - All constants from hr_zone_constants.py
    """

    @staticmethod
    def calculate_zones(hrmax: int, resting_hr: int) -> KarvonenZonesResult:
        """
        Calculate Karvonen heart rate zones.

        Args:
            hrmax: Maximum heart rate (120-220 bpm)
            resting_hr: Resting heart rate (35-110 bpm)

        Returns:
            KarvonenZonesResult with zones dict

        Raises:
            ValueError: If hrmax or resting_hr outside valid ranges or HRR < 30
        """
        # Input validation - raise ValueError (invalid user input)
        if not (
            HRMAX_ESTIMATION["HRMAX_MIN"] <= hrmax <= HRMAX_ESTIMATION["HRMAX_MAX"]
        ):
            raise ValueError(
                f"Invalid HRmax: {hrmax} (must be "
                f"{HRMAX_ESTIMATION['HRMAX_MIN']}-{HRMAX_ESTIMATION['HRMAX_MAX']} bpm)"
            )

        if not (
            HRMAX_ESTIMATION["RESTING_HR_MIN"]
            <= resting_hr
            <= HRMAX_ESTIMATION["RESTING_HR_MAX"]
        ):
            raise ValueError(
                f"Invalid resting HR: {resting_hr} (must be "
                f"{HRMAX_ESTIMATION['RESTING_HR_MIN']}-"
                f"{HRMAX_ESTIMATION['RESTING_HR_MAX']} bpm)"
            )

        # Calculate HRR and validate minimum
        hrr = hrmax - resting_hr
        if hrr < HRMAX_ESTIMATION["MIN_HRR"]:
            raise ValueError(
                f"Heart Rate Reserve too small: {hrr} bpm (HRmax {hrmax} - "
                f"resting {resting_hr}). Minimum HRR is {HRMAX_ESTIMATION['MIN_HRR']} bpm."
            )

        # Also check hrmax < resting_hr (pathological case)
        if hrmax <= resting_hr:
            raise ValueError(
                f"HRmax ({hrmax}) must be greater than resting HR ({resting_hr})"
            )

        # Pure calculation
        zones = {
            "Z1": (
                hrr * KARVONEN_ZONE_PERCENTAGES["Z1"][0] + resting_hr,
                hrr * KARVONEN_ZONE_PERCENTAGES["Z1"][1] + resting_hr,
            ),
            "Z2": (
                hrr * KARVONEN_ZONE_PERCENTAGES["Z2"][0] + resting_hr,
                hrr * KARVONEN_ZONE_PERCENTAGES["Z2"][1] + resting_hr,
            ),
            "Z3": (
                hrr * KARVONEN_ZONE_PERCENTAGES["Z3"][0] + resting_hr,
                hrr * KARVONEN_ZONE_PERCENTAGES["Z3"][1] + resting_hr,
            ),
            "Z4": (
                hrr * KARVONEN_ZONE_PERCENTAGES["Z4"][0] + resting_hr,
                hrr * KARVONEN_ZONE_PERCENTAGES["Z4"][1] + resting_hr,
            ),
            "Z5": (
                hrr * KARVONEN_ZONE_PERCENTAGES["Z5"][0] + resting_hr,
                hrmax,  # Upper bound is actual HRmax
            ),
        }

        logger.debug(
            "Karvonen zones calculated",
            extra={
                "hrmax": hrmax,
                "resting_hr": resting_hr,
                "hrr": hrr,
            },
        )

        return KarvonenZonesResult(
            success=True,
            zones=zones,
            hrr=hrr,
        )

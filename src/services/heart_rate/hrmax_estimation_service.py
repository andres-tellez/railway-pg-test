"""
HRMax Estimation Service

Pure calculation service for estimating HRmax from activities.
No database access, no user context.

This service implements the HRmax estimation algorithm:
1. Filters activities by minimum duration
2. Removes outliers using statistical methods
3. Calculates HRmax using 95th percentile
4. Returns confidence level based on data quality
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Literal
import numpy as np

from src.utils.hr_zone_constants import HRMAX_ESTIMATION
from src.services.heart_rate.validation import validate_activities_shape

logger = logging.getLogger(__name__)


@dataclass
class HRMaxEstimationResult:
    """Result of HRmax estimation from activities."""

    success: bool
    hrmax: Optional[int] = None
    confidence: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"
    activity_count: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "hrmax": self.hrmax,
            "confidence": self.confidence,
            "activity_count": self.activity_count,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


class HRMaxEstimationService:
    """
    Pure calculation service for HRmax estimation.

    ERROR HANDLING:
    - Raises ValueError: Invalid input (activities not list, None, or empty)
    - Returns success=False: Valid input but insufficient/poor-quality data

    GUARDRAILS:
    - No imports from other heart_rate services
    - No database access
    - No user_id in logs
    - All constants from hr_zone_constants.py
    """

    @staticmethod
    def estimate_hrmax(activities: List[Dict[str, Any]]) -> HRMaxEstimationResult:
        """
        Estimate HRmax from activities.

        Args:
            activities: List of activity dicts with max_heartrate, moving_time

        Returns:
            HRMaxEstimationResult with success, hrmax, confidence, or error fields

        Raises:
            ValueError: If activities is None, not a list, or empty list
        """
        # Input validation - raise ValueError (developer/user error)
        is_valid, error_msg = validate_activities_shape(activities)
        if not is_valid:
            raise ValueError(error_msg)

        # Filter 1: Must have HR data and minimum duration
        hr_activities = [
            a
            for a in activities
            if a.get("max_heartrate") is not None
            and a.get("moving_time", 0) >= HRMAX_ESTIMATION["MIN_DURATION_SECONDS"]
        ]

        # Calculation failure - return structured error (data quality issue)
        if len(hr_activities) < HRMAX_ESTIMATION["MIN_ACTIVITIES_REQUIRED"]:
            return HRMaxEstimationResult(
                success=False,
                confidence="LOW",
                activity_count=len(hr_activities),
                error_code="INSUFFICIENT_DATA",
                error_message=(
                    f"Insufficient HR data: {len(hr_activities)} activities "
                    f"(minimum {HRMAX_ESTIMATION['MIN_ACTIVITIES_REQUIRED']} required)"
                ),
            )

        # Extract HR max values
        hr_maxes = [a["max_heartrate"] for a in hr_activities]
        mean_hr = np.mean(hr_maxes)
        std_hr = np.std(hr_maxes)

        # Outlier filtering with fallback
        if std_hr == 0:
            # All values identical - no filtering needed
            filtered = hr_maxes
        else:
            filtered = [
                hr
                for hr in hr_maxes
                if abs(hr - mean_hr)
                <= HRMAX_ESTIMATION["OUTLIER_STD_DEVIATIONS"] * std_hr
            ]

        # Fallback if too many values filtered out
        if len(filtered) < HRMAX_ESTIMATION["MIN_FILTERED_VALUES"]:
            # Too aggressive filtering - use original values
            filtered = hr_maxes
            logger.warning(
                "Outlier filter removed too many values, using original dataset",
                extra={
                    "original_count": len(hr_maxes),
                    "filtered_count": len(
                        [
                            hr
                            for hr in hr_maxes
                            if abs(hr - mean_hr)
                            <= HRMAX_ESTIMATION["OUTLIER_STD_DEVIATIONS"] * std_hr
                        ]
                    ),
                },
            )

        # Final check after fallback
        if len(filtered) < HRMAX_ESTIMATION["MIN_ACTIVITIES_REQUIRED"]:
            return HRMaxEstimationResult(
                success=False,
                confidence="LOW",
                activity_count=len(filtered),
                error_code="INSUFFICIENT_DATA",
                error_message=(
                    f"Not enough clean HR data after filtering: {len(filtered)} activities "
                    f"(minimum {HRMAX_ESTIMATION['MIN_ACTIVITIES_REQUIRED']} required)"
                ),
            )

        # Calculate HRmax using 95th percentile
        hrmax = float(np.percentile(filtered, HRMAX_ESTIMATION["PERCENTILE"]))

        # Physiological validation - return structured error if invalid
        if not (
            HRMAX_ESTIMATION["HRMAX_MIN"] <= hrmax <= HRMAX_ESTIMATION["HRMAX_MAX"]
        ):
            return HRMaxEstimationResult(
                success=False,
                confidence="LOW",
                activity_count=len(filtered),
                error_code="INVALID_HRMAX_RANGE",
                error_message=(
                    f"Estimated HRmax {hrmax:.1f} bpm outside valid range "
                    f"({HRMAX_ESTIMATION['HRMAX_MIN']}-{HRMAX_ESTIMATION['HRMAX_MAX']})"
                ),
            )

        # Confidence scoring
        count = len(filtered)
        if count < HRMAX_ESTIMATION["MIN_ACTIVITIES_FOR_MEDIUM_CONFIDENCE"]:
            confidence = "LOW"
        elif count < HRMAX_ESTIMATION["MIN_ACTIVITIES_FOR_HIGH_CONFIDENCE"]:
            confidence = "MEDIUM"
        else:
            confidence = "HIGH"

        logger.info(
            "HRmax estimation completed",
            extra={
                "activity_count": count,
                "confidence": confidence,
                "estimated_hrmax": round(hrmax),
            },
        )

        return HRMaxEstimationResult(
            success=True,
            hrmax=round(hrmax),
            confidence=confidence,
            activity_count=count,
        )

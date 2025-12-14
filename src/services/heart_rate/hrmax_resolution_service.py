"""
HRMax Resolution Service

Determines effective HRmax based on user preferences.
Handles USER override vs AUTO calculation priority logic.

This service implements the HRmax resolution priority:
1. USER override (max_hr_source="USER") → Use max_hr, never auto-update
2. AUTO-calculated (max_hr_source="AUTO") → Use max_hr, allow recalculation
3. STRAVA-provided (max_hr_source="STRAVA") → Use max_hr, can be auto-updated
4. None → No HRmax available → must estimate
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from src.utils.hr_zone_constants import HRMAX_ESTIMATION

logger = logging.getLogger(__name__)


class HRMaxResolutionService:
    """
    Service for determining effective HRmax based on user preferences.

    RESOLUTION PRIORITY (in order):
    1. USER override (max_hr_source="USER") → use max_hr, never auto-recalc
    2. AUTO-calculated (max_hr_source="AUTO") → use max_hr, allow recalculation
    3. STRAVA-provided (max_hr_source="STRAVA") → use max_hr, allow override
    4. None → no HRmax available → must estimate
    """

    @staticmethod
    def get_effective_max_hr(profile: Dict[str, Any]) -> Optional[int]:
        """
        Determine effective HRmax based on user preferences.

        Args:
            profile: User profile dict with max_hr and max_hr_source

        Returns:
            Effective HRmax value, or None if must be estimated
        """
        max_hr = profile.get("max_hr")
        max_hr_source = profile.get("max_hr_source")

        # Priority 1: User override (never auto-update)
        if max_hr_source == "USER":
            if max_hr and HRMaxResolutionService._validate_user_override(max_hr):
                return max_hr
            # Invalid user override - return None to trigger recalculation
            logger.warning(
                "User override HRmax is invalid, will trigger recalculation",
                extra={"max_hr": max_hr},
            )
            return None

        # Priority 2: Auto-calculated (can be updated)
        if max_hr_source == "AUTO":
            return max_hr  # May be None, which triggers recalculation

        # Priority 3: Strava-provided (can be overridden by AUTO)
        if max_hr_source == "STRAVA":
            return max_hr  # May be None

        # Priority 4: No source → must estimate
        return None

    @staticmethod
    def _validate_user_override(max_hr: int) -> bool:
        """
        Validate user-entered max_hr is in acceptable range.

        Args:
            max_hr: User-entered max HR value

        Returns:
            True if valid, False otherwise
        """
        return HRMAX_ESTIMATION["HRMAX_MIN"] <= max_hr <= HRMAX_ESTIMATION["HRMAX_MAX"]

    @staticmethod
    def should_allow_auto_recalculation(profile: Dict[str, Any]) -> bool:
        """
        Determine if HRmax can be auto-recalculated.

        Args:
            profile: User profile dict

        Returns:
            True if auto-recalc allowed, False if user override is in place
        """
        return profile.get("max_hr_source") != "USER"

    @staticmethod
    def should_recalculate_hrmax(
        profile: Dict[str, Any],
        new_activity_max_hr: Optional[int] = None,
    ) -> bool:
        """
        Determine if HRmax should be recalculated.

        Rules:
        - If max_hr_source == "USER" → never auto-recalculate
        - If max_hr_source == "AUTO" → recalculate on time threshold or new peak
        - If max_hr_source is None → always recalculate

        Args:
            profile: User profile dict
            new_activity_max_hr: Optional new max HR from recent activity

        Returns:
            True if should recalculate, False otherwise
        """
        # User override - never auto-update
        if profile.get("max_hr_source") == "USER":
            return False

        max_hr = profile.get("max_hr")
        max_hr_source = profile.get("max_hr_source")

        # No stored HRmax → must recalculate
        if not max_hr:
            return True

        # Check time-based recalc
        last_calculated = profile.get("hrmax_calculated_at")
        if last_calculated:
            try:
                if isinstance(last_calculated, str):
                    # Parse ISO format string
                    last_calculated = datetime.fromisoformat(
                        last_calculated.replace("Z", "+00:00")
                    )

                # Handle timezone-aware datetime
                if hasattr(last_calculated, "replace") and last_calculated.tzinfo:
                    last_calculated = last_calculated.replace(tzinfo=None)

                days_since = (datetime.now() - last_calculated).days
                if days_since >= HRMAX_ESTIMATION["RECALC_DAYS_THRESHOLD"]:
                    logger.debug(
                        "Time threshold reached for HRmax recalculation",
                        extra={"days_since": days_since},
                    )
                    return True
            except (ValueError, AttributeError, TypeError):
                # Unknown format or parsing error, assume needs recalculation
                logger.warning(
                    "Could not parse hrmax_calculated_at, triggering recalculation",
                    extra={"hrmax_calculated_at": last_calculated},
                )
                return True

        # Check if new peak observed (only for AUTO or None)
        if new_activity_max_hr and max_hr:
            peak_threshold = HRMAX_ESTIMATION["HRMAX_PEAK_THRESHOLD"]
            last_processed_id = profile.get("last_hrmax_activity_id")

            # Skip if we already processed this activity
            # (assuming activity_id is passed separately - for now just check threshold)
            if new_activity_max_hr > max_hr + peak_threshold:
                logger.info(
                    "New HRmax peak detected",
                    extra={
                        "new_peak": new_activity_max_hr,
                        "current_max": max_hr,
                        "threshold": peak_threshold,
                    },
                )
                return True

        return False

    @staticmethod
    def update_max_hr_data(
        profile_data: Dict[str, Any],
        new_max_hr: int,
        source: str,  # "USER", "AUTO", "STRAVA"
        confidence: Optional[str] = None,
        activity_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Prepare profile data update with HRmax and metadata.

        Args:
            profile_data: Existing profile data dict (will be modified)
            new_max_hr: New HRmax value
            source: Source of HRmax ("USER", "AUTO", "STRAVA")
            confidence: Confidence level (for AUTO source)
            activity_count: Activity count used (for AUTO source)

        Returns:
            Updated profile_data dict ready for save_user_profile()

        Raises:
            ValueError: If source is invalid or user override is out of range
        """
        # Validate input
        if source not in ["USER", "AUTO", "STRAVA"]:
            raise ValueError(f"Invalid source: {source}")

        if source == "USER":
            # Validate user override
            if not HRMaxResolutionService._validate_user_override(new_max_hr):
                raise ValueError(
                    f"Invalid user override HRmax: {new_max_hr} "
                    f"(must be {HRMAX_ESTIMATION['HRMAX_MIN']}-"
                    f"{HRMAX_ESTIMATION['HRMAX_MAX']})"
                )

        # Update profile data
        profile_data["max_hr"] = new_max_hr
        profile_data["max_hr_source"] = source

        if source == "AUTO":
            profile_data["hrmax_calculated_at"] = datetime.now()
            if confidence:
                profile_data["hrmax_confidence"] = confidence
            if activity_count is not None:
                profile_data["hrmax_activity_count"] = activity_count
        elif source == "USER":
            # Clear calculated metadata when user sets override
            profile_data["hrmax_calculated_at"] = None
            profile_data["hrmax_confidence"] = None
            profile_data["hrmax_activity_count"] = None

        return profile_data

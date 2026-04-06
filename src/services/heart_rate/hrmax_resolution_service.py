"""
HRMax resolution: separate user-entered (manual) vs activity-estimated (auto) max HR.

- max_hr_manual: value the user entered (e.g. from Strava settings).
- max_hr_auto: value estimated from runs; metadata (calculated_at, confidence, activity_count)
  applies only to this estimate.
- max_hr_active: 'manual' | 'auto' — which value drives zones and coaching.
  Auto estimates can be refreshed without overwriting manual; manual is never overwritten by AUTO.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from src.utils.hr_zone_constants import HRMAX_ESTIMATION

logger = logging.getLogger(__name__)


class HRMaxResolutionService:
    @staticmethod
    def get_effective_max_hr(profile: Dict[str, Any]) -> Optional[int]:
        """
        Return the max HR used for zones: follows max_hr_active, with safe fallbacks.
        """
        manual = profile.get("max_hr_manual")
        auto = profile.get("max_hr_auto")
        active = profile.get("max_hr_active")

        if active == "manual":
            if manual is not None and HRMaxResolutionService._validate_user_override(
                int(manual)
            ):
                return int(manual)
            if auto is not None:
                return int(auto)
            return None

        if active == "auto":
            if auto is not None:
                return int(auto)
            if manual is not None and HRMaxResolutionService._validate_user_override(
                int(manual)
            ):
                return int(manual)
            return None

        # Unset active: prefer validated manual, else auto
        if manual is not None and HRMaxResolutionService._validate_user_override(
            int(manual)
        ):
            return int(manual)
        if auto is not None:
            return int(auto)
        return None

    @staticmethod
    def _validate_user_override(max_hr: int) -> bool:
        return HRMAX_ESTIMATION["HRMAX_MIN"] <= max_hr <= HRMAX_ESTIMATION["HRMAX_MAX"]

    @staticmethod
    def should_allow_auto_recalculation(profile: Dict[str, Any]) -> bool:
        """Auto estimate can always be refreshed; manual lives in a separate column."""
        return True

    @staticmethod
    def should_recalculate_hrmax(
        profile: Dict[str, Any],
        new_activity_max_hr: Optional[int] = None,
    ) -> bool:
        """
        Whether to re-run activity-based HRmax estimation (updates max_hr_auto only).
        Uses max_hr_auto + hrmax_calculated_at, not manual.
        """
        max_auto = profile.get("max_hr_auto")

        if not max_auto:
            return True

        last_calculated = profile.get("hrmax_calculated_at")
        if last_calculated:
            try:
                if isinstance(last_calculated, str):
                    last_calculated = datetime.fromisoformat(
                        last_calculated.replace("Z", "+00:00")
                    )
                if hasattr(last_calculated, "replace") and last_calculated.tzinfo:
                    last_calculated = last_calculated.replace(tzinfo=None)
                days_since = (datetime.now() - last_calculated).days
                if days_since >= HRMAX_ESTIMATION["RECALC_DAYS_THRESHOLD"]:
                    return True
            except (ValueError, AttributeError, TypeError):
                logger.warning(
                    "Could not parse hrmax_calculated_at, triggering recalculation",
                    extra={"hrmax_calculated_at": last_calculated},
                )
                return True

        if new_activity_max_hr and max_auto:
            peak_threshold = HRMAX_ESTIMATION["HRMAX_PEAK_THRESHOLD"]
            if new_activity_max_hr > int(max_auto) + peak_threshold:
                return True

        return False

    @staticmethod
    def update_auto_hrmax(
        profile_data: Dict[str, Any],
        new_max_hr: int,
        confidence: Optional[str] = None,
        activity_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Write activity-estimated max HR + metadata; does not change manual or active."""
        profile_data["max_hr_auto"] = new_max_hr
        profile_data["hrmax_calculated_at"] = datetime.now()
        profile_data["hrmax_confidence"] = confidence
        profile_data["hrmax_activity_count"] = activity_count
        return profile_data

    @staticmethod
    def update_manual_hrmax(
        profile_data: Dict[str, Any], new_max_hr: int
    ) -> Dict[str, Any]:
        """Validate and store user-entered max HR."""
        if not HRMaxResolutionService._validate_user_override(new_max_hr):
            raise ValueError(
                f"Invalid manual HRmax: {new_max_hr} "
                f"(must be {HRMAX_ESTIMATION['HRMAX_MIN']}-"
                f"{HRMAX_ESTIMATION['HRMAX_MAX']})"
            )
        profile_data["max_hr_manual"] = new_max_hr
        return profile_data

    @staticmethod
    def update_max_hr_data(
        profile_data: Dict[str, Any],
        new_max_hr: int,
        source: str,
        confidence: Optional[str] = None,
        activity_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Backward-compatible entry: source AUTO -> update_auto_hrmax;
        USER/STRAVA -> update_manual_hrmax (STRAVA treated as manual entry).
        """
        if source == "AUTO":
            return HRMaxResolutionService.update_auto_hrmax(
                profile_data, new_max_hr, confidence, activity_count
            )
        if source in ("USER", "STRAVA"):
            HRMaxResolutionService.update_manual_hrmax(profile_data, new_max_hr)
            profile_data["hrmax_calculated_at"] = None
            profile_data["hrmax_confidence"] = None
            profile_data["hrmax_activity_count"] = None
            return profile_data
        raise ValueError(f"Invalid source: {source}")

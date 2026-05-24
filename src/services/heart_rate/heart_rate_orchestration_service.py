"""
Heart Rate Zone Orchestration Service

Coordinates HRmax estimation and zone calculation.
Handles data fetching and service orchestration.

⚠️ This is NOT a pure calculation service.
This service coordinates other services and accesses the database.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.services.heart_rate.hrmax_estimation_service import HRMaxEstimationService
from src.services.heart_rate.hrmax_resolution_service import HRMaxResolutionService
from src.services.heart_rate.estimation_helpers import (
    estimate_resting_hr_from_age_group,
)
from src.db.dao.user_profile_dao import get_user_profile, save_user_profile
from src.db.dao.user_athletes_dao import get_by_user_id
from src.smartcoach_mobile_coach.runner_profile.service import (
    get_runner_profile,
    get_runner_zone_string_for_run_type,
    refresh_runner_profile,
)
from src.smartcoach_mobile_coach.runner_profile.models import RunnerZoneProfileData
from src.utils.hr_zone_constants import (
    HR_ZONE_ISSUES,
    NEXT_ACTION_PRIORITY,
    ACCURACY_TIERS,
    HRMAX_ESTIMATION,
    RESTING_HR_ESTIMATION,
)
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class HeartRateZoneOrchestrationService:
    """
    Orchestration service that coordinates:
    - Data fetching (activities from database)
    - HRmax resolution (USER vs AUTO)
    - HRmax estimation (if needed)
    - Zone calculation

    This is the main entry point for routes.
    """

    @staticmethod
    def _runner_profile_to_legacy_zone_payload(
        runner_profile: RunnerZoneProfileData,
    ) -> Dict[str, tuple[int, int]]:
        zones: Dict[str, tuple[int, int]] = {}
        if runner_profile.hr_z1:
            zones["Z1"] = (runner_profile.hr_z1.low, runner_profile.hr_z1.high)
        if runner_profile.hr_z2:
            zones["Z2"] = (runner_profile.hr_z2.low, runner_profile.hr_z2.high)
        if runner_profile.hr_z3:
            zones["Z3"] = (runner_profile.hr_z3.low, runner_profile.hr_z3.high)
        if runner_profile.hr_z4:
            zones["Z4"] = (runner_profile.hr_z4.low, runner_profile.hr_z4.high)
        if runner_profile.hr_z5:
            zones["Z5"] = (runner_profile.hr_z5.low, runner_profile.hr_z5.high)
        return zones

    @staticmethod
    def _zone_response_from_runner_profile(
        session: Session,
        user_id: str,
        *,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        profile = get_user_profile(session, user_id)
        if not profile:
            return {
                "success": False,
                "error_code": "PROFILE_NOT_FOUND",
                "error_message": "User profile not found",
            }

        runner_profile = (
            refresh_runner_profile(session, user_id)
            if force_refresh
            else get_runner_profile(session, user_id)
        )
        if not runner_profile.calibrated:
            return {
                "success": False,
                "error_code": "MISSING_HRMAX",
                "error_message": "Max HR required. Please set it in your profile.",
            }

        return {
            "success": True,
            "hrmax": runner_profile.hrmax_used,
            "resting_hr": runner_profile.resting_hr_used,
            "resting_hr_source": profile.get("resting_hr_source"),
            "zones": HeartRateZoneOrchestrationService._runner_profile_to_legacy_zone_payload(
                runner_profile
            ),
            "confidence": profile.get("hrmax_confidence", "UNKNOWN"),
            "activity_count": profile.get("hrmax_activity_count"),
        }

    @staticmethod
    def fetch_activities_for_hrmax(
        session: Session,
        user_id: str,
        limit: int = 40,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent running activities with HR data for HRmax estimation.

        This is a data-fetching method (matches DataCollectionService pattern).

        Args:
            session: Database session
            user_id: User ID (UUID string)
            limit: Maximum number of activities to fetch

        Returns:
            List of activity dicts with max_heartrate and moving_time
        """
        logger.info(
            "Fetching activities for HRmax estimation",
            extra={"user_id": user_id, "limit": limit},
        )

        try:
            # Query activities with HR data
            # Filter to running activities with max_heartrate
            rows = (
                session.execute(
                    text(
                        """
                        SELECT
                            activity_id,
                            max_heartrate,
                            moving_time,
                            start_date
                        FROM activities
                        WHERE user_id = :user_id
                          AND type = 'Run'
                          AND max_heartrate IS NOT NULL
                          AND moving_time IS NOT NULL
                        ORDER BY start_date DESC
                        LIMIT :limit
                        """
                    ),
                    {"user_id": user_id, "limit": limit},
                )
                .mappings()
                .all()
            )

            activities = []
            for row in rows:
                activities.append(
                    {
                        "activity_id": row.get("activity_id"),
                        "max_heartrate": row.get("max_heartrate"),
                        "moving_time": row.get("moving_time"),
                        "start_date": row.get("start_date"),
                    }
                )

            logger.info(
                "Fetched activities for HRmax estimation",
                extra={"count": len(activities)},
            )

            return activities

        except Exception as e:
            logger.error(
                "Error fetching activities for HRmax estimation",
                extra={"user_id": user_id, "error": str(e)},
            )
            raise

    @staticmethod
    def sanitize_unreliable_stored_max_hr_auto(session: Session, user_id: str) -> bool:
        """
        Clear max_hr_auto when stored value is LOW confidence or diverges from
        a validated manual max. Returns True if the profile was updated.
        """
        profile = get_user_profile(session, user_id)
        if not profile or not HRMaxResolutionService.stored_max_hr_auto_is_unreliable(
            profile
        ):
            return False
        profile_data = profile.copy()
        HRMaxResolutionService.clear_auto_hrmax_fields(profile_data)
        save_user_profile(session, profile_data)
        logger.info(
            "Cleared unreliable max_hr_auto",
            extra={"user_id": user_id},
        )
        try:
            from src.smartcoach_mobile_coach.runner_profile import (
                refresh_runner_profile,
            )

            refresh_runner_profile(session, str(user_id))
        except Exception as e:
            logger.warning(
                "refresh_runner_profile after clearing max_hr_auto failed: %s",
                e,
                extra={"user_id": user_id},
            )
        return True

    @staticmethod
    def refresh_auto_hrmax_from_activities(
        session: Session,
        user_id: str,
        *,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Estimate max HR from stored runs and persist max_hr_auto (+ metadata).

        Runs even when the user already has a manual max HR, so activity-based
        max_hr_auto stays available for comparison and for switching active source.

        Respects should_recalculate_hrmax unless force=True (avoids constant
        rewrites when nothing changed).

        Does not persist estimates that are LOW confidence or diverge strongly
        from a validated manual max HR.

        Returns:
            Dict with success, updated (bool), optional hrmax, confidence,
            activity_count, error_code, error_message, reason (skip reason).
        """
        profile = get_user_profile(session, user_id)
        if not profile:
            return {
                "success": False,
                "updated": False,
                "error_code": "PROFILE_NOT_FOUND",
                "error_message": "User profile not found",
            }

        if HeartRateZoneOrchestrationService.sanitize_unreliable_stored_max_hr_auto(
            session, user_id
        ):
            profile = get_user_profile(session, user_id)
            if not profile:
                return {
                    "success": False,
                    "updated": False,
                    "error_code": "PROFILE_NOT_FOUND",
                    "error_message": "User profile not found",
                }

        activities = HeartRateZoneOrchestrationService.fetch_activities_for_hrmax(
            session, user_id
        )
        if not activities:
            return {
                "success": True,
                "updated": False,
                "reason": "no_activities",
            }

        new_peak: Optional[int] = None
        try:
            peaks = [
                int(a["max_heartrate"])
                for a in activities
                if a.get("max_heartrate") is not None
            ]
            if peaks:
                new_peak = max(peaks)
        except (TypeError, ValueError):
            new_peak = None

        if not force and not HRMaxResolutionService.should_recalculate_hrmax(
            profile,
            new_activity_max_hr=new_peak,
        ):
            return {
                "success": True,
                "updated": False,
                "reason": "not_due",
            }

        hrmax_result = HRMaxEstimationService.estimate_hrmax(activities)
        if not hrmax_result.success:
            return {
                "success": False,
                "updated": False,
                "error_code": hrmax_result.error_code,
                "error_message": hrmax_result.error_message or "Estimation failed",
                "confidence": hrmax_result.confidence,
                "activity_count": hrmax_result.activity_count,
            }

        trustworthy, reject_reason = (
            HRMaxResolutionService.auto_hrmax_estimate_is_trustworthy(
                profile,
                hrmax_result.hrmax,
                hrmax_result.confidence,
            )
        )
        if not trustworthy:
            return {
                "success": True,
                "updated": False,
                "reason": reject_reason,
                "confidence": hrmax_result.confidence,
                "activity_count": hrmax_result.activity_count,
            }

        profile_data = profile.copy()
        HRMaxResolutionService.update_auto_hrmax(
            profile_data,
            hrmax_result.hrmax,
            confidence=hrmax_result.confidence,
            activity_count=hrmax_result.activity_count,
        )
        save_user_profile(session, profile_data)

        return {
            "success": True,
            "updated": True,
            "hrmax": hrmax_result.hrmax,
            "confidence": hrmax_result.confidence,
            "activity_count": hrmax_result.activity_count,
        }

    @staticmethod
    def calculate_zones_for_user(
        session: Session,
        user_id: str,
        use_estimate: bool = False,
        force_estimate: bool = False,
    ) -> Dict[str, Any]:
        """
        Calculate HR zones for a user using Karvonen method.

        This method wraps all DB operations in a transaction to ensure data consistency.
        If any step fails, the transaction is rolled back.

        This is the main orchestration method that coordinates:
        1. Fetch user profile
        2. Resolve effective resting HR (with estimation if needed)
        3. Resolve effective HRmax (USER vs AUTO)
        4. Estimate HRmax if needed
        5. Calculate zones

        Estimation Priority (canonical order):
        1. If force_estimate=True -> always estimate (even if user RHR exists)
        2. Else if user RHR exists -> use manual RHR
        3. Else if use_estimate=True -> auto-estimate from age_group
        4. Else -> fail with "missing resting HR" error

        Args:
            session: Database session
            user_id: User ID (UUID string)
            use_estimate: If True, auto-estimate resting HR from age_group when missing
            force_estimate: If True, force estimation even if user RHR exists

        Returns:
            Dict with:
                - success: bool
                - hrmax: int (if available)
                - resting_hr: int (if available)
                - resting_hr_source: str (USER/ESTIMATED)
                - zones: dict (if calculated)
                - confidence: str (if estimated)
                - error_code: str (if error)
                - error_message: str (if error)
                - can_estimate: bool (if error, indicates if estimation possible)
                - reason: str (if error, reason estimation failed)
        """
        logger.info(
            "Calculating HR zones for user",
            extra={"user_id": user_id},
        )

        # Step 1: Get user profile
        profile = get_user_profile(session, user_id)
        if not profile:
            return {
                "success": False,
                "error_code": "PROFILE_NOT_FOUND",
                "error_message": "User profile not found",
            }

        # Step 2: Resolve resting HR (with estimation priority logic)
        resting_hr = profile.get("resting_hr")
        resting_hr_source = profile.get("resting_hr_source")
        age_group = profile.get("age_group")

        # Priority 1: Force estimate (override user value)
        if force_estimate:
            if not age_group:
                return {
                    "success": False,
                    "error_code": "MISSING_RESTING_HR",
                    "error_message": "Cannot estimate resting HR: age_group is missing.",
                    "can_estimate": False,
                    "reason": "age_group_missing",
                }

            estimated_rhr = estimate_resting_hr_from_age_group(age_group)
            if estimated_rhr is None:
                return {
                    "success": False,
                    "error_code": "MISSING_RESTING_HR",
                    "error_message": "Cannot estimate resting HR: invalid age_group.",
                    "can_estimate": False,
                    "reason": "age_group_invalid",
                }

            # Update profile with estimated RHR
            profile_data = profile.copy()
            profile_data["resting_hr"] = estimated_rhr
            profile_data["resting_hr_source"] = "ESTIMATED"
            profile_data["resting_hr_updated_at"] = datetime.now()
            save_user_profile(session, profile_data)

            resting_hr = estimated_rhr
            resting_hr_source = "ESTIMATED"

        # Priority 2: User RHR exists (use manual value)
        elif resting_hr and resting_hr_source != "ESTIMATED":
            # User has manually entered RHR - use it
            pass  # resting_hr is already set

        # Priority 3: Auto-estimate if use_estimate=True
        elif use_estimate:
            if not age_group:
                return {
                    "success": False,
                    "error_code": "MISSING_RESTING_HR",
                    "error_message": "Resting HR required. Please set it in your profile.",
                    "can_estimate": False,
                    "reason": "age_group_missing",
                }

            estimated_rhr = estimate_resting_hr_from_age_group(age_group)
            if estimated_rhr is None:
                return {
                    "success": False,
                    "error_code": "MISSING_RESTING_HR",
                    "error_message": "Resting HR required. Please set it in your profile.",
                    "can_estimate": False,
                    "reason": "age_group_invalid",
                }

            # Check if we should update existing estimate (respect MIN_RHR_UPDATE_INTERVAL)
            should_update = True
            if resting_hr_source == "ESTIMATED":
                last_updated = profile.get("resting_hr_updated_at")
                if last_updated:
                    try:
                        if isinstance(last_updated, str):
                            last_updated = datetime.fromisoformat(
                                last_updated.replace("Z", "+00:00")
                            )
                        if hasattr(last_updated, "replace") and last_updated.tzinfo:
                            last_updated = last_updated.replace(tzinfo=None)

                        days_since = (datetime.now() - last_updated).days
                        min_interval = RESTING_HR_ESTIMATION[
                            "MIN_RHR_UPDATE_INTERVAL_DAYS"
                        ]
                        should_update = days_since >= min_interval
                    except (ValueError, AttributeError, TypeError):
                        # Parse error - update anyway
                        should_update = True

            if should_update:
                # Update profile with estimated RHR
                profile_data = profile.copy()
                profile_data["resting_hr"] = estimated_rhr
                profile_data["resting_hr_source"] = "ESTIMATED"
                profile_data["resting_hr_updated_at"] = datetime.now()
                save_user_profile(session, profile_data)

                resting_hr = estimated_rhr
                resting_hr_source = "ESTIMATED"
            else:
                # Use existing estimate
                resting_hr = resting_hr  # Already set from profile

        # Priority 4: Fail - no RHR and estimation not allowed
        else:
            return {
                "success": False,
                "error_code": "MISSING_RESTING_HR",
                "error_message": "Resting HR required. Please set it in your profile.",
                "can_estimate": age_group is not None,
                "reason": "resting_hr_missing",
            }

        # Step 3: Resolve effective HRmax
        effective_max_hr = HRMaxResolutionService.get_effective_max_hr(profile)

        # Step 4: Estimate HRmax if needed
        if effective_max_hr is None:
            logger.info(
                "HRmax not available, estimating from activities",
                extra={"user_id": user_id},
            )

            # Fetch activities
            activities = HeartRateZoneOrchestrationService.fetch_activities_for_hrmax(
                session, user_id
            )

            # Estimate HRmax
            hrmax_result = HRMaxEstimationService.estimate_hrmax(activities)

            if not hrmax_result.success:
                return {
                    "success": False,
                    "error_code": hrmax_result.error_code,
                    "error_message": hrmax_result.error_message,
                    "confidence": hrmax_result.confidence,
                    "activity_count": hrmax_result.activity_count,
                }

            trustworthy, _rej = (
                HRMaxResolutionService.auto_hrmax_estimate_is_trustworthy(
                    profile,
                    hrmax_result.hrmax,
                    hrmax_result.confidence,
                )
            )
            if not trustworthy:
                return {
                    "success": False,
                    "error_code": "HRMAX_AUTO_NOT_TRUSTED",
                    "error_message": (
                        "Activity-based max HR is not reliable enough to use yet. "
                        "Set your max HR manually to match your watch or Strava."
                    ),
                    "confidence": hrmax_result.confidence,
                    "activity_count": hrmax_result.activity_count,
                }

            effective_max_hr = hrmax_result.hrmax

            # Update profile with estimated HRmax
            profile_data = profile.copy()
            profile_data = HRMaxResolutionService.update_max_hr_data(
                profile_data,
                effective_max_hr,
                source="AUTO",
                confidence=hrmax_result.confidence,
                activity_count=hrmax_result.activity_count,
            )
            if (
                profile.get("max_hr_active") is None
                and profile.get("max_hr_manual") is None
            ):
                profile_data["max_hr_active"] = "auto"

            # Save updated profile
            save_user_profile(session, profile_data)

            confidence = hrmax_result.confidence
            activity_count = hrmax_result.activity_count
        else:
            confidence = profile.get("hrmax_confidence", "UNKNOWN")
            activity_count = profile.get("hrmax_activity_count")

        # Step 5: Compute + read zones from runner profile SoT.
        try:
            return HeartRateZoneOrchestrationService._zone_response_from_runner_profile(
                session,
                user_id,
                force_refresh=True,
            )
        except Exception as e:
            logger.error(
                "Failed building zone response from runner profile",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True,
            )
            return {
                "success": False,
                "error_code": "ZONE_CALCULATION_FAILED",
                "error_message": "Failed to calculate zones",
            }

    @staticmethod
    def recalculate_zones_for_user(session: Session, user_id: str) -> Dict[str, Any]:
        """
        Force recalculation of HR zones for a user.

        This fetches fresh activities and re-estimates HRmax,
        then recalculates zones.

        Args:
            session: Database session
            user_id: User ID (UUID string)

        Returns:
            Same format as calculate_zones_for_user()
        """
        logger.info(
            "Forcing HR zone recalculation for user",
            extra={"user_id": user_id},
        )

        try:
            # Force recalculation by clearing stored HRmax
            profile = get_user_profile(session, user_id)
            if not profile:
                return {
                    "success": False,
                    "error_code": "PROFILE_NOT_FOUND",
                    "error_message": "User profile not found",
                }

            # Clear activity-based estimate so the next run re-estimates max_hr_auto
            profile_data = profile.copy()
            profile_data["max_hr_auto"] = None
            profile_data["hrmax_calculated_at"] = None
            profile_data["hrmax_confidence"] = None
            profile_data["hrmax_activity_count"] = None
            save_user_profile(session, profile_data)

            # Now calculate zones (will estimate fresh)
            # Note: calculate_zones_for_user handles its own transaction
            return HeartRateZoneOrchestrationService.calculate_zones_for_user(
                session, user_id
            )
        except Exception as e:
            # Rollback transaction on any unexpected error
            session.rollback()
            logger.error(
                "Unexpected error during HR zone recalculation, transaction rolled back",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True,
            )
            return {
                "success": False,
                "error_code": "INTERNAL_ERROR",
                "error_message": "An unexpected error occurred during zone recalculation",
            }

    @staticmethod
    def get_current_zones(session: Session, user_id: str) -> Dict[str, Any]:
        """
        Get current HR zones without recalculation.

        Returns zones if already calculated, otherwise calculates them.

        Args:
            session: Database session
            user_id: User ID (UUID string)

        Returns:
            Same format as calculate_zones_for_user()
        """
        return HeartRateZoneOrchestrationService._zone_response_from_runner_profile(
            session,
            user_id,
            force_refresh=False,
        )

    @staticmethod
    def get_hr_zone_status(session: Session, user_id: str) -> Dict[str, Any]:
        """
        Get HR zone readiness status (read-only diagnostics).

        This endpoint reports readiness WITHOUT calculating zones.
        Status endpoint MUST NEVER trigger HRmax or zone calculation.

        Returns comprehensive status information including:
        - ready: Whether zones can be calculated
        - method: Calculation method that applies
        - accuracy_tier: UX indicator (HIGH/MEDIUM/LOW)
        - next_action: Single action user should take next
        - issues: List of blockers
        - readiness: Detailed structural diagnostics
        - hrmax_source: Legacy-shaped hint (USER when active=manual, AUTO when active=auto)
        - resting_hr_source: Source of resting HR (USER/ESTIMATED)
        - activities_needed: Count of activities needed for estimation

        Critical: This is READ-ONLY. Never calls estimate_hrmax() or calculate_zones().

        Args:
            session: Database session
            user_id: User ID (UUID string)

        Returns:
            Dict with comprehensive status information
        """
        logger.info(
            "Getting HR zone status",
            extra={"user_id": user_id},
        )

        # Initialize status structure
        status = {
            "ready": False,
            "method": None,
            "accuracy_tier": None,
            "next_action": None,
            "issues": [],
            "readiness": {
                "has_strava": False,
                "has_resting_hr": False,
                "can_estimate_resting_hr": False,
                "resting_hr_reason": None,
                "has_hrmax": False,
                "has_activities": False,
                "activities_count": 0,
                "activities_needed": 0,
                "can_estimate_hrmax": False,
            },
            "hrmax_source": None,
            "resting_hr_source": None,
            "activities_needed": 0,
            "zones": None,  # Always null in status
            "confidence": None,  # Always null in status
            "accuracy_warning": None,  # Always null in status
        }

        # Step 1: Check Strava connection
        athlete_link = get_by_user_id(session, user_id)
        has_strava = athlete_link is not None
        status["readiness"]["has_strava"] = has_strava

        if not has_strava:
            status["issues"].append("strava_not_connected")
            status["next_action"] = "connect_strava"
            return status

        # Step 2: Get user profile
        profile = get_user_profile(session, user_id)
        if not profile:
            status["issues"].append("unknown")
            status["next_action"] = (
                "connect_strava"  # Profile should exist if Strava connected
            )
            return status

        # Step 3: Check resting HR
        resting_hr = profile.get("resting_hr")
        resting_hr_source = profile.get("resting_hr_source")
        age_group = profile.get("age_group")

        if resting_hr:
            status["readiness"]["has_resting_hr"] = True
            status["resting_hr_source"] = resting_hr_source or "USER"
        else:
            # Check if we can estimate
            can_estimate = False
            reason = None

            if not age_group:
                reason = "age_group_missing"
            else:
                estimated_rhr = estimate_resting_hr_from_age_group(age_group)
                if estimated_rhr is None:
                    reason = "age_group_invalid"
                else:
                    can_estimate = True
                    status["readiness"]["can_estimate_resting_hr"] = True

            status["readiness"]["can_estimate_resting_hr"] = can_estimate
            status["readiness"]["resting_hr_reason"] = reason

            if not can_estimate:
                status["issues"].append("resting_hr_missing")
                if not status["next_action"]:
                    status["next_action"] = "add_resting_hr"

        # Step 4: Check HRmax
        effective_max_hr = HRMaxResolutionService.get_effective_max_hr(profile)
        active = profile.get("max_hr_active")
        legacy_src = (
            "USER" if active == "manual" else "AUTO" if active == "auto" else None
        )

        if effective_max_hr:
            status["readiness"]["has_hrmax"] = True
            status["hrmax_source"] = legacy_src
            status["max_hr_active"] = active
            status["max_hr_manual"] = profile.get("max_hr_manual")
            status["max_hr_auto"] = profile.get("max_hr_auto")
        else:
            # Check if we can estimate HRmax
            activity_count_result = session.execute(
                text(
                    """
                    SELECT COUNT(*) as count
                    FROM activities
                    WHERE user_id = :user_id
                      AND type = 'Run'
                      AND max_heartrate IS NOT NULL
                      AND moving_time IS NOT NULL
                      AND moving_time >= :min_duration
                    """
                ),
                {
                    "user_id": user_id,
                    "min_duration": HRMAX_ESTIMATION["MIN_DURATION_SECONDS"],
                },
            ).fetchone()

            activity_count = activity_count_result.count if activity_count_result else 0
            status["readiness"]["activities_count"] = activity_count
            status["readiness"]["has_activities"] = activity_count > 0

            min_activities = HRMAX_ESTIMATION["MIN_ACTIVITIES_REQUIRED"]
            activities_needed = max(0, min_activities - activity_count)
            status["activities_needed"] = activities_needed
            status["readiness"]["activities_needed"] = activities_needed

            if activity_count >= min_activities:
                status["readiness"]["can_estimate_hrmax"] = True
            else:
                status["issues"].append("not_enough_activities")
                if not status["next_action"]:
                    status["next_action"] = "run_more_activities"

            status["issues"].append("max_hr_missing")

        # Step 5: Determine readiness and method
        has_resting_hr = status["readiness"]["has_resting_hr"]
        can_estimate_resting_hr = status["readiness"]["can_estimate_resting_hr"]
        has_hrmax = status["readiness"]["has_hrmax"]
        can_estimate_hrmax = status["readiness"]["can_estimate_hrmax"]

        # Ready if we have both resting HR and HRmax (or can estimate both)
        if has_resting_hr and has_hrmax:
            status["ready"] = True
            status["method"] = "KARVONEN"
            status["next_action"] = "view_zones"

            auto_val = profile.get("max_hr_auto")
            zones_use_auto = (
                active == "auto"
                and auto_val is not None
                and effective_max_hr is not None
                and int(auto_val) == int(effective_max_hr)
            )

            if zones_use_auto:
                hrmax_confidence = profile.get("hrmax_confidence", "UNKNOWN")
                if resting_hr_source == "USER" and hrmax_confidence == "HIGH":
                    status["accuracy_tier"] = "HIGH"
                elif resting_hr_source == "USER" or hrmax_confidence in [
                    "MEDIUM",
                    "HIGH",
                ]:
                    status["accuracy_tier"] = "MEDIUM"
                else:
                    status["accuracy_tier"] = "LOW"
            elif resting_hr_source == "USER":
                status["accuracy_tier"] = "MEDIUM"
            else:
                status["accuracy_tier"] = "LOW"

        elif has_resting_hr and can_estimate_hrmax:
            status["ready"] = True
            status["method"] = "KARVONEN"
            status["next_action"] = "view_zones"
            status["accuracy_tier"] = "MEDIUM" if resting_hr_source == "USER" else "LOW"

        elif can_estimate_resting_hr and (has_hrmax or can_estimate_hrmax):
            status["ready"] = True
            status["method"] = "ESTIMATED_KARVONEN"
            status["next_action"] = "view_zones"
            status["accuracy_tier"] = "MEDIUM"

        elif has_hrmax:
            # Has HRmax but no resting HR and can't estimate
            status["method"] = None  # Cannot use Karvonen without resting HR
            status["next_action"] = "add_resting_hr"
            status["accuracy_tier"] = None

        else:
            status["method"] = None
            status["accuracy_tier"] = None

        # Step 6: Determine final next_action using priority order
        # Only override if we don't already have a specific action
        if not status["next_action"]:
            # Apply priority order
            if "strava_not_connected" in status["issues"]:
                status["next_action"] = "connect_strava"
            elif "resting_hr_missing" in status["issues"]:
                status["next_action"] = "add_resting_hr"
            elif "not_enough_activities" in status["issues"]:
                status["next_action"] = "run_more_activities"
            elif status["ready"]:
                status["next_action"] = "view_zones"
            elif status["accuracy_tier"] == "LOW":
                status["next_action"] = "improve_accuracy"

        # Step 7: Clean up - remove issues if we're ready
        if status["ready"]:
            # Only keep non-blocking issues
            status["issues"] = [
                issue
                for issue in status["issues"]
                if issue
                not in ["resting_hr_missing", "max_hr_missing", "not_enough_activities"]
            ]

        return status

    @staticmethod
    def get_hr_zone_string(
        workout_type: str,
        user_profile: Dict[str, Any],
        session: Optional[Session] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Get HR zone string for a specific workout type (e.g., "Z2 (120-150 bpm)").

        This is a lightweight helper method that calculates a single zone string
        without triggering full zone calculation or DB writes unless necessary.

        Priority:
        1. Try to calculate zones from existing profile data (no DB write)
        2. Fall back to simple %maxHR calculation if insufficient data
        3. Only call full orchestration if absolutely necessary and session/user_id provided

        Args:
            workout_type: Workout type key (easy, steady, threshold, vo2, etc.)
            user_profile: User profile dict with max_hr, resting_hr, age_group
            session: Optional database session (only used if full calculation needed)
            user_id: Optional user ID (only used if full calculation needed)

        Returns:
            HR zone string like "Z2 (120-150 bpm)" or empty string if can't calculate
        """
        if session is not None and user_id is not None:
            return get_runner_zone_string_for_run_type(
                session,
                str(user_id),
                workout_type,
                force_refresh=False,
            )

        return ""

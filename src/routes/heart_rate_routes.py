"""
Heart Rate Zone Routes Module
==============================

Provides API endpoints for HR zone calculation using Karvonen method.

Endpoints:
----------
POST /api/heart-rate/zones/calculate
    Calculate HR zones for authenticated user

POST /api/heart-rate/zones/recalculate
    Force recalculation of HR zones

GET  /api/heart-rate/zones/current
    Get current HR zones (without recalculation)

GET  /api/heart-rate/zones/status
    Get HR zone readiness status (read-only diagnostics)

Dependencies:
-------------
- HeartRateZoneOrchestrationService: Main service for zone calculation
- requires_auth: JWT authentication decorator
- error_response, success_response: Standardized response utilities
"""

import logging
from flask import Blueprint, g
from sqlalchemy.orm import Session

from src.services.heart_rate import HeartRateZoneOrchestrationService
from src.utils.auth0_jwt import requires_auth
from src.db.db_session import get_session
from src.utils.response_utils import error_response, success_response

logger = logging.getLogger(__name__)

heart_rate_bp = Blueprint("heart_rate", __name__, url_prefix="/api/heart-rate")


@heart_rate_bp.post("/zones/calculate")
@requires_auth
def calculate_hr_zones():
    """
    Calculate HR zones for authenticated user using Karvonen method.

    This endpoint:
    - Fetches user profile and activities
    - Estimates HRmax if needed
    - Estimates resting HR if use_estimate=True and resting HR is missing
    - Calculates Karvonen zones
    - Returns zones with confidence level

    Query Parameters:
        use_estimate (bool): If True, auto-estimate resting HR from age_group when missing
        force_estimate (bool): If True, force estimation even if user RHR exists

    Returns:
        JSON response with zones or error
    """
    from flask import request

    user_id = g.user_id
    session = get_session()

    # Get query parameters
    use_estimate = request.args.get("use_estimate", "false").lower() == "true"
    force_estimate = request.args.get("force_estimate", "false").lower() == "true"

    try:
        logger.info(
            "Calculating HR zones for user",
            extra={
                "user_id": user_id,
                "use_estimate": use_estimate,
                "force_estimate": force_estimate,
            },
        )

        result = HeartRateZoneOrchestrationService.calculate_zones_for_user(
            session,
            str(user_id),
            use_estimate=use_estimate,
            force_estimate=force_estimate,
        )

        if not result.get("success"):
            return error_response(
                result.get("error_message", "Failed to calculate HR zones"),
                error_code=result.get("error_code", "HR_ZONE_CALCULATION_ERROR"),
                status_code=400,
                details={
                    "confidence": result.get("confidence"),
                    "activity_count": result.get("activity_count"),
                },
            )

        return success_response(
            {
                "hrmax": result.get("hrmax"),
                "resting_hr": result.get("resting_hr"),
                "resting_hr_source": result.get("resting_hr_source"),
                "zones": result.get("zones"),
                "confidence": result.get("confidence"),
                "activity_count": result.get("activity_count"),
            },
            message="HR zones calculated successfully",
        )

    except Exception as e:
        logger.error(
            "Error calculating HR zones",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True,
        )
        return error_response(
            "Internal server error while calculating HR zones",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
    finally:
        session.close()


@heart_rate_bp.post("/zones/recalculate")
@requires_auth
def recalculate_hr_zones():
    """
    Force recalculation of HR zones for authenticated user.

    This clears stored HRmax and forces fresh estimation from activities.

    Returns:
        JSON response with recalculated zones or error
    """
    user_id = g.user_id
    session = get_session()

    try:
        logger.info(
            "Recalculating HR zones for user",
            extra={"user_id": user_id},
        )

        result = HeartRateZoneOrchestrationService.recalculate_zones_for_user(
            session, str(user_id)
        )

        if not result.get("success"):
            return error_response(
                result.get("error_message", "Failed to recalculate HR zones"),
                error_code=result.get("error_code", "HR_ZONE_RECALCULATION_ERROR"),
                status_code=400,
                details={
                    "confidence": result.get("confidence"),
                    "activity_count": result.get("activity_count"),
                },
            )

        return success_response(
            {
                "hrmax": result.get("hrmax"),
                "resting_hr": result.get("resting_hr"),
                "zones": result.get("zones"),
                "confidence": result.get("confidence"),
                "activity_count": result.get("activity_count"),
            },
            message="HR zones recalculated successfully",
        )

    except Exception as e:
        logger.error(
            "Error recalculating HR zones",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True,
        )
        return error_response(
            "Internal server error while recalculating HR zones",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
    finally:
        session.close()


@heart_rate_bp.get("/zones/current")
@requires_auth
def get_current_hr_zones():
    """
    Get current HR zones for authenticated user without recalculation.

    Returns existing zones if available, otherwise calculates them.

    Returns:
        JSON response with current zones or error
    """
    user_id = g.user_id
    session = get_session()

    try:
        logger.info(
            "Getting current HR zones for user",
            extra={"user_id": user_id},
        )

        result = HeartRateZoneOrchestrationService.get_current_zones(
            session, str(user_id)
        )

        if not result.get("success"):
            return error_response(
                result.get("error_message", "Failed to get HR zones"),
                error_code=result.get("error_code", "HR_ZONE_ERROR"),
                status_code=400,
            )

        return success_response(
            {
                "hrmax": result.get("hrmax"),
                "resting_hr": result.get("resting_hr"),
                "zones": result.get("zones"),
                "confidence": result.get("confidence"),
                "activity_count": result.get("activity_count"),
            },
            message="HR zones retrieved successfully",
        )

    except Exception as e:
        logger.error(
            "Error getting current HR zones",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True,
        )
        return error_response(
            "Internal server error while getting HR zones",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )
    finally:
        session.close()

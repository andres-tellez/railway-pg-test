"""
Pace Zones Routes Module
========================

Provides API endpoint for retrieving user's personalized pace zones.

Endpoint:
---------
GET /api/pace-zones
    Returns user's current pace zones calculated from recent performance.

Response:
---------
{
    "easy": {"min": 558.1, "max": 618.1},
    "steady": {"min": 543.1, "max": 553.1},
    "marathon": {"pace": 513.1},
    "threshold": {"min": 483.1, "max": 493.1},
    "updatedAt": "2025-12-10T02:39:38Z",
    "source": "6-week lookback",
    "medianEasyPace": 573.07
}

Dependencies:
-------------
- requires_auth: JWT authentication decorator
- get_runner_profile: Runner profile service

Author: SmartCoach Development Team
Last Updated: December 2025
"""

from flask import Blueprint, jsonify, g
from src.db.db_session import get_session
from src.utils.auth0_jwt import requires_auth
from src.smartcoach_mobile_coach.runner_profile import get_runner_profile
from datetime import datetime
from src.utils.logger import get_logger

logger = get_logger(__name__)

pace_zones_bp = Blueprint("pace_zones", __name__, url_prefix="/api/pace-zones")


@pace_zones_bp.get("/")
@requires_auth
def get_pace_zones():
    """
    Get user's current pace zones.

    Calculates pace zones using the same logic as plan generation:
    - Performance-based calculation from recent runs (preferred)
    - Falls back to calibration if insufficient data

    Returns:
        JSON response with pace zones in seconds per mile
    """
    try:
        # user_id is already resolved by @requires_auth.
        user_id = str(g.user_id)

        session = get_session()
        try:
            profile = get_runner_profile(session, user_id)
            if not profile.calibrated or not profile.pace_z2:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Runner profile pace zones unavailable",
                        }
                    ),
                    404,
                )

            # Format response
            response = {
                "easy": {
                    "min": round(profile.pace_z2.low_sec, 1),
                    "max": round(profile.pace_z2.high_sec, 1),
                },
                "steady": {
                    "min": (
                        round(profile.pace_z3.low_sec, 1) if profile.pace_z3 else None
                    ),
                    "max": (
                        round(profile.pace_z3.high_sec, 1) if profile.pace_z3 else None
                    ),
                },
                "marathon": {
                    "pace": (
                        round(profile.pace_z4.low_sec, 1) if profile.pace_z4 else None
                    )
                },
                "threshold": {
                    "min": (
                        round(profile.pace_z4.low_sec, 1) if profile.pace_z4 else None
                    ),
                    "max": (
                        round(profile.pace_z4.high_sec, 1) if profile.pace_z4 else None
                    ),
                },
                "updatedAt": datetime.utcnow().isoformat() + "Z",
                "source": profile.pace_source or "runner_profile",
            }

            logger.info(
                f"✅ [Pace Zones API] Retrieved pace zones for user {user_id}: "
                f"Easy={response['easy']['min']}-{response['easy']['max']}s/mi"
            )

            return jsonify(response), 200

        except ValueError as e:
            logger.error(f"❌ [Pace Zones API] Validation error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 400
        except RuntimeError as e:
            logger.error(f"❌ [Pace Zones API] Calculation error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
        except Exception as e:
            logger.exception(f"❌ [Pace Zones API] Unexpected error: {e}")
            return (
                jsonify(
                    {"status": "error", "message": "Failed to calculate pace zones"}
                ),
                500,
            )
        finally:
            session.close()

    except Exception as e:
        logger.exception(f"❌ [Pace Zones API] Exception: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500

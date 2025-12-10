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
- get_initial_pace_seed: Pace calculation service
- get_active_plan: Plan DAO (optional, for week1_long)

Author: SmartCoach Development Team
Last Updated: December 2025
"""

from flask import Blueprint, jsonify
from src.db.db_session import get_session
from src.utils.auth0_jwt import requires_auth
from src.utils.auth_helpers import get_user_id_from_request
from src.services.training_plan.pace import get_initial_pace_seed
from src.db.dao.plans_dao import get_active_plan
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
        user_id, error = get_user_id_from_request()
        if error:
            return error

        # Convert UUID to string for validation
        user_id = str(user_id)

        session = get_session()
        try:
            # Try to get week1_long from active plan if available
            week1_long = None
            plan = get_active_plan(session, user_id)
            if plan and plan.workouts:
                # Find first week's long run
                first_week_workouts = sorted(plan.workouts, key=lambda w: w.date)[:7]
                long_runs = [
                    w.miles
                    for w in first_week_workouts
                    if w.workout_type in ("Long Run", "long") and w.miles
                ]
                if long_runs:
                    week1_long = max(long_runs)

            # Calculate pace zones
            pace_seed = get_initial_pace_seed(
                session=session,
                user_id=user_id,
                week1_long=week1_long,
                lookback_weeks=6,  # Default 6 weeks
            )

            # Format response
            response = {
                "easy": {
                    "min": round(pace_seed.E_min, 1),
                    "max": round(pace_seed.E_max, 1),
                },
                "steady": {
                    "min": round(pace_seed.S_min, 1),
                    "max": round(pace_seed.S_max, 1),
                },
                "marathon": {"pace": round(pace_seed.M, 1)},
                "threshold": {
                    "min": round(pace_seed.T_min, 1),
                    "max": round(pace_seed.T_max, 1),
                },
                "updatedAt": datetime.utcnow().isoformat() + "Z",
                "source": "6-week lookback",
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

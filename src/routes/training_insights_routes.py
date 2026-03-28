"""Training insights REST API — serves precomputed weekly insights to mobile."""

import logging

from flask import Blueprint, g, jsonify

from src.db.db_session import get_session
from src.smartcoach_mobile_coach.weekly_insights_service import (
    get_latest_weekly_insight,
)
from src.utils.auth0_jwt import requires_auth

logger = logging.getLogger(__name__)

training_insights_bp = Blueprint(
    "training_insights", __name__, url_prefix="/api/training-insights"
)


@training_insights_bp.get("/weekly")
@requires_auth
def weekly_insight():
    """
    Return the most recent weekly training insight for the authenticated user.
    Precomputed by the Monday cron job — no heavy computation on request.
    """
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)
        if not internal_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        result = get_latest_weekly_insight(session, str(internal_user_id))
        return jsonify(result), 200

    except Exception as e:
        logger.error("Error fetching weekly insight: %s", e, exc_info=True)
        return jsonify({"error": "Failed to fetch weekly insight"}), 500
    finally:
        session.close()

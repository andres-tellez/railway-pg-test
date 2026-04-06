"""Training insights REST API — serves precomputed weekly insights to mobile."""

import logging

from flask import Blueprint, g, jsonify, request

from src.db.db_session import get_session
from src.smartcoach_mobile_coach.weekly_insights_service import (
    get_latest_weekly_insight,
    get_weekly_insight_history,
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
    Precomputed by the Sunday metrics scheduler (weekly insights step) — no heavy computation on request.
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


@training_insights_bp.get("/weekly-history")
@requires_auth
def weekly_insight_history():
    """Return the last N weeks of HR drift data plus zone thresholds for charting."""
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)
        if not internal_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        weeks = request.args.get("weeks", 6, type=int)
        result = get_weekly_insight_history(session, str(internal_user_id), weeks)
        return jsonify(result), 200

    except Exception as e:
        logger.error("Error fetching weekly insight history: %s", e, exc_info=True)
        return jsonify({"error": "Failed to fetch insight history"}), 500
    finally:
        session.close()

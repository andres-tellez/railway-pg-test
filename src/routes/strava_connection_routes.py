"""
strava_connection_routes.py

Routes for managing Strava connection/disconnection.
"""

import logging
from flask import Blueprint, jsonify, g
from src.utils.auth0_jwt import requires_auth
from src.db.db_session import get_session
from src.db.dao.user_athletes_dao import get_by_user_id, delete_by_user_id
from src.db.dao.token_dao import delete_tokens_sa
from src.db.dao.user_identity_dao import resolve_user_id_from_auth_provider
from src.db.models.activities import Activity

logger = logging.getLogger(__name__)

strava_connection_bp = Blueprint("strava_connection", __name__, url_prefix="/api")


@strava_connection_bp.delete("/strava/disconnect")
@requires_auth
def disconnect_strava():
    """
    Disconnect Strava account from user.

    This will:
    1. Delete Strava API tokens (revokes access)
    2. Delete user-athlete link
    3. Keep existing activities (they're already synced)
    4. Keep training plans (they don't require active Strava connection)

    Users can reconnect anytime by going through OAuth flow again.

    Returns:
        JSON with disconnect status and what was deleted/retained
    """
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)

        if not internal_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Get athlete link to find athlete_id
        athlete_link = get_by_user_id(internal_user_id)

        if not athlete_link:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "No Strava account connected",
                        "deleted": {"tokens": 0, "athlete_link": False},
                        "retained": {
                            "activities": 0,
                            "plans": "All training plans remain accessible",
                        },
                    }
                ),
                404,
            )

        athlete_id = athlete_link.athlete_id

        # Count activities before deletion (for response)
        activity_count = (
            session.query(Activity).filter_by(user_id=internal_user_id).count()
        )

        # 1. Delete tokens (revokes API access)
        tokens_deleted = delete_tokens_sa(session, athlete_id)
        logger.info(
            f"Deleted {tokens_deleted} token(s) for athlete {athlete_id} "
            f"(user {internal_user_id})"
        )

        # 2. Delete user-athlete link
        link_deleted = delete_by_user_id(internal_user_id)
        logger.info(
            f"Deleted athlete link for user {internal_user_id} "
            f"(athlete {athlete_id})"
        )

        session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Strava account disconnected successfully",
                    "deleted": {"tokens": tokens_deleted, "athlete_link": link_deleted},
                    "retained": {
                        "activities": activity_count,
                        "message": (
                            f"Your {activity_count} synced activities remain in your account. "
                            "Training plans and metrics based on these activities are still accessible. "
                            "To sync new activities, reconnect Strava."
                        ),
                    },
                    "reconnect": {
                        "message": "You can reconnect Strava anytime via Settings or the Setup page",
                        "url": "/setup",
                    },
                }
            ),
            200,
        )

    except Exception as e:
        session.rollback()
        logger.error(
            f"Error disconnecting Strava for user {internal_user_id}: {e}",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to disconnect Strava account",
                    "detail": str(e),
                }
            ),
            500,
        )
    finally:
        session.close()


@strava_connection_bp.get("/strava/status")
@requires_auth
def get_strava_status():
    """
    Get current Strava connection status.

    Returns:
        JSON with connection status, athlete info, and activity count
    """
    session = get_session()
    try:
        internal_user_id = getattr(g, "user_id", None)

        if not internal_user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Get athlete link
        athlete_link = get_by_user_id(internal_user_id)

        if not athlete_link:
            return (
                jsonify({"connected": False, "message": "No Strava account connected"}),
                200,
            )

        # Count activities
        activity_count = (
            session.query(Activity).filter_by(user_id=internal_user_id).count()
        )

        return (
            jsonify(
                {
                    "connected": True,
                    "athlete_id": athlete_link.athlete_id,
                    "connected_at": (
                        athlete_link.created_at.isoformat()
                        if athlete_link.created_at
                        else None
                    ),
                    "activity_count": activity_count,
                    "message": f"Connected to Strava. {activity_count} activities synced.",
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(
            f"Error fetching Strava status for user {internal_user_id}: {e}",
            exc_info=True,
        )
        return (
            jsonify({"error": "Failed to fetch Strava status", "detail": str(e)}),
            500,
        )
    finally:
        session.close()

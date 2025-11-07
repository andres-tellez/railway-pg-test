"""
Auth Debug Routes
================

Debug and monitoring utilities for authentication (dev only).

⚠️ These endpoints should be disabled in production or protected with admin auth.
"""

from flask import Blueprint, request, session as flask_session
import traceback
import logging
from flask import jsonify

from src.db.db_session import get_session
from src.utils.response_utils import (
    success_response,
    internal_error_response,
)

auth_debug_bp = Blueprint("auth_debug", __name__, url_prefix="/auth")
logger = logging.getLogger(__name__)


@auth_debug_bp.route("/debug/set", methods=["GET"])
def debug_set_cookie():
    """
    Manually set a debug athlete_id in session (dev only).

    ⚠️ This should only be available in development environments.
    """
    flask_session["athlete_id"] = "debug-athlete"
    flask_session.permanent = True
    return success_response(
        data={"status": "set", "session": dict(flask_session)},
        message="Debug session set",
    )


@auth_debug_bp.route("/debug/show", methods=["GET"])
def debug_show_cookie():
    """
    Show current request cookies + session contents (dev only).

    ⚠️ This should only be available in development environments.
    """
    return success_response(
        data={"request_cookies": dict(request.cookies), "session": dict(flask_session)},
        message="Debug session info",
    )


@auth_debug_bp.route("/monitor-tokens", methods=["GET"])
def monitor_tokens():
    """
    List all tokens with their expiry (for debugging).

    ⚠️ This endpoint exposes sensitive token information.
       Should be protected with admin authentication in production.
    """
    session = get_session()
    try:
        rows = session.execute(
            "SELECT athlete_id, expires_at FROM tokens ORDER BY expires_at"
        ).fetchall()
        data = [
            {"athlete_id": r.athlete_id, "expires_at": str(r.expires_at)} for r in rows
        ]
        return success_response(data=data, message="Token monitoring data")
    except Exception as e:
        logger.exception("Error monitoring tokens")
        return internal_error_response("Failed to monitor tokens", log_error=e)
    finally:
        session.close()

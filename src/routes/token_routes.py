"""
Token Management Routes
======================

Handles Strava token refresh and logout operations.

Responsibilities:
- Refresh expired Strava tokens
- Delete Strava tokens (logout)
"""

from flask import Blueprint, request, g
import traceback
import logging

from src.db.db_session import get_session
from src.utils.auth0_jwt import verify_and_decode, requires_auth
from src.utils.response_utils import (
    error_response,
    unauthorized_response,
    internal_error_response,
    success_response,
)
from src.utils.auth_rate_limiter import rate_limit_auth
from src.utils.audit_logger import log_token_refresh, log_logout
import src.services.token_service as token_service

token_bp = Blueprint("token", __name__, url_prefix="/auth")
logger = logging.getLogger(__name__)


@token_bp.route("/refresh/<int:athlete_id>", methods=["POST"])
@requires_auth
@rate_limit_auth("token_refresh")
def refresh_token(athlete_id):
    """
    Force refresh Strava tokens if expired.

    Requires valid Auth0 JWT in Authorization header.
    Automatically rotates refresh tokens for security.
    """
    session = get_session()
    try:
        user_id = getattr(g, "user_id", None)

        refreshed = token_service.refresh_token_if_expired(session, athlete_id)

        # Log token refresh with user_id
        log_token_refresh(
            user_id=user_id,
            athlete_id=str(athlete_id),
            success=True,
            details={"refreshed": refreshed},
        )

        return success_response(
            data={"refreshed": refreshed}, message="Token refreshed successfully"
        )

    except ValueError as e:
        # Token not found or revoked
        user_id = getattr(g, "user_id", None)
        log_token_refresh(
            user_id=user_id,
            athlete_id=str(athlete_id),
            success=False,
            details={"error": str(e)},
        )
        return error_response(str(e), status_code=404, error_code="TOKEN_NOT_FOUND")
    except Exception as e:
        logger.exception(f"Error refreshing token for athlete {athlete_id}")
        user_id = getattr(g, "user_id", None)
        log_token_refresh(
            user_id=user_id,
            athlete_id=str(athlete_id),
            success=False,
            details={"error": str(e)},
        )
        return internal_error_response("Failed to refresh token", log_error=e)
    finally:
        session.close()


@token_bp.route("/logout/<int:athlete_id>", methods=["POST"])
@requires_auth
def logout(athlete_id):
    """
    Logout athlete by revoking stored Strava tokens.

    Uses soft delete (revocation) to maintain audit trail.
    Tokens are marked as revoked but record is kept.
    """
    session = get_session()
    try:
        user_id = getattr(g, "user_id", None)

        # Use revocation instead of hard delete (better for audit trail)
        revoked = token_service.revoke_athlete_tokens(session, athlete_id)

        if not revoked:
            # If no token found or already revoked, try hard delete
            deleted = token_service.delete_athlete_tokens(session, athlete_id)
            if deleted:
                logger.info(
                    f"Deleted tokens for athlete {athlete_id} (no existing record to revoke)"
                )

        # Log logout event
        log_logout(user_id=user_id)

        return success_response(
            data={"revoked": revoked}, message="Logged out successfully"
        )

    except Exception as e:
        logger.exception(f"Error logging out athlete {athlete_id}")
        return internal_error_response("Failed to logout", log_error=e)
    finally:
        session.close()

"""
Strava OAuth Routes
==================

Handles Strava OAuth flow for connecting user's Strava account.

Responsibilities:
- Initiate Strava OAuth flow
- Handle Strava OAuth callbacks (GET and POST)
- Exchange authorization codes for tokens
- Link Strava athletes to users
- Trigger activity ingestion
"""

from flask import Blueprint, request, redirect, jsonify, g, session
import os
import re
import traceback
import threading
import logging

from src.db.db_session import get_session
from src.utils.auth0_jwt import verify_and_decode, requires_auth
from src.utils.response_utils import (
    error_response,
    validation_error_response,
    internal_error_response,
)
from src.utils.auth_rate_limiter import rate_limit_auth
from src.utils.oauth_state_manager import generate_state_token, validate_state_token
from src.utils.audit_logger import log_oauth_callback
from src.db.dao.user_athletes_dao import get_by_user_id, delete_by_user_id
from src.db.dao.token_dao import delete_tokens_sa
from src.db.models.activities import Activity
import src.services.token_service as token_service
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)

strava_bp = Blueprint("strava", __name__, url_prefix="/auth")
# Separate blueprint for connection management (uses /api prefix to match frontend)
strava_connection_bp = Blueprint("strava_connection", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


@strava_bp.route("/strava-login", methods=["GET"])
@rate_limit_auth("login")
def strava_login_redirect():
    """
    Step 1: Start Strava OAuth login.

    Reads Auth0 JWT from cookie (or fallback query param) to get `auth0_sub`.
    Redirects user to Strava with `state=auth0_sub`.
    """
    logger.info("Strava login redirect triggered")

    redirect_uri = (os.getenv("STRAVA_REDIRECT_URI") or "").strip().rstrip(";")

    # Auto-fix HTTP to HTTPS for localhost if app is running on HTTPS
    if redirect_uri.startswith("http://localhost:5000") or redirect_uri.startswith(
        "http://127.0.0.1:5000"
    ):
        redirect_uri = redirect_uri.replace("http://", "https://")
        logger.warning(f"Auto-converted redirect URI to HTTPS: {redirect_uri}")

    client_id = os.getenv("STRAVA_CLIENT_ID") or ""

    if not client_id:
        return error_response(
            "STRAVA_CLIENT_ID not configured",
            status_code=500,
            error_code="CONFIG_ERROR",
        )

    # Extract user identity from cookie or fallback param
    jwt_cookie = request.cookies.get("user_jwt")
    auth0_sub = request.args.get("user_id")  # fallback

    if jwt_cookie:
        try:
            payload = verify_and_decode(jwt_cookie)
            auth0_sub = payload.get("sub") or auth0_sub
        except Exception as e:
            logger.warning(f"Failed to decode JWT cookie: {e}")

    # Generate cryptographically secure state token for CSRF protection
    if auth0_sub:
        state_token = generate_state_token(auth0_sub)
    else:
        # Fallback: generate state without user_id (less secure but better than nothing)
        state_token = generate_state_token("unknown")
        logger.warning("No auth0_sub found, using generic state token")

    # Build Strava OAuth URL with secure state token
    url = (
        "https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read,activity:read_all"
        f"&state={state_token}"
    )

    logger.info(f"Redirecting to Strava OAuth with secure state token")
    return redirect(url)


@strava_bp.route("/strava/connect", methods=["GET"])
def strava_connect_alias():
    """Alias route to trigger Strava OAuth flow (for flexibility in frontend)."""
    logger.info("Strava connect alias triggered")
    return strava_login_redirect()


@strava_bp.route("/callback", methods=["GET"])
@rate_limit_auth("oauth_callback")
def strava_callback_compatibility():
    """
    Compatibility route for /auth/callback redirect URI.

    Handles Strava OAuth callbacks that use the older /auth/callback path.
    This allows existing Strava portal configurations to continue working.
    """
    logger.info(
        "Compatibility route /auth/callback - forwarding to strava_callback_get"
    )
    return strava_callback_get()


@strava_bp.route("/strava/callback", methods=["GET"])
@rate_limit_auth("oauth_callback")
def strava_callback_get():
    """
    Step 2 (Browser Redirect): Strava calls this after user approval.

    - Exchanges code for tokens
    - Links athlete ↔ user
    - Triggers ingestion in background (with fresh session)
    - Redirects back to frontend with query param
    """
    session = get_session()
    try:
        code = request.args.get("code")
        state = request.args.get("state")

        logger.info(
            f"Received Strava callback - code={'present' if code else 'missing'}, state={'present' if state else 'missing'}"
        )

        if not code or not state:
            return validation_error_response(
                "Missing code or state parameter",
                errors={"code": "required", "state": "required"},
            )

        # Validate state token to prevent CSRF attacks
        is_valid, error_msg = validate_state_token(state)
        if not is_valid:
            logger.warning(f"OAuth state validation failed: {error_msg}")
            log_oauth_callback(
                user_id=None,
                athlete_id=None,
                success=False,
                provider="strava",
                details={"error": error_msg, "reason": "state_validation_failed"},
            )
            return error_response(
                "Invalid or expired state parameter",
                status_code=403,
                error_code="CSRF_PROTECTION",
            )

        # Get user_id from session (stored during state generation)
        expected_user_id = session.get("oauth_state_user_id")

        try:
            athlete_id, user_id = process_strava_callback(
                session, code, expected_user_id or state
            )
            log_oauth_callback(
                user_id=user_id,
                athlete_id=str(athlete_id),
                success=True,
                provider="strava",
            )
        except Exception as e:
            logger.exception(f"Failed to process Strava callback: {e}")
            raise RuntimeError(f"Failed to process callback: {e}")

        session.commit()
        logger.info(f"Successfully linked athlete={athlete_id} to user={user_id}")

    except Exception as e:
        session.rollback()
        logger.exception("Error processing Strava callback")
        return internal_error_response("Failed to process Strava callback", log_error=e)
    finally:
        session.close()

    # Ingestion runs with a brand new session
    def background_job():
        try:
            logger.info(f"Starting ingestion for user={user_id}, athlete={athlete_id}")
            run_full_ingestion_and_enrichment(None, athlete_id, user_id=user_id)
        except Exception as e:
            logger.error(
                f"Ingestion failed for athlete={athlete_id}: {e}", exc_info=True
            )

    threading.Thread(target=background_job, daemon=True).start()

    frontend_redirect = (
        (os.getenv("FRONTEND_REDIRECT") or "https://localhost:5173/setup")
        .strip()
        .rstrip("/")
    )
    logger.info(f"Redirecting user to: {frontend_redirect}")
    return redirect(f"{frontend_redirect}?strava=connected")


@strava_bp.route("/strava/callback", methods=["POST"])
@rate_limit_auth("oauth_callback")
def strava_callback_post():
    """
    Step 2 (API Exchange): Alternative to GET callback.

    Allows frontend to POST { code, sub } directly.
    Returns both user_id + athlete_id so frontend can track progress.
    """
    data = request.get_json() or {}
    code = data.get("code")
    auth0_sub = data.get("sub")

    if not code or not auth0_sub:
        return validation_error_response(
            "Missing code or sub", errors={"code": "required", "sub": "required"}
        )

    athlete_id = None
    user_id = None
    try:
        with get_session() as session:
            athlete_id, user_id = process_strava_callback(session, code, auth0_sub)
            session.commit()
            logger.info(f"Successfully linked athlete={athlete_id} to user={user_id}")
            log_oauth_callback(
                user_id=user_id,
                athlete_id=str(athlete_id),
                success=True,
                provider="strava",
            )
    except Exception as e:
        logger.exception("Error processing Strava callback (POST)")
        log_oauth_callback(
            user_id=auth0_sub,
            athlete_id=None,
            success=False,
            provider="strava",
            details={"error": str(e)},
        )
        return internal_error_response("Failed to process Strava callback", log_error=e)

    # Ingestion runs in fresh session
    def background_job():
        db = get_session()
        try:
            logger.info(f"Starting ingestion for user={user_id}, athlete={athlete_id}")
            run_full_ingestion_and_enrichment(None, athlete_id, user_id=user_id)
        except Exception as e:
            logger.error(
                f"Ingestion failed for athlete={athlete_id}: {e}", exc_info=True
            )
        finally:
            db.close()

    threading.Thread(target=background_job, daemon=True).start()

    # Return both IDs
    from flask import jsonify

    return (
        jsonify(
            {
                "status": "success",
                "user_id": user_id,
                "athlete_id": athlete_id,
            }
        ),
        200,
    )


def process_strava_callback(session, code, state_or_sub, create_if_missing=True):
    """
    Shared Strava OAuth processing logic.

    Handles:
    1. Accepts either internal user_id (UUID) or auth0_sub in `state_or_sub`.
    2. If UUID → use directly.
    3. If auth0_sub → resolve to user_id.
    4. Exchanges code for Strava tokens.
    5. Links athlete ↔ user.

    ⚠️ Does NOT trigger ingestion — caller should do that
       after closing the session, with a fresh one.
    """
    if not code or not state_or_sub:
        raise ValueError("Missing OAuth code or user identifier")

    logger.info(
        f"Processing Strava callback: code={'present'}, state_or_sub={'present'}"
    )

    # Simple regex check for UUID format
    uuid_pattern = re.compile(r"^[0-9a-fA-F-]{36}$")

    if uuid_pattern.match(state_or_sub):
        user_id = state_or_sub  # Already internal user_id
    else:
        # Fallback: treat as auth0_sub
        from src.utils.auth_helpers import get_user_id_from_request

        # Create a minimal claims dict with just the sub
        claims = {"sub": state_or_sub}
        user_id, error = get_user_id_from_request(
            claims, create_if_missing=create_if_missing
        )
        if error:
            # Convert error response to ValueError for consistency with existing code
            raise ValueError(
                f"User not found or could not be created: {error[0].json.get('error', 'Unknown error')}"
            )

    redirect_uri = (os.getenv("STRAVA_REDIRECT_URI") or "").strip().rstrip(";")

    # Auto-fix HTTP to HTTPS for localhost if app is running on HTTPS
    if redirect_uri.startswith("http://localhost:5000") or redirect_uri.startswith(
        "http://127.0.0.1:5000"
    ):
        redirect_uri = redirect_uri.replace("http://", "https://")

    try:
        athlete_id, user_id = token_service.store_tokens_from_callback(
            code=code,
            session=session,
            redirect_uri=redirect_uri,
            user_id=user_id,
        )
        logger.info(f"Stored tokens for athlete {athlete_id}")
    except Exception as e:
        raise RuntimeError(f"Token exchange failed: {e}")

    return athlete_id, user_id


# ============================================================================
# Strava Connection Management Routes
# ============================================================================
# These routes handle disconnecting and checking connection status.
# They use /api prefix to match frontend expectations.


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

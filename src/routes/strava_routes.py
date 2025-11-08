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

from flask import Blueprint, request, redirect, g, session
import os
import traceback
import logging

from src.db.db_session import get_session
from src.utils.config import config
from src.utils.auth0_jwt import verify_and_decode, requires_auth
from src.utils.response_utils import (
    error_response,
    validation_error_response,
    internal_error_response,
    success_response,
    unauthorized_response,
    not_found_response,
)
from src.utils.strava_validators import validate_oauth_code
from src.utils.auth_rate_limiter import rate_limit_auth
from src.utils.oauth_state_manager import generate_state_token, validate_state_token
from src.utils.audit_logger import log_oauth_callback
from src.utils.strava_exceptions import (
    StravaOAuthError,
    StravaTokenError,
    StravaAPIError,
    StravaOAuthCodeExchangeError,
)
from src.db.dao.user_athletes_dao import get_by_user_id, delete_by_user_id
from src.db.dao.token_dao import delete_tokens_sa
from src.db.models.activities import Activity
import src.services.token_service as token_service
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)
from src.utils.strava_helpers import (
    get_authenticated_user_id,
    get_user_athlete_link,
    get_authenticated_user_with_athlete,
    run_background_job,
    get_frontend_redirect_url,
    is_uuid_format,
    normalize_redirect_uri,
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
    try:
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
        user_id_param = request.args.get("user_id")  # Could be UUID or auth0_sub

        auth0_sub = None
        internal_user_id = None

        # Check if user_id_param is a UUID (internal user_id) or auth0_sub
        if user_id_param:
            if is_uuid_format(user_id_param):
                internal_user_id = user_id_param
                logger.info(f"Received internal user_id (UUID): {internal_user_id}")
            else:
                auth0_sub = user_id_param
                logger.info(f"Received auth0_sub: {auth0_sub}")

        if jwt_cookie:
            try:
                audience = os.getenv("AUTH0_ID_TOKEN_AUDIENCE") or os.getenv(
                    "AUTH0_CLIENT_ID"
                )
                payload = verify_and_decode(jwt_cookie, audience=audience)
                auth0_sub = payload.get("sub") or auth0_sub
            except Exception as e:
                logger.warning(f"Failed to decode JWT cookie: {e}")

        # If we have internal_user_id but no auth0_sub, we can still proceed
        # The state token will use the internal_user_id
        user_id_for_state = auth0_sub or internal_user_id or "unknown"

        # Generate cryptographically secure state token for CSRF protection
        try:
            state_token = generate_state_token(user_id_for_state)
        except Exception as e:
            logger.error(f"Failed to generate state token: {e}", exc_info=True)
            # Fallback: use a simple state if session is not available
            import secrets

            state_token = secrets.token_urlsafe(32)
            logger.warning("Using fallback state token (session may not be available)")

        # Build Strava OAuth URL with secure state token
        url = (
            f"{config.STRAVA_API_BASE_URL.replace('/api/v3', '')}/oauth/authorize"
            f"?client_id={client_id}"
            f"&response_type=code"
            f"&redirect_uri={redirect_uri}"
            f"&scope=read,activity:read_all"
            f"&state={state_token}"
        )

        logger.info(f"Redirecting to Strava OAuth with secure state token")
        return redirect(url)
    except Exception as e:
        logger.exception("Unexpected error in strava_login_redirect")
        return error_response(
            f"Failed to initiate Strava login: {str(e)}",
            status_code=500,
            error_code="INTERNAL_ERROR",
        )


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
    db_session = get_session()
    try:
        code = request.args.get("code")
        state = request.args.get("state")

        logger.info(
            f"Received Strava callback - code={'present' if code else 'missing'}, state={'present' if state else 'missing'}"
        )

        # Validate OAuth code
        validated_code, error = validate_oauth_code(code)
        if error:
            return error
        code = validated_code

        if not state:
            return validation_error_response(
                "Missing state parameter",
                field="state",
            )

        # Validate state token to prevent CSRF attacks and extract user_id
        is_valid, error_msg, extracted_user_id = validate_state_token(state)
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

        # Use extracted user_id from state token (works even if session expired)
        if not extracted_user_id:
            logger.error("OAuth callback: Could not extract user_id from state token")
            return error_response(
                "Could not identify user from state token. Please try connecting again.",
                status_code=400,
                error_code="USER_ID_EXTRACTION_FAILED",
            )

        try:
            athlete_id, user_id = process_strava_callback(
                db_session, code, extracted_user_id
            )
            log_oauth_callback(
                user_id=user_id,
                athlete_id=str(athlete_id),
                success=True,
                provider="strava",
            )
        except (StravaOAuthError, StravaTokenError) as e:
            logger.exception(f"Strava error during callback processing: {e}")
            raise
        except Exception as e:
            logger.exception(f"Failed to process Strava callback: {e}")
            raise StravaOAuthCodeExchangeError(
                reason=str(e), message="Failed to process Strava OAuth callback"
            )

        db_session.commit()
        logger.info(f"Successfully linked athlete={athlete_id} to user={user_id}")

    except (StravaOAuthError, StravaTokenError, StravaAPIError) as e:
        db_session.rollback()
        logger.exception(f"Strava error during callback: {e}")
        from src.utils.security_utils import (
            get_safe_error_message,
            sanitize_exception_details,
        )

        safe_message = get_safe_error_message(e, context="oauth")
        safe_details = sanitize_exception_details(
            e.details if hasattr(e, "details") else {}
        )
        return error_response(
            message=safe_message,
            status_code=(
                400 if isinstance(e, (StravaOAuthError, StravaTokenError)) else 500
            ),
            error_code=type(e).__name__,
            details=safe_details,
        )
    except Exception as e:
        db_session.rollback()
        logger.exception("Error processing Strava callback")
        return internal_error_response("Failed to process Strava callback", log_error=e)
    finally:
        db_session.close()

    # Ingestion runs with a brand new session
    def ingestion_job(session, athlete_id, user_id):
        logger.info(f"Starting ingestion for user={user_id}, athlete={athlete_id}")
        run_full_ingestion_and_enrichment(None, athlete_id, user_id=user_id)

    run_background_job(ingestion_job, athlete_id, user_id)

    frontend_redirect = get_frontend_redirect_url()
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

    # Validate OAuth code
    validated_code, error = validate_oauth_code(code)
    if error:
        return error
    code = validated_code

    if not auth0_sub:
        return validation_error_response(
            "Missing sub parameter",
            field="sub",
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
    except (StravaOAuthError, StravaTokenError, StravaAPIError) as e:
        logger.exception(f"Strava error during callback (POST): {e}")
        from src.utils.security_utils import (
            get_safe_error_message,
            sanitize_exception_details,
        )

        safe_message = get_safe_error_message(e, context="oauth")
        safe_details = sanitize_exception_details(
            e.details if hasattr(e, "details") else {}
        )
        log_oauth_callback(
            user_id=auth0_sub,
            athlete_id=None,
            success=False,
            provider="strava",
            details={"error": safe_message},
        )
        return error_response(
            message=safe_message,
            status_code=(
                400 if isinstance(e, (StravaOAuthError, StravaTokenError)) else 500
            ),
            error_code=type(e).__name__,
            details=safe_details,
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
    def ingestion_job(session, athlete_id, user_id):
        logger.info(f"Starting ingestion for user={user_id}, athlete={athlete_id}")
        run_full_ingestion_and_enrichment(None, athlete_id, user_id=user_id)

    run_background_job(ingestion_job, athlete_id, user_id)

    # Return both IDs
    return success_response(
        data={
            "user_id": user_id,
            "athlete_id": athlete_id,
        },
        message="Strava account connected successfully",
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

    # Check if state_or_sub is already a UUID (internal user_id)
    if is_uuid_format(state_or_sub):
        user_id = state_or_sub  # Already internal user_id
        logger.info(f"Using UUID as user_id: {user_id}")
    else:
        # Fallback: treat as auth0_sub (must be in format "provider|user_id")
        if "|" not in str(state_or_sub):
            raise ValueError(
                f"Invalid user identifier format: expected UUID or auth0_sub (format: 'provider|user_id'), got: {state_or_sub}"
            )

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
        logger.info(f"Resolved auth0_sub to user_id: {user_id}")

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
    except (StravaOAuthCodeExchangeError, StravaTokenError, StravaAPIError) as e:
        # Re-raise Strava-specific errors as-is
        raise
    except Exception as e:
        raise StravaOAuthCodeExchangeError(
            reason=str(e), message="Token exchange failed"
        )

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
        # Get authenticated user and athlete link
        user_id, athlete_link, error = get_authenticated_user_with_athlete()
        if error:
            # Customize error for disconnect endpoint
            if "No Strava account connected" in str(error):
                return not_found_response(
                    resource="Strava connection",
                    message="No Strava account connected",
                    details={
                        "deleted": {"tokens": 0, "athlete_link": False},
                        "retained": {
                            "activities": 0,
                            "plans": "All training plans remain accessible",
                        },
                    },
                )
            return error

        athlete_id = athlete_link.athlete_id

        # Count activities before deletion (for response)
        activity_count = session.query(Activity).filter_by(user_id=user_id).count()

        # 1. Delete tokens (revokes API access)
        tokens_deleted = delete_tokens_sa(session, athlete_id)
        logger.info(
            f"Deleted {tokens_deleted} token(s) for athlete {athlete_id} "
            f"(user {user_id})"
        )

        # 2. Delete user-athlete link
        link_deleted = delete_by_user_id(user_id)
        logger.info(
            f"Deleted athlete link for user {user_id} " f"(athlete {athlete_id})"
        )

        session.commit()

        return success_response(
            data={
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
            },
            message="Strava account disconnected successfully",
        )

    except Exception as e:
        session.rollback()
        logger.error(
            f"Error disconnecting Strava for user {user_id if 'user_id' in locals() else 'unknown'}: {e}",
            exc_info=True,
        )
        return internal_error_response(
            message="Failed to disconnect Strava account",
            log_error=e,
            details={"detail": str(e)},
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
        # Get authenticated user and athlete link
        user_id, athlete_link, error = get_authenticated_user_with_athlete()
        if error:
            # If not found, return success with connected=False
            if "No Strava account connected" in str(error):
                return success_response(
                    data={"connected": False},
                    message="No Strava account connected",
                )
            return error

        # Count activities
        activity_count = session.query(Activity).filter_by(user_id=user_id).count()

        return success_response(
            data={
                "connected": True,
                "athlete_id": athlete_link.athlete_id,
                "connected_at": (
                    athlete_link.created_at.isoformat()
                    if athlete_link.created_at
                    else None
                ),
                "activity_count": activity_count,
            },
            message=f"Connected to Strava. {activity_count} activities synced.",
        )

    except Exception as e:
        logger.error(
            f"Error fetching Strava status for user {user_id if 'user_id' in locals() else 'unknown'}: {e}",
            exc_info=True,
        )
        return internal_error_response(
            message="Failed to fetch Strava status",
            log_error=e,
            details={"detail": str(e)},
        )
    finally:
        session.close()

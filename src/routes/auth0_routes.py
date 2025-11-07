"""
Auth0 Routes
===========

Handles Auth0 authentication flow (frontend login).

Responsibilities:
- Handle Auth0 login callback
- Verify JWT tokens
- Create/update user identity
- Set session cookies
"""

from flask import Blueprint, request, make_response, redirect
import os
import traceback
import logging

from src.db.db_session import get_session
from src.utils.auth0_jwt import verify_and_decode
from src.utils.response_utils import (
    error_response,
    validation_error_response,
    not_found_response,
    internal_error_response,
)
from src.utils.auth_rate_limiter import rate_limit_auth
from src.utils.audit_logger import log_login_success, log_login_failure

auth0_bp = Blueprint("auth0", __name__, url_prefix="/auth")
logger = logging.getLogger(__name__)


@auth0_bp.route("/login/callback", methods=["POST"])
@rate_limit_auth("login")
def login_callback():
    """
    Handles login after Auth0 provides an id_token (JWT).

    - Verifies JWT signature
    - Extracts user profile fields
    - Resolves or creates internal user_id
    - Sets cookie with `user_jwt` for session persistence
    """
    session = get_session()
    try:
        data = request.get_json() or {}
        id_token = data.get("id_token")

        if not id_token:
            return validation_error_response("Missing id_token", field="id_token")

        # Validate token format and length (security: prevent resource exhaustion)
        if not isinstance(id_token, str):
            return validation_error_response("Invalid token format", field="id_token")

        # JWT tokens should be reasonable length (max 10KB)
        if len(id_token) > 10000:
            return validation_error_response(
                "Token exceeds maximum length", field="id_token"
            )

        # JWT tokens have exactly 3 parts separated by dots
        token_parts = id_token.split(".")
        if len(token_parts) != 3:
            return validation_error_response("Invalid token format", field="id_token")

        try:
            decoded_jwt = verify_and_decode(id_token)
            logger.info(
                f"Token validated successfully for user: {decoded_jwt.get('sub')}"
            )
        except Exception as e:
            # Log full error server-side only
            logger.warning(f"Token validation failed: {e}", exc_info=True)
            # Log failed login attempt
            log_login_failure(reason=f"token_validation_failed: {str(e)[:50]}")
            # Return generic error to client (don't leak validation details)
            return error_response(
                "Invalid or expired token", status_code=401, error_code="INVALID_TOKEN"
            )

        auth0_sub = decoded_jwt.get("sub")
        user_profile = {
            "sub": auth0_sub,  # Required for get_user_id_from_request
            "email": decoded_jwt.get("email"),
            "name": decoded_jwt.get("name"),
            "picture": decoded_jwt.get("picture"),
            "email_verified": decoded_jwt.get("email_verified"),
        }

        from src.utils.auth_helpers import get_user_id_from_request

        user_id, error = get_user_id_from_request(user_profile, create_if_missing=True)
        if error:
            log_login_failure(auth0_sub=auth0_sub, reason="user_id_resolution_failed")
            return error

        user_jwt = id_token  # Use the token we just verified

        logger.info(f"Setting cookie for user_id: {user_id}")

        # Log successful login
        log_login_success(user_id=user_id, auth0_sub=auth0_sub)

        # Create response with redirect
        resp = make_response(redirect("https://app.smartcoach.dev"))

        # Use 'Lax' for same-site by default, 'None' only if cross-site required
        # SameSite=None requires Secure=True (already set)
        require_cross_site = os.getenv("REQUIRE_CROSS_SITE_COOKIES", "0") == "1"
        samesite_value = "None" if require_cross_site else "Lax"

        resp.set_cookie(
            "user_jwt",
            user_jwt,
            httponly=True,
            secure=True,
            samesite=samesite_value,
            domain=os.getenv("SESSION_COOKIE_DOMAIN"),
            path="/",
        )

        logger.debug(
            f"Cookie set: domain={os.getenv('SESSION_COOKIE_DOMAIN')}, secure=True, samesite={samesite_value}"
        )
        return resp

    except Exception as e:
        logger.exception("Error in login_callback")
        return internal_error_response("Failed to process login", log_error=e)
    finally:
        session.close()

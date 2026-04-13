"""
Strava Token Management Service
================================

This module handles Strava OAuth token management, including:
- Token storage and retrieval
- Token refresh (with automatic rotation)
- Token expiration checking
- Token revocation
- User-athlete linking

Key Features:
- Token Rotation: Refresh tokens are rotated (new token issued) on each refresh for security
- Encryption: Access and refresh tokens are encrypted at rest in the database
- Expiration Handling: Automatically refreshes expired tokens
- Audit Logging: All token operations are logged for security auditing

Token Lifecycle:
1. OAuth Callback: Store tokens from Strava OAuth callback
2. Token Usage: Retrieve valid access token (auto-refresh if expired)
3. Token Refresh: Refresh expired tokens (with rotation)
4. Token Revocation: Revoke tokens when user disconnects Strava

Security:
- Tokens are encrypted at rest using Fernet symmetric encryption
- Refresh tokens are rotated on each use (old token invalidated)
- Token operations are audit logged
- Revoked tokens are soft-deleted (maintains audit trail)

Usage:
    from src.services.token_service import (
        get_valid_token,
        refresh_access_token,
        store_tokens_from_callback,
        revoke_athlete_tokens,
    )

    # Get valid access token (auto-refreshes if expired)
    access_token = get_valid_token(session, athlete_id=12345)

    # Store tokens from OAuth callback
    athlete_id, user_id = store_tokens_from_callback(
        code="oauth_code",
        session=session,
        redirect_uri="https://example.com/callback",
        user_id="user-uuid"
    )

    # Revoke tokens
    revoked = revoke_athlete_tokens(session, athlete_id=12345)

Token Storage:
- Tokens are stored in the `tokens` table
- Encrypted fields: `_encrypted_access_token`, `_encrypted_refresh_token`
- Plain fields: `expires_at`, `athlete_id`, `revoked_at`

References:
- https://developers.strava.com/docs/authentication/
- https://developers.strava.com/docs/oauth-updates/
"""

import json
import logging
import uuid as uuid_lib
import requests
from datetime import datetime

from src.utils.config import config
from src.db.db_session import get_session as db_get_session
from src.db.dao.token_dao import get_tokens_sa, insert_token_sa
from src.db.models.tokens import Token
from sqlalchemy.exc import IntegrityError
from src.db.dao import user_athletes_dao  # add this import
from src.utils.strava_exceptions import (
    StravaAthleteAlreadyLinkedError,
    StravaOAuthCodeExchangeError,
)


logger = logging.getLogger(__name__)


def _internal_user_id_str(value) -> str:
    """Normalize stored or passed user id to canonical string for comparison."""
    if value is None:
        return ""
    try:
        return str(uuid_lib.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return str(value).strip()


def get_session():
    return db_get_session()


def is_expired(expires_at):
    return expires_at <= int(datetime.utcnow().timestamp())


def get_valid_token(session, athlete_id):
    """
    Get a valid access token for an athlete, refreshing if expired.

    Args:
        session: Database session
        athlete_id: Strava athlete ID

    Returns:
        Valid access token (string)

    Raises:
        StravaTokenNotFoundError: If no tokens found for athlete
        StravaTokenRefreshError: If token refresh fails
        StravaTokenRevokedError: If token has been revoked
    """
    token_data = get_tokens_sa(session, athlete_id)
    if not token_data:
        raise StravaTokenNotFoundError(athlete_id)

    if is_expired(token_data["expires_at"]):
        try:
            refreshed = refresh_access_token(session, athlete_id)
            return refreshed["access_token"]
        except (StravaTokenRevokedError, StravaTokenRefreshError):
            raise
        except Exception as e:
            raise StravaTokenRefreshError(
                athlete_id=athlete_id,
                reason=str(e),
                message=f"Failed to refresh expired token for athlete {athlete_id}",
            )

    return token_data["access_token"]


def refresh_access_token(session, athlete_id):
    """
    Refresh access token (also rotates refresh token).

    Returns:
        Dict with access_token, refresh_token, expires_at

    Note: This function also performs token rotation for security.
    """
    from src.db.models.tokens import Token
    from src.utils.audit_logger import log_token_refresh

    token = session.query(Token).filter_by(athlete_id=athlete_id).first()
    if not token:
        raise StravaTokenNotFoundError(
            athlete_id=athlete_id,
            message=f"No refresh token available for athlete {athlete_id}",
        )

    # Check if token is revoked
    if token.is_revoked():
        raise StravaTokenRevokedError(athlete_id=athlete_id)

    # Refresh tokens (Strava returns new access + refresh tokens)
    tokens = refresh_token_static(token.refresh_token)

    # ✅ Token rotation: Update both access and refresh tokens
    token.access_token = tokens["access_token"]  # Automatically encrypted
    token.refresh_token = tokens["refresh_token"]  # New refresh token (rotated)
    token.expires_at = tokens["expires_at"]
    token.revoked_at = None  # Ensure not revoked
    session.commit()

    from src.utils.security_utils import redact_dict

    redacted_tokens = redact_dict(tokens)
    logger.info(f"Tokens refreshed and rotated: {redacted_tokens}")

    log_token_refresh(
        user_id=None,  # Will be set by caller if available
        athlete_id=str(athlete_id),
        success=True,
        details={"rotated": True},
    )

    return tokens  # Return dict with access_token, refresh_token, expires_at


def refresh_token_static(refresh_token):
    """
    Refresh Strava token via API (static method, no session required).

    Args:
        refresh_token: Strava refresh token

    Returns:
        Dict with access_token, refresh_token, expires_at

    Raises:
        StravaTokenRefreshError: If refresh fails
        StravaAPIError: If API request fails
    """
    try:
        response = requests.post(
            f"{config.STRAVA_API_BASE_URL}/oauth/token",
            data={
                "client_id": config.STRAVA_CLIENT_ID,
                "client_secret": config.STRAVA_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        raise StravaTokenRefreshError(
            athlete_id=None,
            reason=f"HTTP {e.response.status_code}: {e.response.text[:200] if e.response.text else 'Unknown error'}",
            message="Failed to refresh token via Strava API",
        )
    except requests.exceptions.RequestException as e:
        raise StravaAPIError(
            f"Network error during token refresh: {e}",
            details={"error_type": type(e).__name__},
        )


def refresh_token_if_expired(session, athlete_id):
    """
    Refresh tokens if expired, with automatic token rotation.

    Note: Refresh tokens are rotated (new refresh token issued) on each refresh
    for improved security. Old refresh tokens are invalidated.
    """
    from src.db.models.tokens import Token
    from src.utils.audit_logger import log_token_refresh

    token = session.query(Token).filter_by(athlete_id=athlete_id).first()
    if not token:
        raise ValueError(f"No token found for athlete ID {athlete_id}")

    # Check if token is revoked
    if token.is_revoked():
        logger.warning(f"Attempted to refresh revoked token for athlete {athlete_id}")
        log_token_refresh(
            user_id=None,
            athlete_id=str(athlete_id),
            success=False,
            details={"reason": "token_revoked"},
        )
        raise ValueError(f"Token for athlete {athlete_id} has been revoked")

    now = datetime.utcnow().timestamp()
    if token.expires_at <= now:
        # Refresh tokens (Strava returns new access + refresh tokens)
        refreshed = refresh_token_static(token.refresh_token)

        # ✅ Token rotation: Update both access and refresh tokens
        # This invalidates the old refresh token (one-time use)
        token.access_token = refreshed["access_token"]  # Automatically encrypted
        token.refresh_token = refreshed["refresh_token"]  # New refresh token (rotated)
        token.expires_at = refreshed["expires_at"]
        token.revoked_at = None  # Ensure not revoked
        session.commit()

        logger.info(f"Tokens refreshed and rotated for athlete {athlete_id}")
        log_token_refresh(
            user_id=None,  # Will be set by caller if available
            athlete_id=str(athlete_id),
            success=True,
            details={"rotated": True},
        )
        return True
    return False


def delete_athlete_tokens(session, athlete_id):
    """
    Delete tokens for athlete (hard delete).

    For soft delete (revocation), use revoke_athlete_tokens instead.
    """
    from src.db.models.tokens import Token
    from src.utils.audit_logger import log_token_revocation

    token = session.query(Token).filter_by(athlete_id=athlete_id).first()
    if token:
        log_token_revocation(
            user_id=None,  # Will be set by caller if available
            athlete_id=str(athlete_id),
        )

    deleted = session.query(Token).filter_by(athlete_id=athlete_id).delete()
    session.commit()
    return deleted


def revoke_athlete_tokens(session, athlete_id):
    """
    Revoke tokens for athlete (soft delete - marks as revoked but keeps record).

    This allows for immediate revocation while maintaining audit trail.
    """
    from src.db.models.tokens import Token
    from src.utils.audit_logger import log_token_revocation

    token = session.query(Token).filter_by(athlete_id=athlete_id).first()
    if not token:
        return False

    if not token.is_revoked():
        token.revoke()  # Sets revoked_at timestamp
        session.commit()
        logger.info(f"Tokens revoked for athlete {athlete_id}")
        log_token_revocation(
            user_id=None,  # Will be set by caller if available
            athlete_id=str(athlete_id),
        )
        return True

    return False  # Already revoked


def store_tokens_from_callback(code, session, redirect_uri, user_id: str | None = None):
    logger.info(
        f"[store_tokens_from_callback] called with user_id={user_id}, redirect_uri={redirect_uri}"
    )
    from sqlalchemy.exc import IntegrityError
    from src.db.dao import user_athletes_dao
    from src.db.dao.token_dao import insert_token_sa
    from src.db.models.tokens import Token
    from src.utils.config import config
    import requests

    from src.utils.security_utils import redact_secret, redact_token, redact_dict

    logger.info(f"Using Strava client_id: {config.STRAVA_CLIENT_ID}")
    logger.info(
        f"Using Strava client_secret: {redact_secret(config.STRAVA_CLIENT_SECRET)}"
    )
    logger.info(f"Using redirect_uri: {redirect_uri}")
    logger.info(f"Using code: {redact_token(code, show_length=False)}")

    redirect_uri_clean = redirect_uri.strip().rstrip(";")
    logger.debug(f"[TokenService] Using cleaned redirect_uri: '{redirect_uri_clean}'")

    payload = {
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri_clean,
    }

    # Redact sensitive data before logging
    redacted_payload = redact_dict(payload)
    logger.debug(
        f"[TokenService] Sending POST data to Strava token endpoint: {redacted_payload}"
    )

    try:
        response = requests.post(
            f"{config.STRAVA_API_BASE_URL}/oauth/token", data=payload
        )
    except requests.exceptions.RequestException as e:
        raise StravaOAuthCodeExchangeError(
            reason=f"Network error: {e}",
            message="Failed to connect to Strava API for token exchange",
        )

    # Log response status and body (response body may contain tokens - redact if needed)
    logger.info(f"Strava token response status: {response.status_code}")

    # Try to parse and redact response body if it contains tokens
    response_data = None
    try:
        response_data = response.json()
        redacted_response = redact_dict(response_data)
        logger.debug(f"Strava token response: {redacted_response}")
    except (ValueError, TypeError) as e:
        # If not JSON, log as-is (may be error message)
        logger.debug(f"Strava token response body (non-JSON): {response.text[:200]}")
        logger.debug(f"JSON parse error: {e}")

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        error_details = response_data
        if error_details is None:
            try:
                error_details = response.json()
            except (ValueError, TypeError):
                error_details = (
                    e.response.text[:200] if e.response and e.response.text else ""
                )

        if isinstance(error_details, dict):
            sanitized_error = redact_dict(error_details)
            sanitized_error_str = json.dumps(sanitized_error, default=str)[:500]
        else:
            sanitized_error_str = error_details or "No response body"
        logger.error(
            "Strava token exchange failed: status=%s, body=%s",
            e.response.status_code if e.response else "unknown",
            sanitized_error_str,
        )
        raise StravaOAuthCodeExchangeError(
            reason=(
                f"HTTP {e.response.status_code}: {sanitized_error_str}"
                if e.response
                else f"HTTP error: {sanitized_error_str}"
            ),
            message="Failed to exchange OAuth code for tokens",
        )

    if not response_data:
        # Try to parse again if we failed earlier
        try:
            response_data = response.json()
        except (ValueError, TypeError):
            raise StravaOAuthCodeExchangeError(
                reason="Invalid response format (not JSON)",
                message="Strava OAuth response is not valid JSON",
            )

    athlete = response_data.get("athlete")
    if not athlete or "id" not in athlete:
        raise StravaOAuthCodeExchangeError(
            reason="Response missing athlete ID",
            message="Strava OAuth response missing required athlete field",
        )

    strava_athlete_id = athlete["id"]
    # Extract premium status from OAuth response (same pattern as athlete_id)
    has_premium = athlete.get(
        "summit", False
    )  # Summit is boolean indicating paid subscription
    premium_checked_at = datetime.utcnow()

    # Block linking the same Strava athlete to a second app user (prevents token
    # row churn and confusing sync_status rows). Same user reconnecting is allowed.
    if user_id:
        from src.db.models.user_athletes import UserAthleteLink

        existing_for_athlete = (
            session.query(UserAthleteLink)
            .filter_by(athlete_id=strava_athlete_id)
            .first()
        )
        if existing_for_athlete and _internal_user_id_str(
            existing_for_athlete.user_id
        ) != _internal_user_id_str(user_id):
            logger.warning(
                "Strava OAuth rejected: athlete_id=%s already linked to user_id=%s "
                "(current flow user_id=%s)",
                strava_athlete_id,
                existing_for_athlete.user_id,
                user_id,
            )
            raise StravaAthleteAlreadyLinkedError(strava_athlete_id)

    # ✅ 1. Ensure athlete exists in user_athletes BEFORE inserting token
    if user_id:
        try:
            user_athletes_dao.create_link(
                user_id=user_id,
                athlete_id=strava_athlete_id,
                has_strava_premium=has_premium,
                strava_premium_checked_at=premium_checked_at,
                session=session,  # Use the same session for transaction consistency
            )
            logger.info(
                f"Linked user {user_id} → athlete {strava_athlete_id} (premium: {has_premium})"
            )
        except IntegrityError:
            session.rollback()  # clear failed transaction
            from src.db.models.user_athletes import UserAthleteLink

            other = (
                session.query(UserAthleteLink)
                .filter_by(athlete_id=strava_athlete_id)
                .first()
            )
            if other and _internal_user_id_str(other.user_id) != _internal_user_id_str(
                user_id
            ):
                logger.warning(
                    "Strava OAuth IntegrityError: athlete_id=%s owned by user_id=%s, "
                    "not current user_id=%s",
                    strava_athlete_id,
                    other.user_id,
                    user_id,
                )
                raise StravaAthleteAlreadyLinkedError(strava_athlete_id)

            logger.debug(f"Link already exists for user {user_id}")
            # Update existing link with premium status (same pattern as token update)
            existing_link = (
                session.query(UserAthleteLink).filter_by(user_id=user_id).first()
            )
            if existing_link:
                existing_link.has_strava_premium = has_premium
                existing_link.strava_premium_checked_at = premium_checked_at
                session.commit()
                logger.info(
                    f"Updated existing link for user {user_id} with premium status: {has_premium}"
                )

    # ✅ 2. Insert or update tokens
    # Extract token data from response
    access_token = response_data.get("access_token")
    refresh_token = response_data.get("refresh_token")
    expires_at = response_data.get("expires_at")

    if not access_token or not refresh_token or not expires_at:
        raise StravaOAuthCodeExchangeError(
            reason="Response missing required token fields",
            message="Strava OAuth response missing access_token, refresh_token, or expires_at",
        )

    try:
        insert_token_sa(
            session=session,
            athlete_id=strava_athlete_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        logger.info(f"Token stored for athlete: {strava_athlete_id}")
    except IntegrityError:
        session.rollback()  # clear failed transaction
        logger.info(
            f"Token already exists for athlete {strava_athlete_id}, updating instead"
        )

        # UPDATE existing token row instead of failing
        existing = session.query(Token).filter_by(athlete_id=strava_athlete_id).first()
        if existing:
            existing.access_token = access_token
            existing.refresh_token = refresh_token
            existing.expires_at = expires_at
            session.commit()
            logger.info(f"Token updated for athlete: {strava_athlete_id}")

    logger.info(
        f"[store_tokens_from_callback] ✅ Finished storing tokens for user_id={user_id}, athlete_id={strava_athlete_id}"
    )
    return strava_athlete_id, user_id


def exchange_code_for_token(code, redirect_uri=None):
    if redirect_uri is None:
        redirect_uri = config.STRAVA_REDIRECT_URI.strip().rstrip(";")
    else:
        redirect_uri = redirect_uri.strip().rstrip(";")

    response = requests.post(
        f"{config.STRAVA_API_BASE_URL}/oauth/token",
        data={
            "client_id": config.STRAVA_CLIENT_ID,
            "client_secret": config.STRAVA_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )
    response.raise_for_status()
    return response.json()


def get_authorization_url():
    redirect_uri = config.STRAVA_REDIRECT_URI.strip().rstrip(";")
    client_id = config.STRAVA_CLIENT_ID
    url = (
        f"{config.STRAVA_API_BASE_URL.replace('/api/v3', '')}/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read,activity:read_all"
    )
    return url

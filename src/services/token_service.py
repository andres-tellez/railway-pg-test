# src/services/token_service.py
import logging
import requests
from datetime import datetime

from src.utils.config import config
from src.db.db_session import get_session as db_get_session
from src.db.dao.token_dao import get_tokens_sa, insert_token_sa
from src.db.models.tokens import Token
from sqlalchemy.exc import IntegrityError
from src.db.dao import user_athletes_dao  # add this import


logger = logging.getLogger(__name__)


def get_session():
    return db_get_session()


def is_expired(expires_at):
    return expires_at <= int(datetime.utcnow().timestamp())


def get_valid_token(session, athlete_id):
    token_data = get_tokens_sa(session, athlete_id)
    if not token_data:
        raise RuntimeError(f"No tokens found for athlete {athlete_id}")

    if is_expired(token_data["expires_at"]):
        return refresh_access_token(session, athlete_id)["access_token"]

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
        raise RuntimeError(f"No refresh token available for athlete {athlete_id}")

    # Check if token is revoked
    if token.is_revoked():
        raise ValueError(f"Token for athlete {athlete_id} has been revoked")

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
    response = requests.post(
        "https://www.strava.com/api/v3/oauth/token",
        data={
            "client_id": config.STRAVA_CLIENT_ID,
            "client_secret": config.STRAVA_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    response.raise_for_status()
    return response.json()


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

    response = requests.post("https://www.strava.com/api/v3/oauth/token", data=payload)

    # Log response status and body (response body may contain tokens - redact if needed)
    logger.info(f"Strava token response status: {response.status_code}")

    # Try to parse and redact response body if it contains tokens
    try:
        response_data = response.json()
        redacted_response = redact_dict(response_data)
        logger.debug(f"Strava token response: {redacted_response}")
    except:
        # If not JSON, log as-is (may be error message)
        logger.debug(f"Strava token response body (non-JSON): {response.text[:200]}")

    response.raise_for_status()
    token_data = response.json()

    athlete = token_data.get("athlete")
    if not athlete or "id" not in athlete:
        raise KeyError("❌ Strava callback response missing athlete ID")

    strava_athlete_id = athlete["id"]

    # ✅ 1. Ensure athlete exists in user_athletes BEFORE inserting token
    if user_id:
        try:
            user_athletes_dao.create_link(
                user_id=user_id,
                athlete_id=strava_athlete_id,
            )
            print(f"✅ Linked user {user_id} → athlete {strava_athlete_id}", flush=True)
        except IntegrityError:
            session.rollback()  # clear failed transaction
            print(f"🔗 Link already exists for user {user_id}", flush=True)

    # ✅ 2. Insert or update tokens
    try:
        insert_token_sa(
            session=session,
            athlete_id=strava_athlete_id,
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=token_data["expires_at"],
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
            existing.access_token = token_data["access_token"]
            existing.refresh_token = token_data["refresh_token"]
            existing.expires_at = token_data["expires_at"]
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
        "https://www.strava.com/api/v3/oauth/token",
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
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read,activity:read_all"
    )
    return url

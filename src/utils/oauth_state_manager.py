"""
OAuth State Manager
===================

Manages OAuth state parameters for CSRF protection.

The OAuth state parameter must be:
1. Cryptographically random
2. Stored securely (session)
3. Validated on callback
4. Expired after reasonable time (5 minutes)

This prevents CSRF attacks where an attacker tricks a user into
connecting their account to the attacker's account.
"""

import secrets
import time
from flask import session
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# State token expires after 5 minutes
STATE_TOKEN_TTL_SEC = 300


def generate_state_token(user_id: str) -> str:
    """
    Generate a cryptographically secure random state token.

    Args:
        user_id: User ID to associate with the state (for validation)

    Returns:
        Cryptographically random state token (URL-safe base64)
    """
    state_token = secrets.token_urlsafe(32)  # 32 bytes = 256 bits of entropy
    expiry = time.time() + STATE_TOKEN_TTL_SEC

    # Store in session with user_id and expiry
    session["oauth_state_token"] = state_token
    session["oauth_state_user_id"] = user_id
    session["oauth_state_expiry"] = expiry

    logger.debug(f"Generated OAuth state token for user {user_id}")
    return state_token


def validate_state_token(
    state: str, expected_user_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate OAuth state token from callback.

    Args:
        state: State token from OAuth callback
        expected_user_id: Optional user ID to verify matches

    Returns:
        Tuple of (is_valid, error_message)
        - If valid: (True, None)
        - If invalid: (False, error_message)
    """
    if not state:
        return False, "Missing state parameter"

    stored_token = session.get("oauth_state_token")
    stored_user_id = session.get("oauth_state_user_id")
    stored_expiry = session.get("oauth_state_expiry")

    if not stored_token:
        logger.warning("OAuth callback: No state token found in session")
        return False, "State token not found (session expired or invalid)"

    if time.time() > stored_expiry:
        logger.warning("OAuth callback: State token expired")
        # Clear expired state
        session.pop("oauth_state_token", None)
        session.pop("oauth_state_user_id", None)
        session.pop("oauth_state_expiry", None)
        return False, "State token expired"

    if state != stored_token:
        logger.warning("OAuth callback: State token mismatch")
        return False, "Invalid state parameter (possible CSRF attack)"

    # If expected_user_id provided, verify it matches
    if expected_user_id and stored_user_id != expected_user_id:
        logger.warning(
            f"OAuth callback: User ID mismatch (expected {expected_user_id}, got {stored_user_id})"
        )
        return False, "User ID mismatch"

    # Clear state after successful validation
    session.pop("oauth_state_token", None)
    session.pop("oauth_state_user_id", None)
    session.pop("oauth_state_expiry", None)

    logger.debug(f"OAuth state token validated successfully for user {stored_user_id}")
    return True, None

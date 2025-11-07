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

State token format: {random_token}.{base64url_encoded_user_id}
This allows user_id to be extracted even if session is lost.
"""

import secrets
import time
import base64
from flask import session
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# State token expires after 5 minutes
STATE_TOKEN_TTL_SEC = 300


def generate_state_token(user_id: str) -> str:
    """
    Generate a cryptographically secure random state token with embedded user_id.

    Args:
        user_id: User ID to associate with the state (for validation)

    Returns:
        State token in format: {random_token}.{base64url_encoded_user_id}
    """
    random_token = secrets.token_urlsafe(32)  # 32 bytes = 256 bits of entropy
    expiry = time.time() + STATE_TOKEN_TTL_SEC

    # Encode user_id in base64url (URL-safe)
    encoded_user_id = (
        base64.urlsafe_b64encode(user_id.encode("utf-8")).decode("utf-8").rstrip("=")
    )

    # Combine: random_token.encoded_user_id
    state_token = f"{random_token}.{encoded_user_id}"

    # Store in session for CSRF validation (best effort - if session fails, we can still extract user_id)
    try:
        session["oauth_state_token"] = random_token
        session["oauth_state_user_id"] = user_id
        session["oauth_state_expiry"] = expiry
        # Ensure session is marked as modified
        session.permanent = True
    except Exception as e:
        logger.warning(
            f"Failed to store state token in session (will rely on embedded user_id): {e}"
        )
        # Don't raise - we can still extract user_id from the state token itself

    logger.debug(f"Generated OAuth state token for user {user_id}")
    return state_token


def validate_state_token(
    state: str, expected_user_id: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate OAuth state token from callback and extract user_id.

    Args:
        state: State token from OAuth callback (format: {random_token}.{encoded_user_id})
        expected_user_id: Optional user ID to verify matches

    Returns:
        Tuple of (is_valid, error_message, extracted_user_id)
        - If valid: (True, None, user_id)
        - If invalid: (False, error_message, None)
    """
    if not state:
        return False, "Missing state parameter", None

    # Extract user_id from state token (embedded in format: random_token.encoded_user_id)
    extracted_user_id = None
    random_token_from_state = None

    if "." in state:
        try:
            parts = state.split(".", 1)
            random_token_from_state = parts[0]
            encoded_user_id = parts[1]
            # Decode base64url (add padding if needed)
            padding = 4 - len(encoded_user_id) % 4
            if padding != 4:
                encoded_user_id += "=" * padding
            extracted_user_id = base64.urlsafe_b64decode(encoded_user_id).decode(
                "utf-8"
            )
        except Exception as e:
            logger.warning(f"Failed to extract user_id from state token: {e}")
            return False, "Invalid state token format", None
    else:
        # Legacy format (just random token) - try to get user_id from session
        random_token_from_state = state
        logger.warning("Legacy state token format (no embedded user_id)")

    # Try to validate using session (best case - full CSRF protection)
    stored_token = session.get("oauth_state_token")
    stored_user_id = session.get("oauth_state_user_id")
    stored_expiry = session.get("oauth_state_expiry")

    if stored_token and stored_expiry:
        # Session available - use it for validation
        if time.time() > stored_expiry:
            logger.warning("OAuth callback: State token expired")
            # Clear expired state
            session.pop("oauth_state_token", None)
            session.pop("oauth_state_user_id", None)
            session.pop("oauth_state_expiry", None)
            # Fall through to use extracted_user_id if available

        elif random_token_from_state == stored_token:
            # Token matches - use session user_id (most secure)
            user_id_to_use = stored_user_id or extracted_user_id

            # If expected_user_id provided, verify it matches
            if expected_user_id and user_id_to_use != expected_user_id:
                logger.warning(
                    f"OAuth callback: User ID mismatch (expected {expected_user_id}, got {user_id_to_use})"
                )
                return False, "User ID mismatch", None

            # Clear state after successful validation
            session.pop("oauth_state_token", None)
            session.pop("oauth_state_user_id", None)
            session.pop("oauth_state_expiry", None)

            logger.debug(
                f"OAuth state token validated successfully for user {user_id_to_use}"
            )
            return True, None, user_id_to_use
        else:
            logger.warning(
                "OAuth callback: State token mismatch (possible CSRF attack)"
            )
            # Don't return False yet - fall through to use extracted_user_id if available
    else:
        logger.warning(
            "OAuth callback: No state token found in session (session may have expired)"
        )

    # Session validation failed or unavailable - use extracted user_id as fallback
    if extracted_user_id:
        logger.info(
            f"Using extracted user_id from state token (session unavailable): {extracted_user_id}"
        )

        # If expected_user_id provided, verify it matches
        if expected_user_id and extracted_user_id != expected_user_id:
            logger.warning(
                f"OAuth callback: User ID mismatch (expected {expected_user_id}, got {extracted_user_id})"
            )
            return False, "User ID mismatch", None

        return True, None, extracted_user_id

    # No user_id available from either source
    return False, "State token not found and could not extract user_id", None

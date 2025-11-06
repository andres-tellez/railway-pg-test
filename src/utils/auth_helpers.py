"""
Authentication Helper Utilities
==============================

Utility functions to reduce code repetition in authentication-related routes.

These functions provide consistent patterns for:
- Extracting sub claim from JWT
- Resolving user_id from claims
- Handling common authentication errors

Usage:
    from src.utils.auth_helpers import get_sub_from_claims, get_user_id_from_request

    # Extract sub claim
    sub, error = get_sub_from_claims()
    if error:
        return error

    # Get user_id (handles sub extraction and resolution)
    user_id, error = get_user_id_from_request()
    if error:
        return error
"""

from flask import g
from typing import Tuple, Optional
from src.utils.response_utils import validation_error_response, not_found_response
from src.db.dao.user_identity_dao import resolve_user_id_from_auth_provider


def get_sub_from_claims(
    claims: Optional[dict] = None,
) -> Tuple[Optional[str], Optional[tuple]]:
    """
    Extract sub claim from current_user, with consistent error handling.

    Args:
        claims: Optional claims dict. If None, extracts from g.current_user.

    Returns:
        Tuple of (sub, error_response):
        - If sub exists: (sub, None)
        - If sub missing: (None, error_response_tuple)

    Example:
        sub, error = get_sub_from_claims()
        if error:
            return error
        # Use sub...
    """
    if claims is None:
        claims = getattr(g, "current_user", {})

    sub = claims.get("sub")
    if not sub:
        return None, validation_error_response(
            "Missing sub claim in token", field="sub"
        )

    return sub, None


def get_user_id_from_request(
    claims: Optional[dict] = None, create_if_missing: bool = False
) -> Tuple[Optional[str], Optional[tuple]]:
    """
    Get user_id from current request, with consistent error handling.

    This function:
    1. Extracts sub claim from JWT
    2. Resolves internal user_id from sub
    3. Handles all error cases consistently

    Args:
        claims: Optional claims dict. If None, extracts from g.current_user.
        create_if_missing: If True, creates user identity if it doesn't exist.

    Returns:
        Tuple of (user_id, error_response):
        - If user_id exists: (user_id, None)
        - If error: (None, error_response_tuple)

    Example:
        user_id, error = get_user_id_from_request()
        if error:
            return error
        # Use user_id...
    """
    # Extract sub claim
    sub, error = get_sub_from_claims(claims)
    if error:
        return None, error

    # Resolve user_id
    if claims is None:
        claims = getattr(g, "current_user", {})

    user_id = resolve_user_id_from_auth_provider(
        sub, claims, create_if_missing=create_if_missing
    )

    if not user_id:
        return None, not_found_response("User")

    return user_id, None


def get_claims_and_sub() -> Tuple[dict, Optional[str], Optional[tuple]]:
    """
    Get claims and sub in one call, with consistent error handling.

    Returns:
        Tuple of (claims, sub, error_response):
        - If successful: (claims, sub, None)
        - If error: (claims, None, error_response_tuple)

    Example:
        claims, sub, error = get_claims_and_sub()
        if error:
            return error
        # Use claims and sub...
    """
    claims = getattr(g, "current_user", {})
    sub, error = get_sub_from_claims(claims)

    if error:
        return claims, None, error

    return claims, sub, None

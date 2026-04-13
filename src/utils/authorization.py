"""
Authorization Utilities
=======================

Authorization decorators and utilities for access control.

Provides:
- Resource ownership validation
- Role-based access control
- Permission checks

Note: Authentication (who are you?) is handled by @requires_auth.
Authorization (what can you do?) is handled here.
"""

from functools import wraps
import os
from typing import Optional
from flask import g, jsonify
from src.utils.response_utils import unauthorized_response
import logging

logger = logging.getLogger(__name__)


def requires_ownership(resource_user_id_field: str = "user_id"):
    """
    Decorator to ensure user owns the resource they're trying to access.

    Args:
        resource_user_id_field: Field name in the resource that contains user_id

    Usage:
        @requires_ownership("user_id")
        def get_user_data(user_id):
            # This will fail if g.user_id != user_id
            ...

    OR:
        @requires_ownership("owner_id")
        def get_resource(resource_id):
            resource = get_resource_by_id(resource_id)
            # Decorator checks resource.owner_id == g.user_id
            ...
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Get current user ID from Flask g (set by @requires_auth)
            current_user_id = getattr(g, "user_id", None)
            if not current_user_id:
                return unauthorized_response("Authentication required")

            # Check if function parameter matches resource_user_id_field
            # If the route parameter name matches resource_user_id_field, use it
            if resource_user_id_field in kwargs:
                resource_user_id = kwargs[resource_user_id_field]
                if str(current_user_id) != str(resource_user_id):
                    logger.warning(
                        f"Authorization failed: user {current_user_id} attempted to access "
                        f"resource owned by {resource_user_id}"
                    )
                    return unauthorized_response(
                        "Not authorized to access this resource"
                    )

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def requires_resource_ownership(get_resource_func):
    """
    Decorator to ensure user owns a resource fetched by a function.

    Args:
        get_resource_func: Function that takes route args/kwargs and returns resource object

    Usage:
        @requires_resource_ownership(lambda resource_id: get_resource(resource_id))
        def update_resource(resource_id):
            # Decorator checks resource.user_id == g.user_id
            ...
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            current_user_id = getattr(g, "user_id", None)
            if not current_user_id:
                return unauthorized_response("Authentication required")

            # Get resource using provided function
            resource = get_resource_func(*args, **kwargs)
            if not resource:
                from src.utils.response_utils import not_found_response

                return not_found_response("Resource")

            # Check ownership
            resource_user_id = getattr(resource, "user_id", None)
            if not resource_user_id or str(current_user_id) != str(resource_user_id):
                logger.warning(
                    f"Authorization failed: user {current_user_id} attempted to access "
                    f"resource owned by {resource_user_id}"
                )
                return unauthorized_response("Not authorized to access this resource")

            return fn(*args, **kwargs)

        return wrapper

    return decorator


def check_user_owns_resource(
    resource_user_id: str, current_user_id: Optional[str] = None
) -> bool:
    """
    Check if current user owns a resource.

    Args:
        resource_user_id: User ID that owns the resource
        current_user_id: Current user ID (defaults to g.user_id)

    Returns:
        True if user owns resource, False otherwise
    """
    if current_user_id is None:
        current_user_id = getattr(g, "user_id", None)

    if not current_user_id:
        return False

    return str(current_user_id) == str(resource_user_id)


def is_admin(user_id: Optional[str] = None) -> bool:
    """
    Check if user has admin role.

    Args:
        user_id: User ID to check (defaults to g.user_id)

    Returns:
        True if user is admin, False otherwise

    Set ADMIN_USER_IDS to a comma-separated list of internal user_id UUID strings
    (the same values as g.user_id after Auth resolution).
    """
    if user_id is None:
        user_id = getattr(g, "user_id", None)

    if not user_id:
        return False

    raw = (os.getenv("ADMIN_USER_IDS") or "").strip()
    if not raw:
        return False

    allowed = {part.strip() for part in raw.split(",") if part.strip()}
    return str(user_id) in allowed


def requires_admin(fn):
    """
    Decorator to require admin role.

    Usage:
        @requires_admin
        @requires_auth
        def admin_endpoint():
            ...
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_admin():
            logger.warning(
                f"Admin access denied for user {getattr(g, 'user_id', 'unknown')}"
            )
            return unauthorized_response("Admin access required")
        return fn(*args, **kwargs)

    return wrapper

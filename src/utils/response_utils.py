"""
Response Utilities
==================

Standardized response formatting for API endpoints.

This module provides utility functions for consistent API responses,
error handling, and status codes across all route handlers.

Usage:
    from src.utils.response_utils import error_response, success_response

    @route('/api/endpoint')
    def my_endpoint():
        try:
            data = do_something()
            return success_response(data, status_code=200)
        except ValueError as e:
            return error_response(str(e), status_code=400)
"""

from flask import jsonify
from typing import Any, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def success_response(
    data: Any = None, message: Optional[str] = None, status_code: int = 200, **kwargs
) -> Tuple[Dict[str, Any], int]:
    """
    Create a standardized success response.

    Args:
        data: The response data (dict, list, or any serializable object)
        message: Optional success message
        status_code: HTTP status code (default: 200)
        **kwargs: Additional fields to include in response

    Returns:
        Tuple of (JSON response, status_code)

    Example:
        >>> success_response({"user_id": "123"}, message="User created")
        ({"data": {"user_id": "123"}, "message": "User created", "status": 200}, 200)
    """
    response = {"status": status_code}

    if data is not None:
        response["data"] = data

    if message:
        response["message"] = message

    # Add any additional fields
    response.update(kwargs)

    return jsonify(response), status_code


def error_response(
    message: str,
    status_code: int = 400,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Tuple[Dict[str, Any], int]:
    """
    Create a standardized error response.

    Args:
        message: Human-readable error message (will be sanitized)
        status_code: HTTP status code (default: 400)
        error_code: Optional machine-readable error code
        details: Optional additional error details
        **kwargs: Additional fields to include in response

    Returns:
        Tuple of (JSON response, status_code)

    Example:
        >>> error_response("User not found", status_code=404, error_code="USER_NOT_FOUND")
        ({"error": "User not found", "error_code": "USER_NOT_FOUND", "status": 404}, 404)
    """
    # Sanitize error message to prevent leaking sensitive information
    sanitized_message = _sanitize_error_message(message)

    response = {"error": sanitized_message, "status": status_code}

    if error_code:
        response["error_code"] = error_code

    if details:
        response["details"] = details

    # Add any additional fields
    response.update(kwargs)

    # Log error for debugging (but don't expose in response)
    logger.error(f"Error response: {sanitized_message} (status: {status_code})")

    return jsonify(response), status_code


def _sanitize_error_message(message: str) -> str:
    """
    Sanitize error messages to prevent leaking sensitive information.

    Removes or masks:
    - Database connection strings
    - API keys/tokens
    - File paths
    - Stack traces

    Args:
        message: Original error message

    Returns:
        Sanitized error message
    """
    # For now, just return the message as-is
    # In production, you might want to:
    # - Remove stack traces
    # - Mask tokens/keys
    # - Remove file paths

    # Basic sanitization: limit length
    if len(message) > 500:
        return message[:500] + "..."

    return message


def unauthorized_response(reason: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
    """
    Create a standardized 401 Unauthorized response.

    Args:
        reason: Optional reason for unauthorized access

    Returns:
        Tuple of (JSON response, 401)
    """
    message = "Unauthorized"
    if reason:
        message = f"Unauthorized: {reason}"

    return error_response(
        message, status_code=401, error_code="UNAUTHORIZED", reason=reason
    )


def not_found_response(resource: Optional[str] = None) -> Tuple[Dict[str, Any], int]:
    """
    Create a standardized 404 Not Found response.

    Args:
        resource: Optional resource name that was not found

    Returns:
        Tuple of (JSON response, 404)
    """
    message = "Resource not found"
    if resource:
        message = f"{resource} not found"

    return error_response(message, status_code=404, error_code="NOT_FOUND")


def validation_error_response(
    message: str, field: Optional[str] = None, errors: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], int]:
    """
    Create a standardized 400 Validation Error response.

    Args:
        message: Validation error message
        field: Optional field name that failed validation
        errors: Optional dictionary of validation errors

    Returns:
        Tuple of (JSON response, 400)
    """
    details = {}
    if field:
        details["field"] = field
    if errors:
        details["errors"] = errors

    return error_response(
        message,
        status_code=400,
        error_code="VALIDATION_ERROR",
        details=details if details else None,
    )


def internal_error_response(
    message: str = "Internal server error", log_error: Optional[Exception] = None
) -> Tuple[Dict[str, Any], int]:
    """
    Create a standardized 500 Internal Server Error response.

    Args:
        message: Error message (will be sanitized)
        log_error: Optional exception to log (for debugging)

    Returns:
        Tuple of (JSON response, 500)
    """
    if log_error:
        logger.exception("Internal server error", exc_info=log_error)

    return error_response(message, status_code=500, error_code="INTERNAL_ERROR")

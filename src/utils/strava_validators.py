"""
Strava Integration Validation Utilities
=======================================

Utility functions for validating Strava-related input parameters.

These functions provide consistent validation patterns for:
- Athlete IDs (Strava athlete IDs)
- Activity IDs (Strava activity IDs)
- User IDs (internal UUIDs)
- Webhook event data
- Ingestion parameters

Usage:
    from src.utils.strava_validators import validate_athlete_id, validate_activity_id

    athlete_id, error = validate_athlete_id(athlete_id_param)
    if error:
        return error
"""

import re
import uuid
from typing import Optional, Tuple, Dict, Any
from src.utils.response_utils import validation_error_response


def validate_athlete_id(athlete_id: Any) -> Tuple[Optional[int], Optional[tuple]]:
    """
    Validate Strava athlete ID.

    Args:
        athlete_id: Athlete ID to validate (can be int, str, or None)

    Returns:
        Tuple of (validated_athlete_id, error_response):
        - If valid: (athlete_id as int, None)
        - If invalid: (None, error_response_tuple)

    Example:
        athlete_id, error = validate_athlete_id(request.args.get("athlete_id"))
        if error:
            return error
    """
    if athlete_id is None:
        return None, validation_error_response(
            message="athlete_id is required",
            field="athlete_id",
        )

    try:
        # Convert to int if string
        if isinstance(athlete_id, str):
            athlete_id = int(athlete_id)

        # Must be positive integer
        if not isinstance(athlete_id, int) or athlete_id <= 0:
            return None, validation_error_response(
                message="athlete_id must be a positive integer",
                field="athlete_id",
            )

        # Strava athlete IDs are typically 6-9 digits
        if athlete_id > 999999999:
            return None, validation_error_response(
                message="athlete_id is too large (invalid format)",
                field="athlete_id",
            )

        return athlete_id, None

    except (ValueError, TypeError):
        return None, validation_error_response(
            message="athlete_id must be a valid integer",
            field="athlete_id",
        )


def validate_activity_id(activity_id: Any) -> Tuple[Optional[int], Optional[tuple]]:
    """
    Validate Strava activity ID.

    Args:
        activity_id: Activity ID to validate (can be int, str, or None)

    Returns:
        Tuple of (validated_activity_id, error_response):
        - If valid: (activity_id as int, None)
        - If invalid: (None, error_response_tuple)

    Example:
        activity_id, error = validate_activity_id(request.args.get("activity_id"))
        if error:
            return error
    """
    if activity_id is None:
        return None, validation_error_response(
            message="activity_id is required",
            field="activity_id",
        )

    try:
        # Convert to int if string
        if isinstance(activity_id, str):
            activity_id = int(activity_id)

        # Must be positive integer
        if not isinstance(activity_id, int) or activity_id <= 0:
            return None, validation_error_response(
                message="activity_id must be a positive integer",
                field="activity_id",
            )

        return activity_id, None

    except (ValueError, TypeError):
        return None, validation_error_response(
            message="activity_id must be a valid integer",
            field="activity_id",
        )


def validate_user_id(user_id: Any) -> Tuple[Optional[str], Optional[tuple]]:
    """
    Validate internal user ID (UUID format).

    Args:
        user_id: User ID to validate (should be UUID string)

    Returns:
        Tuple of (validated_user_id, error_response):
        - If valid: (user_id as str, None)
        - If invalid: (None, error_response_tuple)

    Example:
        user_id, error = validate_user_id(request.args.get("user_id"))
        if error:
            return error
    """
    if user_id is None:
        return None, validation_error_response(
            message="user_id is required",
            field="user_id",
        )

    if not isinstance(user_id, str):
        return None, validation_error_response(
            message="user_id must be a string",
            field="user_id",
        )

    # Validate UUID format
    uuid_pattern = re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    if not uuid_pattern.match(user_id):
        try:
            # Try to parse as UUID to get better error message
            uuid.UUID(user_id)
        except ValueError:
            return None, validation_error_response(
                message="user_id must be a valid UUID",
                field="user_id",
            )

    return user_id, None


def validate_ingestion_params(
    lookback_days: Any = None,
    max_activities: Any = None,
    batch_size: Any = None,
    per_page: Any = None,
) -> Tuple[Optional[Dict[str, int]], Optional[tuple]]:
    """
    Validate ingestion parameters.

    Args:
        lookback_days: Number of days to look back (optional, default: 365)
        max_activities: Maximum activities to fetch (optional)
        batch_size: Batch size for enrichment (optional)
        per_page: Activities per API page (optional)

    Returns:
        Tuple of (validated_params_dict, error_response):
        - If valid: (dict with validated params, None)
        - If invalid: (None, error_response_tuple)

    Example:
        params, error = validate_ingestion_params(
            lookback_days=request.args.get("lookback_days"),
            max_activities=request.args.get("max_activities")
        )
        if error:
            return error
    """
    validated = {}
    errors = {}

    # Validate lookback_days
    if lookback_days is not None:
        try:
            lookback_days = int(lookback_days)
            if lookback_days < 1 or lookback_days > 3650:  # Max 10 years
                errors["lookback_days"] = "must be between 1 and 3650"
            else:
                validated["lookback_days"] = lookback_days
        except (ValueError, TypeError):
            errors["lookback_days"] = "must be a valid integer"

    # Validate max_activities
    if max_activities is not None:
        try:
            max_activities = int(max_activities)
            if max_activities < 1 or max_activities > 10000:
                errors["max_activities"] = "must be between 1 and 10000"
            else:
                validated["max_activities"] = max_activities
        except (ValueError, TypeError):
            errors["max_activities"] = "must be a valid integer"

    # Validate batch_size
    if batch_size is not None:
        try:
            batch_size = int(batch_size)
            if batch_size < 1 or batch_size > 1000:
                errors["batch_size"] = "must be between 1 and 1000"
            else:
                validated["batch_size"] = batch_size
        except (ValueError, TypeError):
            errors["batch_size"] = "must be a valid integer"

    # Validate per_page
    if per_page is not None:
        try:
            per_page = int(per_page)
            if per_page < 1 or per_page > 200:  # Strava API limit
                errors["per_page"] = "must be between 1 and 200"
            else:
                validated["per_page"] = per_page
        except (ValueError, TypeError):
            errors["per_page"] = "must be a valid integer"

    if errors:
        return None, validation_error_response(
            message="Invalid ingestion parameters",
            errors=errors,
        )

    return validated, None


def validate_webhook_event(
    event_data: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], Optional[tuple]]:
    """
    Validate webhook event data from Strava.

    Args:
        event_data: Webhook event data dictionary

    Returns:
        Tuple of (validated_event_data, error_response):
        - If valid: (event_data dict, None)
        - If invalid: (None, error_response_tuple)

    Example:
        validated, error = validate_webhook_event(request.get_json())
        if error:
            return error
    """
    if not isinstance(event_data, dict):
        return None, validation_error_response(
            message="Webhook event data must be a JSON object",
            field="body",
        )

    required_fields = ["object_type", "object_id", "aspect_type", "owner_id"]
    missing_fields = []
    errors = {}

    # Check required fields
    for field in required_fields:
        if field not in event_data or event_data[field] is None:
            missing_fields.append(field)
            errors[field] = "required"

    if missing_fields:
        return None, validation_error_response(
            message=f"Missing required fields: {', '.join(missing_fields)}",
            errors=errors,
        )

    # Validate object_type
    object_type = event_data.get("object_type")
    if object_type not in ["activity", "athlete"]:
        errors["object_type"] = f"must be 'activity' or 'athlete', got '{object_type}'"

    # Validate aspect_type
    aspect_type = event_data.get("aspect_type")
    if object_type == "activity" and aspect_type not in ["create", "update", "delete"]:
        errors["aspect_type"] = (
            f"for activity must be 'create', 'update', or 'delete', got '{aspect_type}'"
        )
    elif object_type == "athlete" and aspect_type not in ["update", "delete"]:
        errors["aspect_type"] = (
            f"for athlete must be 'update' or 'delete', got '{aspect_type}'"
        )

    # Validate object_id (should be positive integer)
    object_id = event_data.get("object_id")
    try:
        object_id_int = int(object_id)
        if object_id_int <= 0:
            errors["object_id"] = "must be a positive integer"
    except (ValueError, TypeError):
        errors["object_id"] = "must be a valid integer"

    # Validate owner_id (should be positive integer - Strava athlete ID)
    owner_id = event_data.get("owner_id")
    try:
        owner_id_int = int(owner_id)
        if owner_id_int <= 0:
            errors["owner_id"] = "must be a positive integer"
    except (ValueError, TypeError):
        errors["owner_id"] = "must be a valid integer"

    if errors:
        return None, validation_error_response(
            message="Invalid webhook event data",
            errors=errors,
        )

    return event_data, None


def validate_oauth_code(code: Any) -> Tuple[Optional[str], Optional[tuple]]:
    """
    Validate OAuth authorization code.

    Args:
        code: OAuth code to validate

    Returns:
        Tuple of (validated_code, error_response):
        - If valid: (code as str, None)
        - If invalid: (None, error_response_tuple)

    Example:
        code, error = validate_oauth_code(request.args.get("code"))
        if error:
            return error
    """
    if code is None:
        return None, validation_error_response(
            message="OAuth code is required",
            field="code",
        )

    if not isinstance(code, str):
        return None, validation_error_response(
            message="OAuth code must be a string",
            field="code",
        )

    # OAuth codes are typically 40-200 characters
    if len(code) < 10 or len(code) > 500:
        return None, validation_error_response(
            message="OAuth code has invalid length",
            field="code",
        )

    return code, None
